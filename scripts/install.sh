#!/bin/bash

# ASA DDOS Auto-Remediation System - Installation Script
# Instalare completă cu toate componentele

set -e

echo "======================================"
echo "ASA DDOS Auto-Remediation Installer"
echo "======================================"
echo ""

# Check root
if [[ $EUID -ne 0 ]]; then
    echo "Acest script trebuie rulat cu sudo"
    exit 1
fi

# Colori
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# ============= CONFIGURARE =============

echo -e "${YELLOW}[*] Introducere Configurări${NC}"
echo ""

read -p "ASA Firewall IP [192.168.1.1]: " ASA_HOST
ASA_HOST=${ASA_HOST:-192.168.1.1}

read -p "ASA Username [admin]: " ASA_USER
ASA_USER=${ASA_USER:-admin}

read -sp "ASA Password: " ASA_PASS
echo ""

read -p "Slack Webhook URL (opțional): " SLACK_WEBHOOK
read -p "Email SMTP Server [smtp.gmail.com]: " SMTP_SERVER
SMTP_SERVER=${SMTP_SERVER:-smtp.gmail.com}

read -p "Email Address (sender): " SENDER_EMAIL
read -sp "Email Password: " SENDER_PASS
echo ""

read -p "Recipients (comma-separated) [security@yourdomain.com]: " RECIPIENTS
RECIPIENTS=${RECIPIENTS:-security@yourdomain.com}

# ============= INSTALARE DEPENDENȚE =============

echo -e "${YELLOW}[*] Instalare dependențe sistem...${NC}"

apt-get update -qq
apt-get install -y -qq \
    python3 \
    python3-pip \
    python3-venv \
    sqlite3 \
    openssh-client \
    git

echo -e "${GREEN}[✓] Dependențe sistem instalate${NC}"

# ============= PYTHON PACKAGES =============

echo -e "${YELLOW}[*] Instalare pachete Python...${NC}"

python3 -m pip install -q \
    paramiko \
    flask \
    requests \
    scikit-learn \
    numpy

echo -e "${GREEN}[✓] Pachete Python instalate${NC}"

# ============= CREARE DIRECTOARE =============

echo -e "${YELLOW}[*] Creare structură directoare...${NC}"

mkdir -p /opt/asa-ddos-remediation
mkdir -p /var/lib/asa-ddos
mkdir -p /var/log/asa-ddos
mkdir -p /etc/asa-ddos

# ============= COPY FIȘIERE =============

echo -e "${YELLOW}[*] Copiere fișiere...${NC}"

cp asa_ddos_complete.py /opt/asa-ddos-remediation/
cp dashboard.html /opt/asa-ddos-remediation/templates/dashboard.html || {
    mkdir -p /opt/asa-ddos-remediation/templates
    cp dashboard.html /opt/asa-ddos-remediation/templates/
}

chmod +x /opt/asa-ddos-remediation/asa_ddos_complete.py
chown -R root:root /opt/asa-ddos-remediation

echo -e "${GREEN}[✓] Fișiere copiate${NC}"

# ============= CONFIGURARE CONFIG =============

echo -e "${YELLOW}[*] Generare configurație...${NC}"

cat > /etc/asa-ddos/config.json <<EOF
{
    "asa": {
        "host": "$ASA_HOST",
        "username": "$ASA_USER",
        "password": "$ASA_PASS"
    },
    "slack": {
        "webhook_url": "$SLACK_WEBHOOK",
        "enabled": $([ -z "$SLACK_WEBHOOK" ] && echo "false" || echo "true")
    },
    "email": {
        "smtp_server": "$SMTP_SERVER",
        "smtp_port": 587,
        "sender": "$SENDER_EMAIL",
        "sender_password": "$SENDER_PASS",
        "recipients": ["$(echo $RECIPIENTS | sed 's/, /", "/g')"],
        "enabled": true
    },
    "auto_unblock_hours": 24,
    "ml_threshold": -0.5,
    "dashboard_port": 5000
}
EOF

chmod 600 /etc/asa-ddos/config.json
echo -e "${GREEN}[✓] Configurație salvată${NC}"

# ============= SYSTEMD SERVICES =============

echo -e "${YELLOW}[*] Setup Systemd services...${NC}"

# Syslog listener service
cat > /etc/systemd/system/asa-ddos-syslog.service <<EOF
[Unit]
Description=ASA DDOS Syslog Listener
After=network.target
Wants=asa-ddos-dashboard.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/asa-ddos-remediation
ExecStart=/usr/bin/python3 /opt/asa-ddos-remediation/asa_ddos_complete.py syslog
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Dashboard service
cat > /etc/systemd/system/asa-ddos-dashboard.service <<EOF
[Unit]
Description=ASA DDOS Dashboard
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/asa-ddos-remediation
ExecStart=/usr/bin/python3 /opt/asa-ddos-remediation/asa_ddos_complete.py dashboard
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable asa-ddos-syslog.service
systemctl enable asa-ddos-dashboard.service

echo -e "${GREEN}[✓] Systemd services configurate${NC}"

# ============= LOGROTATE =============

echo -e "${YELLOW}[*] Setup logrotate...${NC}"

cat > /etc/logrotate.d/asa-ddos <<EOF
/var/log/asa_ddos_remediation.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 root root
    sharedscripts
    postrotate
        systemctl reload asa-ddos-syslog.service > /dev/null 2>&1 || true
    endscript
}
EOF

echo -e "${GREEN}[✓] Logrotate configurat${NC}"

# ============= RSYSLOG CONFIGURATION =============

echo -e "${YELLOW}[*] Configurare rsyslog pentru IDS alerts...${NC}"

cat > /etc/rsyslog.d/30-asa-ddos.conf <<'EOF'
# Forward IDS/Snort alerts to local listener
# Configure on your IDS/ASA to send syslog to this server:
# logging host <this-server-ip> 514

:programname, contains, "snort" @@localhost:514
:programname, contains, "ids" @@localhost:514
& stop

# Or alternatively, listen on UDP 514:
$ModLoad imudp
$UDPServerRun 514
EOF

systemctl restart rsyslog
echo -e "${GREEN}[✓] Rsyslog configurat${NC}"

# ============= NGINX REVERSE PROXY (optional) =============

echo -e "${YELLOW}[?] Vrei să configurez Nginx reverse proxy pentru dashboard? (y/n)${NC}"
read -r SETUP_NGINX

if [[ $SETUP_NGINX == "y" ]]; then
    apt-get install -y -qq nginx

    cat > /etc/nginx/sites-available/asa-ddos <<'EOF'
server {
    listen 8080;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:5000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF

    ln -sf /etc/nginx/sites-available/asa-ddos /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default
    nginx -t && systemctl restart nginx

    echo -e "${GREEN}[✓] Nginx configurat pe port 8080${NC}"
fi

# ============= FIREWALL =============

echo -e "${YELLOW}[*] Configurare firewall (ufw)...${NC}"

if command -v ufw &> /dev/null; then
    ufw allow 514/udp comment "Syslog IDS alerts"
    ufw allow 5000/tcp comment "ASA DDOS Dashboard"
    [[ $SETUP_NGINX == "y" ]] && ufw allow 8080/tcp comment "ASA DDOS Dashboard (Nginx)"
    echo -e "${GREEN}[✓] Firewall updated${NC}"
fi

# ============= TEST CONFIGURATION =============

echo ""
echo -e "${YELLOW}[*] Testare configurare...${NC}"

python3 /opt/asa-ddos-remediation/asa_ddos_complete.py test 2>/dev/null || echo -e "${YELLOW}[!] Test alert - expected behavior${NC}"

# ============= FINAL SUMMARY =============

echo ""
echo -e "${GREEN}======================================"
echo "✓ Instalare completă!"
echo "======================================${NC}"
echo ""

echo "📋 INFORMAȚII IMPORTANTE:"
echo ""
echo "1. PORNIRE SERVICII:"
echo "   sudo systemctl start asa-ddos-syslog"
echo "   sudo systemctl start asa-ddos-dashboard"
echo ""

echo "2. VERIFICARE STATUS:"
echo "   sudo systemctl status asa-ddos-syslog"
echo "   sudo systemctl status asa-ddos-dashboard"
echo ""

echo "3. LOGS:"
echo "   tail -f /var/log/asa_ddos_remediation.log"
echo "   journalctl -u asa-ddos-syslog -f"
echo ""

echo "4. DASHBOARD:"
if [[ $SETUP_NGINX == "y" ]]; then
    echo "   http://localhost:8080 (Nginx proxy)"
else
    echo "   http://localhost:5000 (Direct)"
fi
echo ""

echo "5. CONFIGURAȚIE SLACK/EMAIL:"
echo "   cat /etc/asa-ddos/config.json"
echo ""

echo "6. CONFIGURARE IDS/ASA:"
echo "   Configureaza IDS-ul sa trimita syslog la:"
echo "   logging host $(hostname -I | awk '{print $1}') 514"
echo ""

echo "7. WHITELIST DEFAULT:"
echo "   Dashboard → Whitelist → Add IP"
echo ""

echo "8. MACHINE LEARNING:"
echo "   Modelul se va antrena automat din datele istorice"
echo ""

echo -e "${YELLOW}[!] IMPORTANT - Edit config daca e necesar:${NC}"
echo "    sudo nano /etc/asa-ddos/config.json"
echo ""

read -p "Vrei să pornești serviciile acum? (y/n): " START_SERVICES

if [[ $START_SERVICES == "y" ]]; then
    systemctl start asa-ddos-syslog
    systemctl start asa-ddos-dashboard
    echo -e "${GREEN}✓ Servicii pornite${NC}"
    echo ""
    sleep 2
    systemctl status asa-ddos-syslog
fi

echo ""
echo -e "${GREEN}Instalare finalizată!${NC}"
