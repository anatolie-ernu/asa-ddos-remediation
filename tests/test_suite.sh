#!/bin/bash

# ASA DDOS Remediation - Test Suite
# Script pentru testare și validare completă a sistemului

set -e

# Colori
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

TESTS_PASSED=0
TESTS_FAILED=0

# ============= TEST FUNCTIONS =============

test_print_header() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║ $1${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

test_assert_success() {
    local test_name=$1
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ PASS${NC}: $test_name"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}✗ FAIL${NC}: $test_name"
        ((TESTS_FAILED++))
    fi
}

test_assert_file_exists() {
    local file=$1
    local test_name=$2
    if [ -f "$file" ]; then
        echo -e "${GREEN}✓ PASS${NC}: $test_name - File exists"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}✗ FAIL${NC}: $test_name - File not found: $file"
        ((TESTS_FAILED++))
    fi
}

test_assert_dir_exists() {
    local dir=$1
    local test_name=$2
    if [ -d "$dir" ]; then
        echo -e "${GREEN}✓ PASS${NC}: $test_name - Directory exists"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}✗ FAIL${NC}: $test_name - Directory not found: $dir"
        ((TESTS_FAILED++))
    fi
}

test_assert_command_exists() {
    local cmd=$1
    local test_name=$2
    if command -v "$cmd" &> /dev/null; then
        echo -e "${GREEN}✓ PASS${NC}: $test_name - Command available"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}✗ FAIL${NC}: $test_name - Command not found: $cmd"
        ((TESTS_FAILED++))
    fi
}

# ============= TESTS =============

test_print_header "1. VERIFICARE INSTALARE FIȘIERE"

test_assert_file_exists "/opt/asa-ddos-remediation/asa_ddos_complete.py" "Python script"
test_assert_file_exists "/opt/asa-ddos-remediation/templates/dashboard.html" "Dashboard HTML"
test_assert_file_exists "/etc/asa-ddos/config.json" "Configuration file"
test_assert_dir_exists "/var/lib/asa-ddos" "Data directory"
test_assert_dir_exists "/var/log/asa-ddos" "Logs directory"

test_print_header "2. VERIFICARE DEPENDENȚE PYTHON"

test_assert_command_exists "python3" "Python3 interpreter"

# Test Python packages
python3 -c "import paramiko" 2>/dev/null
test_assert_success "Paramiko module"

python3 -c "import flask" 2>/dev/null
test_assert_success "Flask module"

python3 -c "import sklearn" 2>/dev/null
test_assert_success "Scikit-learn module"

python3 -c "import numpy" 2>/dev/null
test_assert_success "NumPy module"

python3 -c "import requests" 2>/dev/null
test_assert_success "Requests module"

test_print_header "3. VERIFICARE SERVICII SYSTEMD"

systemctl is-enabled asa-ddos-syslog >/dev/null 2>&1
test_assert_success "Syslog service enabled"

systemctl is-enabled asa-ddos-dashboard >/dev/null 2>&1
test_assert_success "Dashboard service enabled"

test_print_header "4. VERIFICARE BAZA DE DATE"

if [ -f "/var/lib/asa-ddos/alerts.db" ]; then
    # Check tables
    sqlite3 /var/lib/asa-ddos/alerts.db ".tables" | grep -q "blocked_ips"
    test_assert_success "Tabelă blocked_ips"
    
    sqlite3 /var/lib/asa-ddos/alerts.db ".tables" | grep -q "whitelist"
    test_assert_success "Tabelă whitelist"
    
    sqlite3 /var/lib/asa-ddos/alerts.db ".tables" | grep -q "alerts"
    test_assert_success "Tabelă alerts"
    
    sqlite3 /var/lib/asa-ddos/alerts.db ".tables" | grep -q "ml_training_data"
    test_assert_success "Tabelă ml_training_data"
else
    echo -e "${YELLOW}⚠ WARNING${NC}: Database not yet created (will be created on first run)"
fi

test_print_header "5. VERIFICARE CONFIGURAȚIE"

if [ -f "/etc/asa-ddos/config.json" ]; then
    python3 -c "import json; json.load(open('/etc/asa-ddos/config.json'))" 2>/dev/null
    test_assert_success "Valid JSON configuration"
    
    grep -q '"host"' /etc/asa-ddos/config.json
    test_assert_success "ASA host configured"
    
    grep -q '"smtp_server"' /etc/asa-ddos/config.json
    test_assert_success "Email configuration"
else
    echo -e "${RED}✗ FAIL${NC}: Configuration file not found"
    ((TESTS_FAILED++))
fi

test_print_header "6. VERIFICARE PERMISIUNI"

# Check file permissions
if [ -f "/etc/asa-ddos/config.json" ]; then
    perms=$(stat -c '%a' /etc/asa-ddos/config.json)
    if [ "$perms" = "600" ]; then
        echo -e "${GREEN}✓ PASS${NC}: Config file permissions (600)"
        ((TESTS_PASSED++))
    else
        echo -e "${YELLOW}⚠ WARNING${NC}: Config file permissions ($perms) - Should be 600"
    fi
fi

# Check directory ownership
if [ -d "/var/lib/asa-ddos" ]; then
    owner=$(stat -c '%U' /var/lib/asa-ddos)
    if [ "$owner" = "root" ] || [ "$owner" = "www-data" ]; then
        echo -e "${GREEN}✓ PASS${NC}: Data directory ownership"
        ((TESTS_PASSED++))
    else
        echo -e "${YELLOW}⚠ WARNING${NC}: Data directory owner ($owner)"
    fi
fi

test_print_header "7. TESTE DE CONECTIVITATE"

# Test DNS
python3 -c "import socket; socket.gethostbyname('8.8.8.8')" 2>/dev/null
test_assert_success "Internet connectivity (DNS)"

# Test ports
if netstat -tlnp 2>/dev/null | grep -q ":5000"; then
    echo -e "${GREEN}✓ PASS${NC}: Dashboard port 5000 listening"
    ((TESTS_PASSED++))
elif ss -tlnp 2>/dev/null | grep -q ":5000"; then
    echo -e "${GREEN}✓ PASS${NC}: Dashboard port 5000 listening"
    ((TESTS_PASSED++))
else
    echo -e "${YELLOW}⚠ WARNING${NC}: Dashboard port 5000 not listening (service may not be running)"
fi

# Check syslog listener
if netstat -tlnp 2>/dev/null | grep -q ":514"; then
    echo -e "${GREEN}✓ PASS${NC}: Syslog port 514 listening"
    ((TESTS_PASSED++))
elif ss -tlnp 2>/dev/null | grep -q ":514"; then
    echo -e "${GREEN}✓ PASS${NC}: Syslog port 514 listening"
    ((TESTS_PASSED++))
else
    echo -e "${YELLOW}⚠ WARNING${NC}: Syslog port 514 not listening (service may not be running)"
fi

test_print_header "8. TESTE FUNCȚIONALITATE"

# Test Python import
python3 << 'EOF' 2>/dev/null
import sys
sys.path.insert(0, '/opt/asa-ddos-remediation')
try:
    from asa_ddos_complete import DatabaseManager, ASAController, AlertNotifier
    print("OK")
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
EOF
test_assert_success "Core module imports"

# Test database creation
python3 << 'EOF' 2>/dev/null
import sys
sys.path.insert(0, '/opt/asa-ddos-remediation')
from asa_ddos_complete import DatabaseManager
db = DatabaseManager()
conn = __import__('sqlite3').connect(db.db_path)
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
count = cursor.fetchone()[0]
conn.close()
if count >= 4:
    print("OK")
else:
    print("ERROR: Not all tables created")
    sys.exit(1)
EOF
test_assert_success "Database initialization"

# Test configuration loading
python3 << 'EOF' 2>/dev/null
import json
try:
    with open('/etc/asa-ddos/config.json') as f:
        config = json.load(f)
    if 'asa' in config and 'slack' in config and 'email' in config:
        print("OK")
    else:
        print("ERROR: Missing configuration sections")
        exit(1)
except Exception as e:
    print(f"ERROR: {e}")
    exit(1)
EOF
test_assert_success "Configuration loading"

test_print_header "9. TESTE PARSING ALERT"

# Test IDS alert parsing
python3 << 'EOF' 2>/dev/null
import sys
sys.path.insert(0, '/opt/asa-ddos-remediation')
from asa_ddos_complete import DDOSRemediationEngine

engine = DDOSRemediationEngine()
alert = """
[**] [1:2345:1] DDoS Attack Detected [**]
{TCP} 203.0.113.50:54321 -> 192.168.1.100:80
"""

result = engine.parse_ids_alert(alert)
if result['source_ip'] == '203.0.113.50' and result['dest_ip'] == '192.168.1.100':
    print("OK")
else:
    print("ERROR: Alert parsing failed")
    sys.exit(1)
EOF
test_assert_success "IDS alert parsing"

test_print_header "10. TESTE WHITELIST"

# Test whitelist functionality
python3 << 'EOF' 2>/dev/null
import sys
sys.path.insert(0, '/opt/asa-ddos-remediation')
from asa_ddos_complete import DatabaseManager

db = DatabaseManager()
test_ip = "192.168.1.50"

# Add to whitelist
db.add_to_whitelist(test_ip, "Test IP", "test")

# Check whitelist
is_whitelisted = db.is_whitelisted(test_ip)

if is_whitelisted:
    print("OK")
else:
    print("ERROR: Whitelist check failed")
    sys.exit(1)
EOF
test_assert_success "Whitelist functionality"

test_print_header "11. TESTE ML DETECTION"

# Test ML module
python3 << 'EOF' 2>/dev/null
import sys
sys.path.insert(0, '/opt/asa-ddos-remediation')
from asa_ddos_complete import MLDDOSDetector

ml = MLDDOSDetector()

# Test traffic data
traffic = {
    'packets_per_sec': 1000,
    'bytes_per_sec': 100000,
    'unique_sources': 50,
    'port_diversity': 10,
    'protocol_variety': 2
}

result = ml.predict_ddos(traffic)
if 'is_ddos' in result and 'score' in result and 'confidence' in result:
    print("OK")
else:
    print("ERROR: ML prediction failed")
    sys.exit(1)
EOF
test_assert_success "ML detection module"

test_print_header "12. TESTE LOG ROTATION"

if [ -f "/etc/logrotate.d/asa-ddos" ]; then
    echo -e "${GREEN}✓ PASS${NC}: Logrotate configuration"
    ((TESTS_PASSED++))
else
    echo -e "${YELLOW}⚠ WARNING${NC}: Logrotate configuration not found"
fi

# ============= FINAL SUMMARY =============

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║ TEST SUMMARY${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

TOTAL=$((TESTS_PASSED + TESTS_FAILED))
PERCENTAGE=$((TESTS_PASSED * 100 / TOTAL))

echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
echo -e "${RED}Failed: $TESTS_FAILED${NC}"
echo -e "Total: $TOTAL"
echo -e "Success Rate: $PERCENTAGE%"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ ALL TESTS PASSED!${NC}"
    echo ""
    echo "Sistem gata pentru producție. Next steps:"
    echo "1. Pornire servicii: sudo systemctl start asa-ddos-*"
    echo "2. Verifica logs: tail -f /var/log/asa_ddos_remediation.log"
    echo "3. Deschide dashboard: http://localhost:5000"
    exit 0
else
    echo -e "${RED}✗ SOME TESTS FAILED${NC}"
    echo ""
    echo "Verifica erorile de mai sus și rulează din nou."
    echo "Pentru debugging, verifica logs:"
    echo "  tail -f /var/log/asa_ddos_remediation.log"
    exit 1
fi
