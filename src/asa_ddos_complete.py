#!/usr/bin/env python3
"""
ASA DDOS Auto-Remediation System - Enterprise Edition
- Detectare și blocare DDOS cu ML
- Notificări Slack/Email
- Dashboard web pentru management
- Whitelist și machine learning
"""

import paramiko
import re
import time
import logging
import json
import smtplib
import requests
import sqlite3
import pickle
from datetime import datetime, timedelta
from collections import defaultdict
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, render_template, jsonify, request
from threading import Thread
import socket
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import numpy as np
import hashlib

# ============= CONFIGURARE LOGGING =============

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/asa_ddos_remediation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============= CONFIGURĂRI GLOBALE =============

CONFIG = {
    'asa': {
        'host': '192.168.1.1',
        'username': 'admin',
        'password': 'your_password'
    },
    'slack': {
        'webhook_url': 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL',
        'enabled': True
    },
    'email': {
        'smtp_server': 'smtp.gmail.com',
        'smtp_port': 587,
        'sender': 'alerts@yourdomain.com',
        'sender_password': 'your_app_password',
        'recipients': ['security@yourdomain.com', 'it-manager@yourdomain.com'],
        'enabled': True
    },
    'auto_unblock_hours': 24,
    'ml_threshold': -0.5,  # Isolation Forest anomaly threshold
    'dashboard_port': 5000
}

# ============= DATABASE - SQLite =============

class DatabaseManager:
    def __init__(self, db_path='/var/lib/asa-ddos/alerts.db'):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Inițializează baza de date"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Tabelă IPs blocate
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS blocked_ips (
                id INTEGER PRIMARY KEY,
                ip_address TEXT UNIQUE,
                reason TEXT,
                severity TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                auto_unblock_time DATETIME,
                status TEXT DEFAULT 'active',
                protocol TEXT,
                source_port INTEGER,
                dest_ip TEXT,
                dest_port INTEGER
            )
        ''')
        
        # Tabelă Whitelist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS whitelist (
                id INTEGER PRIMARY KEY,
                ip_address TEXT UNIQUE,
                description TEXT,
                added_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                added_by TEXT
            )
        ''')
        
        # Tabelă alerts
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY,
                ip_address TEXT,
                alert_type TEXT,
                message TEXT,
                severity TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                slack_sent BOOLEAN DEFAULT 0,
                email_sent BOOLEAN DEFAULT 0
            )
        ''')
        
        # Tabelă ML training data
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ml_training_data (
                id INTEGER PRIMARY KEY,
                packets_per_sec INTEGER,
                bytes_per_sec INTEGER,
                unique_sources INTEGER,
                protocol TEXT,
                port_diversity INTEGER,
                is_ddos BOOLEAN,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("Database initialized")
    
    def add_blocked_ip(self, ip_address, reason, severity, **kwargs):
        """Adaugă IP blocat în baza de date"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        auto_unblock = datetime.now() + timedelta(
            hours=CONFIG['auto_unblock_hours']
        )
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO blocked_ips 
                (ip_address, reason, severity, auto_unblock_time, 
                 protocol, source_port, dest_ip, dest_port)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                ip_address, reason, severity, auto_unblock,
                kwargs.get('protocol'), kwargs.get('source_port'),
                kwargs.get('dest_ip'), kwargs.get('dest_port')
            ))
            conn.commit()
            logger.info(f"IP {ip_address} adăugată în baza de date")
        except Exception as e:
            logger.error(f"Eroare adăugare IP în DB: {e}")
        finally:
            conn.close()
    
    def get_blocked_ips(self):
        """Obține toate IPs blocate"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM blocked_ips WHERE status = "active"')
        ips = cursor.fetchall()
        conn.close()
        return ips
    
    def add_to_whitelist(self, ip_address, description, added_by="system"):
        """Adaugă IP în whitelist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO whitelist (ip_address, description, added_by)
                VALUES (?, ?, ?)
            ''', (ip_address, description, added_by))
            conn.commit()
            logger.info(f"IP {ip_address} adăugată în whitelist")
        except sqlite3.IntegrityError:
            logger.warning(f"IP {ip_address} deja în whitelist")
        finally:
            conn.close()
    
    def is_whitelisted(self, ip_address):
        """Verifică dacă IP e în whitelist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM whitelist WHERE ip_address = ?', (ip_address,))
        result = cursor.fetchone()
        conn.close()
        return result is not None
    
    def log_alert(self, ip_address, alert_type, message, severity):
        """Logare alert"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO alerts (ip_address, alert_type, message, severity)
            VALUES (?, ?, ?, ?)
        ''', (ip_address, alert_type, message, severity))
        conn.commit()
        conn.close()
    
    def add_ml_training_data(self, pps, bps, unique_sources, protocol, port_div, is_ddos):
        """Adaugă date pentru ML training"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO ml_training_data 
            (packets_per_sec, bytes_per_sec, unique_sources, protocol, port_diversity, is_ddos)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (pps, bps, unique_sources, protocol, port_div, is_ddos))
        conn.commit()
        conn.close()

# ============= NOTIFICĂRI - SLACK & EMAIL =============

class AlertNotifier:
    def __init__(self):
        self.db = DatabaseManager()
    
    def send_slack(self, title, message, color="danger", fields=None):
        """Trimite notificare pe Slack"""
        if not CONFIG['slack']['enabled']:
            logger.warning("Slack disabled in config")
            return False
        
        try:
            payload = {
                "attachments": [{
                    "fallback": title,
                    "color": color,
                    "title": title,
                    "text": message,
                    "ts": int(time.time())
                }]
            }
            
            if fields:
                payload["attachments"][0]["fields"] = fields
            
            response = requests.post(
                CONFIG['slack']['webhook_url'],
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"Slack alert sent: {title}")
                return True
            else:
                logger.error(f"Slack error: {response.status_code}")
                return False
        
        except Exception as e:
            logger.error(f"Eroare trimitere Slack: {e}")
            return False
    
    def send_email(self, subject, body_html, recipients=None):
        """Trimite email notificare"""
        if not CONFIG['email']['enabled']:
            logger.warning("Email disabled in config")
            return False
        
        recipients = recipients or CONFIG['email']['recipients']
        
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = CONFIG['email']['sender']
            msg['To'] = ', '.join(recipients)
            
            msg.attach(MIMEText(body_html, 'html'))
            
            with smtplib.SMTP(CONFIG['email']['smtp_server'], CONFIG['email']['smtp_port']) as server:
                server.starttls()
                server.login(CONFIG['email']['sender'], CONFIG['email']['sender_password'])
                server.sendmail(CONFIG['email']['sender'], recipients, msg.as_string())
            
            logger.info(f"Email sent to {recipients}")
            return True
        
        except Exception as e:
            logger.error(f"Eroare trimitere email: {e}")
            return False
    
    def alert_ddos_detected(self, ddos_info):
        """Alarmă DDOS detectat"""
        slack_fields = [
            {"title": "IP Sursă", "value": ddos_info.get('source_ip'), "short": True},
            {"title": "IP Destinație", "value": ddos_info.get('dest_ip'), "short": True},
            {"title": "Port", "value": str(ddos_info.get('dest_port')), "short": True},
            {"title": "Protocol", "value": ddos_info.get('protocol'), "short": True},
            {"title": "Severitate", "value": ddos_info.get('severity'), "short": True},
            {"title": "Timestamp", "value": str(ddos_info.get('timestamp')), "short": True}
        ]
        
        self.send_slack(
            "🚨 DDOS Attack Detected",
            f"Atac DDOS detectat de la {ddos_info['source_ip']}",
            color="danger",
            fields=slack_fields
        )
        
        email_body = f"""
        <html>
            <body>
                <h2 style="color: red;">⚠️ DDOS Attack Alert</h2>
                <table border="1" cellpadding="10">
                    <tr><td><b>IP Sursă</b></td><td>{ddos_info['source_ip']}</td></tr>
                    <tr><td><b>IP Destinație</b></td><td>{ddos_info['dest_ip']}</td></tr>
                    <tr><td><b>Port</b></td><td>{ddos_info['dest_port']}</td></tr>
                    <tr><td><b>Protocol</b></td><td>{ddos_info['protocol']}</td></tr>
                    <tr><td><b>Severitate</b></td><td>{ddos_info['severity']}</td></tr>
                    <tr><td><b>Timestamp</b></td><td>{ddos_info['timestamp']}</td></tr>
                </table>
                <p>Acțiune: IP a fost blocat pe ASA firewall.</p>
            </body>
        </html>
        """
        
        self.send_email("🚨 DDOS Attack Detected - Action Taken", email_body)
    
    def alert_ip_unblocked(self, ip_address):
        """Alarmă IP deblocat"""
        self.send_slack(
            "✅ IP Deblocked",
            f"IP {ip_address} a fost deblochată automat",
            color="good"
        )

# ============= MACHINE LEARNING - DDOS DETECTION =============

class MLDDOSDetector:
    def __init__(self):
        self.model = IsolationForest(contamination=0.1, random_state=42)
        self.scaler = StandardScaler()
        self.model_path = '/var/lib/asa-ddos/ml_model.pkl'
        self.load_or_train_model()
    
    def load_or_train_model(self):
        """Încarcă model salvat sau antrenează nou"""
        try:
            with open(self.model_path, 'rb') as f:
                self.model = pickle.load(f)
            logger.info("ML model loaded from disk")
        except FileNotFoundError:
            logger.info("No ML model found, starting with untrained model")
    
    def extract_features(self, traffic_data):
        """Extrage features din traffic data
        
        Features:
        - packets_per_sec: Pachete pe secundă
        - bytes_per_sec: Bytes pe secundă
        - unique_sources: Numărul de IP-uri sursă unice
        - port_diversity: Diversitatea porturilor folosite
        - protocol_variety: Varietatea de protocoale
        """
        return np.array([
            traffic_data.get('packets_per_sec', 0),
            traffic_data.get('bytes_per_sec', 0),
            traffic_data.get('unique_sources', 0),
            traffic_data.get('port_diversity', 0),
            traffic_data.get('protocol_variety', 0)
        ]).reshape(1, -1)
    
    def predict_ddos(self, traffic_data):
        """Predicție ML pentru DDOS
        
        Return:
        - is_ddos: Boolean
        - score: Anomaly score (-1 to 1)
        - confidence: Incredere predicție
        """
        try:
            features = self.extract_features(traffic_data)
            
            # Normalize features
            features_scaled = self.scaler.fit_transform(features)
            
            # Anomaly score
            anomaly_score = self.model.score_samples(features_scaled)[0]
            
            # Predicție
            is_ddos = anomaly_score < CONFIG['ml_threshold']
            
            # Confidence (distanța de la threshold)
            confidence = abs(anomaly_score - CONFIG['ml_threshold'])
            
            logger.info(f"ML Prediction - Score: {anomaly_score:.3f}, DDOS: {is_ddos}, Confidence: {confidence:.3f}")
            
            return {
                'is_ddos': is_ddos,
                'score': anomaly_score,
                'confidence': min(confidence, 1.0)
            }
        
        except Exception as e:
            logger.error(f"ML prediction error: {e}")
            return {
                'is_ddos': False,
                'score': 0,
                'confidence': 0
            }
    
    def train_from_historical_data(self, db):
        """Antrenează model din date istorice"""
        try:
            conn = sqlite3.connect(db.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT packets_per_sec, bytes_per_sec, unique_sources, 
                       port_diversity, is_ddos FROM ml_training_data
            ''')
            
            data = cursor.fetchall()
            conn.close()
            
            if len(data) < 10:
                logger.warning("Insuficient training data")
                return
            
            X = np.array(data)[:, :-1].astype(float)
            
            # Antrenare
            self.scaler.fit(X)
            X_scaled = self.scaler.transform(X)
            self.model.fit(X_scaled)
            
            # Salvare
            with open(self.model_path, 'wb') as f:
                pickle.dump(self.model, f)
            
            logger.info(f"ML model trained on {len(data)} samples")
        
        except Exception as e:
            logger.error(f"ML training error: {e}")

# ============= ASA FIREWALL CONTROL =============

class ASAController:
    def __init__(self):
        self.asa_host = CONFIG['asa']['host']
        self.username = CONFIG['asa']['username']
        self.password = CONFIG['asa']['password']
        self.ssh = None
    
    def connect(self):
        """Conectare la ASA"""
        try:
            self.ssh = paramiko.SSHClient()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh.connect(
                self.asa_host,
                username=self.username,
                password=self.password,
                timeout=10
            )
            logger.info(f"Connected to ASA: {self.asa_host}")
            return True
        except Exception as e:
            logger.error(f"ASA connection error: {e}")
            return False
    
    def send_command(self, command):
        """Trimite comandă la ASA"""
        try:
            shell = self.ssh.invoke_shell()
            shell.send(f"{command}\n")
            time.sleep(0.5)
            output = shell.recv(4096).decode()
            return output
        except Exception as e:
            logger.error(f"Command error: {e}")
            return None
    
    def block_ip(self, ip_address):
        """Blochează IP pe ASA"""
        commands = [
            "conf t",
            f"access-list DDOS_BLOCK line 1 deny tcp any host {ip_address}",
            f"access-list DDOS_BLOCK line 2 deny udp any host {ip_address}",
            f"access-list DDOS_BLOCK line 3 deny icmp any host {ip_address}",
            "access-group DDOS_BLOCK in interface outside",
            "write mem",
            "exit"
        ]
        
        try:
            for cmd in commands:
                self.send_command(cmd)
            logger.warning(f"IP BLOCKED on ASA: {ip_address}")
            return True
        except Exception as e:
            logger.error(f"Block IP error: {e}")
            return False
    
    def unblock_ip(self, ip_address):
        """Deblochează IP pe ASA"""
        commands = [
            "conf t",
            f"no access-list DDOS_BLOCK line 1 deny tcp any host {ip_address}",
            f"no access-list DDOS_BLOCK line 2 deny udp any host {ip_address}",
            f"no access-list DDOS_BLOCK line 3 deny icmp any host {ip_address}",
            "write mem",
            "exit"
        ]
        
        try:
            for cmd in commands:
                self.send_command(cmd)
            logger.info(f"IP UNBLOCKED on ASA: {ip_address}")
            return True
        except Exception as e:
            logger.error(f"Unblock IP error: {e}")
            return False
    
    def disconnect(self):
        """Deconectare ASA"""
        if self.ssh:
            self.ssh.close()

# ============= DDOS REMEDIATION ENGINE =============

class DDOSRemediationEngine:
    def __init__(self):
        self.db = DatabaseManager()
        self.notifier = AlertNotifier()
        self.asa = ASAController()
        self.ml_detector = MLDDOSDetector()
    
    def parse_ids_alert(self, syslog_message):
        """Parse alert de la IDS"""
        ddos_info = {
            'source_ip': None,
            'dest_ip': None,
            'dest_port': None,
            'protocol': None,
            'severity': 'MEDIUM',
            'timestamp': datetime.now()
        }
        
        # Extrage IP și port
        ip_pattern = r'\{(\w+)\}\s+(\d+\.\d+\.\d+\.\d+):(\d+)\s+->\s+(\d+\.\d+\.\d+\.\d+):(\d+)'
        match = re.search(ip_pattern, syslog_message)
        
        if match:
            ddos_info['protocol'] = match.group(1)
            ddos_info['source_ip'] = match.group(2)
            ddos_info['source_port'] = match.group(3)
            ddos_info['dest_ip'] = match.group(4)
            ddos_info['dest_port'] = match.group(5)
        
        # Detectează severitate
        if "High" in syslog_message or "CRITICAL" in syslog_message:
            ddos_info['severity'] = 'HIGH'
        
        return ddos_info
    
    def process_alert(self, syslog_message):
        """Procesează alert DDOS"""
        ddos_info = self.parse_ids_alert(syslog_message)
        
        if not ddos_info['source_ip']:
            logger.warning("Could not parse IDS alert")
            return
        
        source_ip = ddos_info['source_ip']
        
        # Check whitelist
        if self.db.is_whitelisted(source_ip):
            logger.info(f"IP {source_ip} is whitelisted, skipping")
            return
        
        logger.warning(f"DDOS Alert from: {source_ip}")
        
        # ML Detection - Optional enhanced check
        traffic_data = {
            'packets_per_sec': 10000,  # Din metrics real
            'bytes_per_sec': 1000000,
            'unique_sources': 500,
            'port_diversity': 100,
            'protocol_variety': 3
        }
        
        ml_result = self.ml_detector.predict_ddos(traffic_data)
        
        if ml_result['confidence'] > 0.7:
            logger.critical(f"ML HIGH CONFIDENCE DDOS: {source_ip}")
        
        # Acțiune: Blocare IP
        if self.asa.connect():
            self.asa.block_ip(source_ip)
            self.asa.disconnect()
        
        # Log în baza de date
        self.db.add_blocked_ip(
            source_ip,
            "DDOS - IDS Alert",
            ddos_info['severity'],
            protocol=ddos_info['protocol'],
            source_port=ddos_info['source_port'],
            dest_ip=ddos_info['dest_ip'],
            dest_port=ddos_info['dest_port']
        )
        
        # Notificări
        self.notifier.alert_ddos_detected(ddos_info)
        self.db.log_alert(source_ip, "DDOS_DETECTED", syslog_message, ddos_info['severity'])
    
    def check_auto_unblock(self):
        """Verifică și deblochează IPs după interval"""
        blocked_ips = self.db.get_blocked_ips()
        
        for ip_data in blocked_ips:
            ip_address = ip_data[1]
            auto_unblock_time = ip_data[5]
            
            if datetime.fromisoformat(auto_unblock_time) <= datetime.now():
                logger.info(f"Auto-unblocking IP: {ip_address}")
                
                if self.asa.connect():
                    self.asa.unblock_ip(ip_address)
                    self.asa.disconnect()
                
                self.notifier.alert_ip_unblocked(ip_address)

# ============= FLASK DASHBOARD =============

app = Flask(__name__)
remediation_engine = DDOSRemediationEngine()

@app.route('/')
def dashboard():
    """Dashboard HTML"""
    return render_template('dashboard.html')

@app.route('/api/blocked-ips', methods=['GET'])
def api_blocked_ips():
    """API - Lista IPs blocate"""
    db = DatabaseManager()
    blocked_ips = db.get_blocked_ips()
    
    ips_list = []
    for ip_data in blocked_ips:
        ips_list.append({
            'ip': ip_data[1],
            'reason': ip_data[2],
            'severity': ip_data[3],
            'timestamp': ip_data[4],
            'auto_unblock': ip_data[5]
        })
    
    return jsonify(ips_list)

@app.route('/api/unblock-ip/<ip_address>', methods=['POST'])
def api_unblock_ip(ip_address):
    """API - Deblochează IP manual"""
    asa = ASAController()
    
    if asa.connect():
        asa.unblock_ip(ip_address)
        asa.disconnect()
        return jsonify({'success': True, 'message': f'IP {ip_address} unblocked'})
    
    return jsonify({'success': False, 'error': 'Failed to unblock'}), 500

@app.route('/api/whitelist', methods=['GET', 'POST'])
def api_whitelist():
    """API - Manage whitelist"""
    db = DatabaseManager()
    
    if request.method == 'POST':
        data = request.get_json()
        db.add_to_whitelist(data['ip'], data['description'], data.get('added_by', 'admin'))
        return jsonify({'success': True})
    
    # GET - Return whitelist
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT ip_address, description FROM whitelist')
    whitelist = [{'ip': row[0], 'description': row[1]} for row in cursor.fetchall()]
    conn.close()
    
    return jsonify(whitelist)

@app.route('/api/alerts', methods=['GET'])
def api_alerts():
    """API - Recent alerts"""
    db = DatabaseManager()
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT ip_address, alert_type, message, severity, timestamp 
        FROM alerts 
        ORDER BY timestamp DESC LIMIT 50
    ''')
    alerts = [
        {'ip': row[0], 'type': row[1], 'message': row[2], 'severity': row[3], 'time': row[4]}
        for row in cursor.fetchall()
    ]
    conn.close()
    
    return jsonify(alerts)

@app.route('/api/stats', methods=['GET'])
def api_stats():
    """API - Statistics"""
    db = DatabaseManager()
    
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM blocked_ips WHERE status = "active"')
    active_blocks = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM alerts WHERE timestamp > datetime("now", "-24 hours")')
    alerts_24h = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM whitelist')
    whitelist_count = cursor.fetchone()[0]
    
    conn.close()
    
    return jsonify({
        'active_blocks': active_blocks,
        'alerts_24h': alerts_24h,
        'whitelist_count': whitelist_count
    })

# ============= SYSLOG LISTENER =============

class SyslogListener:
    def __init__(self, port=514):
        self.port = port
        self.socket = None
        self.engine = DDOSRemediationEngine()
    
    def start(self):
        """Pornire listener"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(('0.0.0.0', self.port))
        
        logger.info(f"Syslog listener started on port {self.port}")
        
        try:
            while True:
                data, addr = self.socket.recvfrom(4096)
                syslog_msg = data.decode('utf-8', errors='ignore')
                
                if "DDoS" in syslog_msg or "DOS" in syslog_msg or "IDS" in syslog_msg:
                    logger.warning(f"IDS Alert from {addr[0]}: {syslog_msg[:100]}")
                    # Process în thread separat
                    Thread(target=self.engine.process_alert, args=(syslog_msg,), daemon=True).start()
        
        except KeyboardInterrupt:
            logger.info("Syslog listener stopped")
        finally:
            if self.socket:
                self.socket.close()

# ============= MAIN =============

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == 'syslog':
            # Pornire listener
            listener = SyslogListener()
            listener.start()
        
        elif sys.argv[1] == 'dashboard':
            # Pornire dashboard web
            app.run(host='0.0.0.0', port=CONFIG['dashboard_port'], debug=False)
        
        elif sys.argv[1] == 'test':
            # Test
            engine = DDOSRemediationEngine()
            test_alert = """
            [**] [1:2345:1] DDoS Attack Detected [**]
            {TCP} 203.0.113.50:54321 -> 192.168.1.100:80
            """
            engine.process_alert(test_alert)
    
    else:
        print("""
        Usage: python3 asa_ddos_complete.py [command]
        
        Commands:
            syslog      - Start syslog listener
            dashboard   - Start web dashboard
            test        - Test alert processing
        """)
