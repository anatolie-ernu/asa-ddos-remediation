# ASA DDOS Auto-Remediation System

🛡️ **Enterprise-Grade Automated DDOS Protection for Cisco ASA Firewalls**

## Overview

Sistem complet de detectare și blocare automată a atacurilor DDOS pe firewalluri Cisco ASA cu notificări Slack/Email, Machine Learning detection, și dashboard web de management.

**Status**: Production Ready ✅

## Features

- 🚀 **Real-time DDOS Detection** - Procesare instantanee a alertelor IDS
- 🔒 **Automatic IP Blocking** - Reguli ASA aplicate în <2 secunde
- 🤖 **Machine Learning** - Isolation Forest anomaly detection cu confidence scoring
- 💬 **Multi-Channel Alerts** - Slack + Email HTML templates
- 📊 **Web Dashboard** - Real-time monitoring și control manual
- ✅ **Smart Whitelist** - Trusted IP management cu API
- 🗄️ **Persistent Storage** - SQLite database cu 90-day retention
- 🔄 **Auto-Unblock** - Configurable timeout (default 24h)

## Quick Start

```bash
# 1. Install
sudo chmod +x scripts/install.sh
sudo ./scripts/install.sh

# 2. Configure
sudo nano /etc/asa-ddos/config.json

# 3. Start
sudo systemctl start asa-ddos-syslog
sudo systemctl start asa-ddos-dashboard

# 4. Access Dashboard
http://localhost:5000
```

## Architecture

```
IDS Alert (Syslog) → Parser → ML Detection → ASA Block
                              ↓
                        Slack + Email
                              ↓
                          Dashboard
```

## Components

| Component | Size | Description |
|-----------|------|-------------|
| Core Engine | 27KB | Python - ASA control, IDS parsing, ML |
| Dashboard | 22KB | HTML/CSS/JS - Real-time web UI |
| Installer | 8.6KB | Bash - Automated deployment |
| Tests | 11KB | Bash - 12 validation tests |

## Documentation

- [QUICK_START.md](docs/QUICK_START.md) - 5-minute setup guide
- [README.md](docs/README.md) - Full documentation (200+ pages)
- [DEPLOYMENT_SUMMARY.txt](docs/DEPLOYMENT_SUMMARY.txt) - Complete overview

## Configuration

```json
{
  "asa": {
    "host": "192.168.1.1",
    "username": "admin",
    "password": "password"
  },
  "slack": {
    "webhook_url": "https://hooks.slack.com/services/YOUR/WEBHOOK",
    "enabled": true
  },
  "email": {
    "smtp_server": "smtp.gmail.com",
    "sender": "alerts@yourdomain.com",
    "recipients": ["security@yourdomain.com"],
    "enabled": true
  }
}
```

See [config/config.example.json](config/config.example.json) for all options.

## Performance

- Alert Processing: <1s
- IP Blocking: <2s
- Dashboard: <500ms
- Memory: ~100MB
- CPU: <5% (idle)

## Requirements

- Ubuntu 20.04+ / Debian 11+
- Python 3.8+
- SSH access to ASA
- Port 514 (UDP) for syslog
- Port 5000/8080 for dashboard

## Installation

### Automated (Recommended)

```bash
git clone https://github.com/anatolie-ernu/asa-ddos-remediation
cd asa-ddos-remediation
sudo ./scripts/install.sh
```

### Manual

1. Copy `src/asa_ddos_complete.py` to `/opt/asa-ddos-remediation/`
2. Copy `web/templates/dashboard.html` to `/opt/asa-ddos-remediation/templates/`
3. Install Python dependencies: `pip install -r requirements.txt`
4. Create systemd services
5. Configure `/etc/asa-ddos/config.json`

## API Endpoints

```bash
GET  /api/blocked-ips              # List current blocks
POST /api/unblock-ip/<ip>          # Manual unblock
GET  /api/whitelist                # List whitelisted IPs
POST /api/whitelist                # Add to whitelist
GET  /api/alerts                   # Recent alerts
GET  /api/stats                    # Statistics
```

## Database Schema

- `blocked_ips` - Tracked IP blocks with auto-unblock timer
- `whitelist` - Trusted IPs
- `alerts` - Alert history (90-day retention)
- `ml_training_data` - ML model training dataset

## Machine Learning

**Algorithm**: Isolation Forest  
**Features**:
- Packets per second (PPS)
- Bytes per second (BPS)
- Unique source IPs
- Port diversity
- Protocol variety

**Auto-training**: Daily (configurable)  
**Threshold**: -0.5 (adjustable)  
**Confidence**: 0-1 scale

## Monitoring

```bash
# Logs
tail -f /var/log/asa_ddos_remediation.log

# Systemd
journalctl -u asa-ddos-syslog -f

# Database
sqlite3 /var/lib/asa-ddos/alerts.db "SELECT * FROM blocked_ips;"
```

## Testing

```bash
sudo ./tests/test_suite.sh
```

Tests:
- File integrity
- Python dependencies
- Systemd services
- Database structure
- Configuration validity
- Connectivity
- Functionality

## Troubleshooting

### Service down
```bash
sudo systemctl status asa-ddos-syslog -l
journalctl -u asa-ddos-syslog -n 50
```

### ASA connection failed
```bash
python3 -c "
import sys; sys.path.insert(0, '/opt/asa-ddos-remediation')
from asa_ddos_complete import ASAController
asa = ASAController()
print('Connected!' if asa.connect() else 'Failed!')
"
```

### Slack alerts not sending
```bash
grep "Slack" /var/log/asa_ddos_remediation.log
```

## Support

📧 Email: ITSec@ernu.md  
🌐 Website: https://ernu.md  
📱 GitHub: https://github.com/anatolie-ernu/asa-ddos-remediation

## License

MIT License - See [LICENSE](LICENSE) file

## Author

**Anatolie Ernu**  
IT & Security Consultant  
Head of IT @ ARCOM (Moldova)  
ERNU.EU

---

**Version**: 1.0  
**Last Updated**: September 27, 2026  
**Status**: Production Ready ✅
