# ASA DDOS Auto-Remediation System - Documentație Completă

## 📋 Cuprins

1. [Prezentare Generală](#prezentare-generală)
2. [Caracteristici](#caracteristici)
3. [Cerințe Sistem](#cerințe-sistem)
4. [Instalare](#instalare)
5. [Configurare](#configurare)
6. [Utilizare](#utilizare)
7. [Dashboard Web](#dashboard-web)
8. [Integrare Slack/Email](#integrare-slackemail)
9. [Machine Learning](#machine-learning)
10. [Whitelist Management](#whitelist-management)
11. [Troubleshooting](#troubleshooting)

---

## Prezentare Generală

Sistemul de auto-remediere DDOS pentru Cisco ASA este o soluție enterprise-grade care:

- **Detectează** atacuri DDOS în timp real din alerturile IDS
- **Blochează** automat IP-urile atacatoare pe firewall
- **Notifică** echipa via Slack și Email
- **Monitorizează** folosind Machine Learning pentru detecție precisă
- **Gestionează** whitelist-ul de IP-uri de încredere
- **Oferă** dashboard web pentru control manual

### Fluxul de Remediere

```
IDS Alert (Syslog)
    ↓
Parser DDOS Detection
    ↓
Check Whitelist
    ↓
ML Anomaly Detection
    ↓
Block IP on ASA
    ↓
Database Logging
    ↓
Send Alerts (Slack/Email)
    ↓
Auto-Unblock (24h)
```

---

## Caracteristici

### 🔒 Blocare Automată
- Detectare în timp real a alerturilor IDS
- Aplicare instantanee a regulilor ASA
- Rate-limiting inteligent

### 📊 Machine Learning
- Isolation Forest pentru detecție anomalii
- Antrenare din date istorice
- Confidence scoring

### 🔔 Notificări Multiple
- Slack real-time alerts cu detalii atac
- Email cu HTML templates
- Timestamp și IP information

### ✅ Whitelist Management
- Adăugare rapida a IP-urilor de încredere
- Excluzie din blocări automate
- UI dashboard

### 📈 Dashboard Web
- Lista IP-uri blocate în timp real
- Statistici și métrici
- Timeline cu ultimos alerts
- Control manual unblock

### 🗄️ Bază de Date SQLite
- Stocaj persistent al alertelor
- Tracking auto-unblock
- Date pentru ML training

---

## Cerințe Sistem

### Hardware
- CPU: 2+ cores
- RAM: 2+ GB
- Storage: 10+ GB (pentru logs)

### Software
- Ubuntu 20.04+ / Debian 11+
- Python 3.8+
- SSH client pentru ASA

### Network
- Conectivitate SSH la ASA firewall
- Port UDP 514 pentru syslog (IDS alerts)
- Port 5000/8080 pentru dashboard
- Internet pentru notificări Slack/Email (opțional)

### Acces
- Sudo access pe server
- SSH credentials pentru ASA
- Slack webhook (opțional)
- Email app password (pentru Gmail)

---

## Instalare

### Pas 1: Download Fișiere

```bash
# Clone repository sau download manual
git clone https://github.com/yourusername/asa-ddos-remediation
cd asa-ddos-remediation
```

### Pas 2: Rulează Script Instalare

```bash
sudo chmod +x install.sh
sudo ./install.sh
```

Script-ul va interoga pentru:
- IP ASA firewall
- Credențiale ASA
- Slack webhook URL
- Email configuration
- Recipients

### Pas 3: Verificare Instalare

```bash
# Check servicii
sudo systemctl status asa-ddos-syslog
sudo systemctl status asa-ddos-dashboard

# Check logs
tail -f /var/log/asa_ddos_remediation.log

# Check database
sqlite3 /var/lib/asa-ddos/alerts.db ".tables"
```

---

## Configurare

### ASA Firewall

#### 1. Activare SSH

```
asa(config)# ssh 0.0.0.0 0.0.0.0 inside
asa(config)# ssh timeout 30
asa(config)# ssh key-exchange group dh-group1
```

#### 2. Configurare Syslog Output

```
asa(config)# logging enable
asa(config)# logging timestamp
asa(config)# logging host inside 192.168.1.100 514
asa(config)# logging trap informational
asa(config)# write mem
```

#### 3. Enable Threat Detection

```
asa(config)# threat-detection basic-threat
asa(config)# threat-detection statistics host
asa(config)# threat-detection statistics port
asa(config)# write mem
```

### IDS / Snort Configuration

Dacă folosești IDS inline:

```
asa(config)# class-map IDS_CLASS
asa(config-cmap)# match access-list IDS_ACL
asa(config-cmap)# exit

asa(config)# policy-map IDS_POLICY
asa(config-pmap)# class IDS_CLASS
asa(config-pmap-c)# ids signature-id 1:1000-2000 inline-drop
```

### Server Configuration

Editează configurația:

```bash
sudo nano /etc/asa-ddos/config.json
```

Exemplu:

```json
{
    "asa": {
        "host": "192.168.1.1",
        "username": "admin",
        "password": "secure_password"
    },
    "slack": {
        "webhook_url": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
        "enabled": true
    },
    "email": {
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
        "sender": "alerts@yourdomain.com",
        "sender_password": "your_app_password",
        "recipients": [
            "security@yourdomain.com",
            "it-manager@yourdomain.com"
        ],
        "enabled": true
    },
    "auto_unblock_hours": 24,
    "ml_threshold": -0.5,
    "dashboard_port": 5000
}
```

#### Configurare Gmail App Password

1. Enable 2FA pe Gmail
2. Generate app password: https://myaccount.google.com/apppasswords
3. Copiează în config

---

## Utilizare

### Pornire Servicii

```bash
# Pornire individual
sudo systemctl start asa-ddos-syslog
sudo systemctl start asa-ddos-dashboard

# Pornire amândouă
sudo systemctl start asa-ddos-*

# Enable la boot
sudo systemctl enable asa-ddos-syslog
sudo systemctl enable asa-ddos-dashboard
```

### Monitorizare Logs

```bash
# Real-time logging
tail -f /var/log/asa_ddos_remediation.log

# Systemd journal
journalctl -u asa-ddos-syslog -f
journalctl -u asa-ddos-dashboard -f

# Grep specific alerts
grep "DDOS" /var/log/asa_ddos_remediation.log
grep "BLOCKED" /var/log/asa_ddos_remediation.log
```

### Database Queries

```bash
# Connect la database
sqlite3 /var/lib/asa-ddos/alerts.db

# Listeaza tabele
.tables

# Blocked IPs
SELECT ip_address, reason, severity, timestamp FROM blocked_ips WHERE status='active';

# Whitelist
SELECT ip_address, description FROM whitelist;

# Recent alerts
SELECT * FROM alerts ORDER BY timestamp DESC LIMIT 20;

# ML training data
SELECT * FROM ml_training_data LIMIT 10;
```

### Test Alert

```bash
# Simulare alert DDOS
python3 /opt/asa-ddos-remediation/asa_ddos_complete.py test

# Manual syslog test
echo "<134>IDS Alert: {TCP} 203.0.113.50:12345 -> 192.168.1.100:80" | \
  nc -w 0 localhost 514
```

---

## Dashboard Web

### Accesare

```
http://localhost:5000              (Direct Flask)
http://localhost:8080              (Via Nginx proxy)
```

### Caracteristici

#### 1. **Statistics Panel**
- Active blocks count
- Alerts in last 24h
- Whitelisted IPs
- System status

#### 2. **Blocked IPs Tab**
- Tabel cu toate IPs blocate
- Reason, Severity, Timestamp
- Auto-unblock time countdown
- Unblock button (manual)
- Quick whitelist button

#### 3. **Whitelist Tab**
- Listeaza IPs whitelisted
- Add new IP form
- Remove from whitelist

#### 4. **Alerts Timeline**
- Recent alerts în format timeline
- Color-coded by severity
- IP source tracking
- Alert type categorization

### API Endpoints

```bash
# Get all blocked IPs
curl http://localhost:5000/api/blocked-ips

# Get whitelist
curl http://localhost:5000/api/whitelist

# Add to whitelist
curl -X POST http://localhost:5000/api/whitelist \
  -H "Content-Type: application/json" \
  -d '{"ip":"192.168.1.50","description":"Office IP"}'

# Unblock IP
curl -X POST http://localhost:5000/api/unblock-ip/203.0.113.50

# Get alerts
curl http://localhost:5000/api/alerts

# Get statistics
curl http://localhost:5000/api/stats
```

---

## Integrare Slack/Email

### Slack Setup

#### 1. Creare Webhook

1. Go to https://api.slack.com/apps
2. Create New App → From scratch
3. Name: "ASA DDOS Alerts"
4. Workspace: Select your workspace
5. Features → Incoming Webhooks → Add
6. Copy Webhook URL

#### 2. Configurare

```bash
# Edit config
sudo nano /etc/asa-ddos/config.json

# Add webhook URL
"slack": {
    "webhook_url": "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXX",
    "enabled": true
}
```

#### 3. Test

```bash
# Trigger alert
python3 -c "
from asa_ddos_complete import AlertNotifier
notifier = AlertNotifier()
notifier.send_slack('Test Alert', 'This is a test message', color='warning')
"
```

### Email Setup

#### Gmail (Recommended)

1. Enable 2FA: https://support.google.com/accounts/answer/185833
2. Generate App Password: https://myaccount.google.com/apppasswords
3. Select "Mail" and "Windows Computer"
4. Copy generated password

```json
{
    "email": {
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
        "sender": "your.email@gmail.com",
        "sender_password": "xxxx xxxx xxxx xxxx",
        "recipients": ["security@yourdomain.com"],
        "enabled": true
    }
}
```

#### Other SMTP Servers

```json
{
    "email": {
        "smtp_server": "mail.yourdomain.com",
        "smtp_port": 587,
        "sender": "alerts@yourdomain.com",
        "sender_password": "password",
        "recipients": ["admin@yourdomain.com"],
        "enabled": true
    }
}
```

#### Test Email

```bash
python3 -c "
from asa_ddos_complete import AlertNotifier
notifier = AlertNotifier()
notifier.send_email(
    'Test Subject',
    '<h1>Test Email</h1><p>This is a test</p>'
)
"
```

### Alert Templates

Sistemul trimite:

**Slack Alert:**
- IP Sursă, IP Destinație
- Port, Protocol
- Severity
- Timestamp

**Email Alert:**
- HTML formatted table
- Detalii atac
- Acțiune luată (IP blocat)
- Link toward dashboard

---

## Machine Learning

### Features Folosite

```python
1. packets_per_sec     - Pachete pe secundă
2. bytes_per_sec       - Bytes pe secundă
3. unique_sources      - Numărul IP-uri sursă unice
4. port_diversity      - Diversitatea porturilor
5. protocol_variety    - Varietatea de protocoale
```

### Training Process

```python
# Antrenare automată din date istorice
ml_detector.train_from_historical_data(db)

# Predicție
result = ml_detector.predict_ddos(traffic_data)
# Returns: is_ddos, score, confidence
```

### Tuning ML Model

```bash
# Edit parametri în config
"ml_threshold": -0.5          # -1 to 1 (lower = more sensitive)
"contamination": 0.1          # Percentage expected to be anomalies
```

### ML Monitoring

```bash
# Check model training
tail -f /var/log/asa_ddos_remediation.log | grep "ML"

# Retrain model
python3 -c "
from asa_ddos_complete import MLDDOSDetector, DatabaseManager
ml = MLDDOSDetector()
ml.train_from_historical_data(DatabaseManager())
"
```

---

## Whitelist Management

### Adaugă IP via Dashboard

1. Deschide Dashboard
2. Click "Whitelist" tab
3. Click "+ Add IP to Whitelist"
4. Fill IP + Description
5. Submit

### Adaugă IP via CLI

```bash
python3 -c "
from asa_ddos_complete import DatabaseManager
db = DatabaseManager()
db.add_to_whitelist('192.168.1.50', 'Office IP', 'admin')
"
```

### Adaugă IP via SQLite

```bash
sqlite3 /var/lib/asa-ddos/alerts.db

INSERT INTO whitelist (ip_address, description, added_by)
VALUES ('192.168.1.50', 'Office Network', 'admin');
```

### Bulk Import Whitelist

```bash
# Create CSV: whitelist.csv
# Format: ip_address,description

python3 -c "
import csv
from asa_ddos_complete import DatabaseManager

db = DatabaseManager()
with open('whitelist.csv') as f:
    for row in csv.DictReader(f):
        db.add_to_whitelist(row['ip_address'], row['description'])
"
```

### List Whitelisted IPs

```bash
sqlite3 /var/lib/asa-ddos/alerts.db \
  "SELECT ip_address, description, added_date FROM whitelist;"
```

---

## Troubleshooting

### Serviciu nu pornește

```bash
# Check erori
sudo systemctl status asa-ddos-syslog -l

# Check logs
journalctl -u asa-ddos-syslog -n 50

# Check permissions
ls -la /var/lib/asa-ddos/
ls -la /opt/asa-ddos-remediation/
```

### Nu se conectează la ASA

```bash
# Test SSH connectivity
ssh -v admin@192.168.1.1

# Check ASA config
# asa# show run | include logging
# asa# show run | include ssh

# Verify credentials
python3 -c "
from asa_ddos_complete import ASAController
asa = ASAController()
print('Connected!' if asa.connect() else 'Failed!')
"
```

### Alerts nu ajung pe Slack

```bash
# Check webhook URL
curl -X POST https://hooks.slack.com/services/YOUR/WEBHOOK/URL \
  -H 'Content-Type: application/json' \
  -d '{"text":"Test message"}'

# Check logs
grep "Slack" /var/log/asa_ddos_remediation.log
```

### Email alerts nu se trimit

```bash
# Test SMTP
python3 -c "
import smtplib
try:
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login('your.email@gmail.com', 'app_password')
    print('SMTP OK!')
except Exception as e:
    print(f'Error: {e}')
"

# Check Gmail app password
# https://myaccount.google.com/apppasswords
```

### Database locked

```bash
# Restart database process
sudo systemctl restart asa-ddos-syslog

# Check locks
lsof /var/lib/asa-ddos/alerts.db

# Backup și reset
cp /var/lib/asa-ddos/alerts.db /var/lib/asa-ddos/alerts.db.bak
rm /var/lib/asa-ddos/alerts.db
# Database will be recreated automatically
```

### Performance Issues

```bash
# Monitor resource usage
watch -n 1 'ps aux | grep asa_ddos'

# Check database size
du -sh /var/lib/asa-ddos/alerts.db

# Cleanup old alerts (keep 30 days)
sqlite3 /var/lib/asa-ddos/alerts.db "
DELETE FROM alerts WHERE timestamp < datetime('now', '-30 days');
VACUUM;
"
```

### ML Model Issues

```bash
# Check model file
ls -la /var/lib/asa-ddos/ml_model.pkl

# Retrain from scratch
python3 << 'EOF'
from asa_ddos_complete import *
import os

# Remove old model
if os.path.exists('/var/lib/asa-ddos/ml_model.pkl'):
    os.remove('/var/lib/asa-ddos/ml_model.pkl')

# Retrain
ml = MLDDOSDetector()
ml.train_from_historical_data(DatabaseManager())
print("Model retrained!")
EOF
```

---

## Performance Optimization

### Database Maintenance

```bash
# Weekly maintenance
sqlite3 /var/lib/asa-ddos/alerts.db << 'EOF'
-- Clean old data
DELETE FROM alerts WHERE timestamp < datetime('now', '-90 days');
DELETE FROM ml_training_data WHERE timestamp < datetime('now', '-180 days');

-- Optimize
VACUUM;
ANALYZE;
EOF
```

### Log Rotation

```bash
# Already configured by install
# Logs rotate daily, keep 30 days

# Manual rotation
logrotate -f /etc/logrotate.d/asa-ddos
```

### Nginx Optimization

```bash
# /etc/nginx/sites-available/asa-ddos
worker_processes auto;
worker_connections 1024;

# Add caching
proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=dashboard:10m;
proxy_cache dashboard;
```

---

## Security Best Practices

### 1. Protect Credentials
- Never commit passwords în git
- Use environment variables
- Restrict /etc/asa-ddos/config.json permissions

```bash
sudo chmod 600 /etc/asa-ddos/config.json
```

### 2. Network Security
- Restrict port 5000/8080 cu firewall
- Use Nginx SSL certificates

```bash
# Self-signed cert
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/nginx/ssl/private.key \
  -out /etc/nginx/ssl/certificate.crt
```

### 3. Audit Logging
- Check who made whitelist changes
- Track unblock actions
- Review database queries

```bash
sqlite3 /var/lib/asa-ddos/alerts.db \
  "SELECT * FROM blocked_ips ORDER BY timestamp DESC LIMIT 100;"
```

### 4. Backup Strategy
- Daily backup database
- Keep 30-day retention

```bash
# Add to crontab
0 2 * * * cp /var/lib/asa-ddos/alerts.db /backup/asa-ddos-$(date +\%Y\%m\%d).db
```

---

## Support & Maintenance

### Regular Tasks

- **Daily**: Monitor dashboard, check alerts
- **Weekly**: Review blocked IPs, update whitelist
- **Monthly**: Analyze statistics, retrain ML model
- **Quarterly**: Update packages, backup database

### Useful Commands

```bash
# Service management
sudo systemctl restart asa-ddos-*
sudo systemctl stop asa-ddos-syslog

# Log analysis
tail -n 100 /var/log/asa_ddos_remediation.log
grep -i "error" /var/log/asa_ddos_remediation.log

# Database export
sqlite3 /var/lib/asa-ddos/alerts.db ".dump" > backup.sql

# Configuration backup
sudo cp -r /etc/asa-ddos /backup/asa-ddos-config
```

---

## Changelog

### v1.0 (2026-09-27)
- Initial release
- Core DDOS detection and blocking
- Slack/Email notifications
- ML anomaly detection
- Web dashboard
- Whitelist management

---

**Support**: ITSec@ernu.md | ERNU.EU
