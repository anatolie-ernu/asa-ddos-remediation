# ASA DDOS Auto-Remediation - Quick Start Guide

## 📦 Instalare Rapidă (5 minute)

### 1. Download și Instalare

```bash
# Clone files
cd /tmp
wget https://your-repo/asa_ddos_complete.py
wget https://your-repo/dashboard.html
wget https://your-repo/install.sh
chmod +x install.sh

# Rulează installer
sudo ./install.sh
```

### 2. Configurare Inițială

```bash
# Editează configurație
sudo nano /etc/asa-ddos/config.json

# Mandatory fields:
# - asa.host: IP ASA firewall (ex: 192.168.1.1)
# - asa.username: Admin user pe ASA
# - asa.password: Parola ASA
# - slack.webhook_url: (optional) Slack webhook
# - email.sender: Email address sender
# - email.sender_password: Email password (app password for Gmail)
```

### 3. Pornire Servicii

```bash
sudo systemctl start asa-ddos-syslog
sudo systemctl start asa-ddos-dashboard

# Verifica status
sudo systemctl status asa-ddos-syslog
sudo systemctl status asa-ddos-dashboard
```

### 4. Verificare Instalare

```bash
# Rulează test suite
sudo bash test_suite.sh
```

---

## 🔧 Configurare ASA Firewall (2 minute)

```bash
# SSH pe ASA
ssh admin@192.168.1.1

# Enable SSH
asa(config)# ssh 0.0.0.0 0.0.0.0 inside
asa(config)# ssh timeout 30

# Configure syslog output
asa(config)# logging enable
asa(config)# logging timestamp
asa(config)# logging host inside YOUR_SERVER_IP 514
asa(config)# logging trap informational

# Enable threat detection
asa(config)# threat-detection basic-threat
asa(config)# threat-detection statistics host

# Save
asa(config)# write mem
asa(config)# exit
```

---

## 📊 Acces Dashboard

```
URL: http://YOUR_SERVER_IP:5000
- Default port: 5000
- Via Nginx proxy: http://YOUR_SERVER_IP:8080
```

### Funcționalități:
- 🔒 Listeaza IPs blocate
- ✅ Manage whitelist
- 📋 Vezi recent alerts
- 📈 Statistici real-time
- 🕐 Auto-unblock countdown

---

## 💬 Setup Slack Notifications (1 minute)

### 1. Create Slack App

- Go to https://api.slack.com/apps
- Click "Create New App" → "From scratch"
- Name: "ASA DDOS Alerts"
- Go to "Incoming Webhooks" → "Add New Webhook"
- Copy the Webhook URL

### 2. Add to Config

```bash
sudo nano /etc/asa-ddos/config.json

# Edit:
"slack": {
    "webhook_url": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
    "enabled": true
}
```

### 3. Restart Service

```bash
sudo systemctl restart asa-ddos-syslog
```

---

## 📧 Setup Email Notifications (Gmail)

### 1. Generate App Password

- Go to https://myaccount.google.com/apppasswords
- Select "Mail" and "Windows Computer"
- Copy the generated 16-character password

### 2. Add to Config

```bash
sudo nano /etc/asa-ddos/config.json

# Edit:
"email": {
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "sender": "your.email@gmail.com",
    "sender_password": "xxxx xxxx xxxx xxxx",
    "recipients": [
        "security@yourdomain.com"
    ],
    "enabled": true
}
```

### 3. Restart Service

```bash
sudo systemctl restart asa-ddos-syslog
```

---

## 🤖 Machine Learning Setup

ML Detection se activeaza automat. Features folosite:

- Packets per second
- Bytes per second
- Unique source IPs
- Port diversity
- Protocol variety

### Tuning ML Sensitivity

```bash
sudo nano /etc/asa-ddos/config.json

# Lower = More Sensitive (catches more DDoS)
"ml_threshold": -0.5

# Adjust contamination % (expected anomalies)
"contamination": 0.1
```

---

## ✅ Whitelist Management

### Via Dashboard

1. Open http://YOUR_SERVER:5000
2. Click "Whitelist" tab
3. Click "+ Add IP to Whitelist"
4. Enter IP + Description
5. Submit

### Via CLI

```bash
python3 << 'EOF'
import sys
sys.path.insert(0, '/opt/asa-ddos-remediation')
from asa_ddos_complete import DatabaseManager

db = DatabaseManager()
db.add_to_whitelist('192.168.1.50', 'Office Network', 'admin')
print("Added to whitelist")
EOF
```

### Bulk Import

```bash
# Create whitelist.txt
cat > /tmp/whitelist.txt << 'EOF'
192.168.1.0/24|Office Network
10.0.0.0/8|Partner Network
203.0.113.0/24|Trusted Customer
EOF

# Import
python3 << 'EOF'
import sys
sys.path.insert(0, '/opt/asa-ddos-remediation')
from asa_ddos_complete import DatabaseManager

db = DatabaseManager()
with open('/tmp/whitelist.txt') as f:
    for line in f:
        ip, desc = line.strip().split('|')
        db.add_to_whitelist(ip, desc, 'admin')
print("Imported")
EOF
```

---

## 📋 Common Commands

### Monitorizare Logs

```bash
# Real-time logs
tail -f /var/log/asa_ddos_remediation.log

# Filtrare DDOS alerts
grep "DDOS" /var/log/asa_ddos_remediation.log

# Filtrare blocked IPs
grep "BLOCKED" /var/log/asa_ddos_remediation.log

# Systemd journal
journalctl -u asa-ddos-syslog -f
```

### Database Queries

```bash
# Connect la database
sqlite3 /var/lib/asa-ddos/alerts.db

# List current blocks
SELECT ip_address, reason, timestamp FROM blocked_ips WHERE status='active';

# List whitelisted
SELECT ip_address, description FROM whitelist;

# Recent alerts
SELECT * FROM alerts ORDER BY timestamp DESC LIMIT 20;

# Exit
.quit
```

### Service Management

```bash
# Start services
sudo systemctl start asa-ddos-syslog
sudo systemctl start asa-ddos-dashboard

# Stop services
sudo systemctl stop asa-ddos-syslog

# Restart
sudo systemctl restart asa-ddos-syslog

# Status
sudo systemctl status asa-ddos-syslog

# View logs
journalctl -u asa-ddos-syslog -n 50
```

---

## 🧪 Test Alert

Simulează un alert DDOS pentru testare:

```bash
# Method 1: Python
sudo python3 /opt/asa-ddos-remediation/asa_ddos_complete.py test

# Method 2: Syslog
echo "<134>IDS Alert: [**] DDoS Attack {TCP} 203.0.113.50:54321 -> 192.168.1.100:80" | \
  nc -w 0 localhost 514
```

---

## 🔍 Troubleshooting

### Service nu pornește

```bash
# Check erori
sudo systemctl status asa-ddos-syslog -l

# Check logs
journalctl -u asa-ddos-syslog -n 50

# Test Python script direct
sudo python3 /opt/asa-ddos-remediation/asa_ddos_complete.py test
```

### Nu se conectează la ASA

```bash
# Test SSH connection
ssh -v admin@192.168.1.1

# Check config
cat /etc/asa-ddos/config.json | grep -A 3 '"asa"'

# Test connection
python3 << 'EOF'
import sys
sys.path.insert(0, '/opt/asa-ddos-remediation')
from asa_ddos_complete import ASAController
asa = ASAController()
if asa.connect():
    print("Connected!")
else:
    print("Connection failed!")
EOF
```

### Alerts nu ajung pe Slack

```bash
# Test webhook
curl -X POST 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL' \
  -H 'Content-Type: application/json' \
  -d '{"text":"Test message"}'

# Check config
cat /etc/asa-ddos/config.json | grep -A 3 '"slack"'

# Check logs
grep "Slack" /var/log/asa_ddos_remediation.log
```

### Email alerts nu se trimit

```bash
# Test SMTP
python3 << 'EOF'
import smtplib
try:
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login('your.email@gmail.com', 'xxxx xxxx xxxx xxxx')
    print("SMTP OK!")
except Exception as e:
    print(f"Error: {e}")
EOF

# Check config
cat /etc/asa-ddos/config.json | grep -A 5 '"email"'
```

---

## 📈 API Endpoints

```bash
# Get blocked IPs
curl http://localhost:5000/api/blocked-ips

# Get whitelist
curl http://localhost:5000/api/whitelist

# Get recent alerts
curl http://localhost:5000/api/alerts

# Get statistics
curl http://localhost:5000/api/stats

# Unblock IP
curl -X POST http://localhost:5000/api/unblock-ip/203.0.113.50

# Add to whitelist
curl -X POST http://localhost:5000/api/whitelist \
  -H "Content-Type: application/json" \
  -d '{"ip":"192.168.1.50","description":"Office"}'
```

---

## 📞 Support & Issues

### Logs Location
- Main: `/var/log/asa_ddos_remediation.log`
- Systemd: `journalctl -u asa-ddos-syslog`

### Configuration
- Location: `/etc/asa-ddos/config.json`

### Database
- Location: `/var/lib/asa-ddos/alerts.db`
- Backup: `/var/backups/asa-ddos/`

### Documentation
- Full README: See `README.md`
- Example config: See `config.example.json`

---

## ✅ Checklist Post-Instalare

- [ ] Instalare completă rulată
- [ ] ASA firewall configurată pentru syslog
- [ ] Servicii pornite și active
- [ ] Dashboard accesibil
- [ ] Slack webhook adăugat (opțional)
- [ ] Email configuration testat (opțional)
- [ ] Test alert simulat
- [ ] IPs whitelisted-uri adăugate
- [ ] Backups configurate
- [ ] Monitoring activated

---

## 🚀 Next Steps

1. **Configure Email Alerts** - Setup Gmail app password
2. **Setup Slack Notifications** - Create Slack app + webhook
3. **Add Whitelist IPs** - Whitelist office/partner networks
4. **Monitor Dashboard** - Check real-time statistics
5. **Review Logs** - Understand system behavior
6. **Schedule Backups** - Configure daily database backups
7. **Train ML Model** - Collect 100+ training samples
8. **Fine-tune Thresholds** - Adjust sensitivity as needed

---

**Version**: 1.0  
**Last Updated**: 2026-09-27  
**Maintainer**: ERNU.EU - ITSec Team
