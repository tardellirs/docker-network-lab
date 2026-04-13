#!/bin/bash
# Integration tests for the Computer Networks Lab
# Requires: Docker, Docker Compose v2, sshpass, curl
# Usage: bash tests/test_integration.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
FAIL=0
TESTS_RUN=0

pass() { ((PASS++)); ((TESTS_RUN++)); echo -e "  ${GREEN}PASS${NC} $1"; }
fail() { ((FAIL++)); ((TESTS_RUN++)); echo -e "  ${RED}FAIL${NC} $1: $2"; }

cleanup() {
    echo ""
    echo -e "${YELLOW}Cleaning up...${NC}"
    docker compose down -v 2>/dev/null || true
    rm -f docker-compose.yml credentials.txt credentials.json
}
trap cleanup EXIT

echo "============================================"
echo " Computer Networks Lab — Integration Tests"
echo "============================================"
echo ""

# --- Setup ---
echo -e "${YELLOW}Setting up 2-student lab...${NC}"
python3 generate_lab.py -n 2 -s testpass123

if [ ! -f docker-compose.yml ]; then
    echo -e "${RED}FATAL: docker-compose.yml not generated${NC}"
    exit 1
fi

docker compose up -d --build

# Wait for containers to be ready
echo -e "${YELLOW}Waiting for services to start...${NC}"
sleep 5

# Retry loop: wait up to 30s for containers to be healthy
for i in $(seq 1 6); do
    running=$(docker compose ps --format json 2>/dev/null | grep -c '"running"' || true)
    if [ "$running" -ge 2 ]; then
        break
    fi
    echo "  Waiting... ($i/6)"
    sleep 5
done

echo ""
echo "--- Container Tests ---"

# Test 1: Containers are running
running=$(docker compose ps --format json | grep -c '"running"' || true)
if [ "$running" -ge 2 ]; then
    pass "Both containers are running"
else
    fail "Containers running" "Expected 2, got $running"
fi

# Test 2: HTTP accessible
echo ""
echo "--- HTTP Tests ---"
http_response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8001 2>/dev/null || echo "000")
if [ "$http_response" = "200" ]; then
    pass "student01 HTTP returns 200"
else
    fail "student01 HTTP" "Expected 200, got $http_response"
fi

http_body=$(curl -s http://localhost:8001 2>/dev/null || echo "")
if echo "$http_body" | grep -qi "redes"; then
    pass "student01 HTTP serves default page"
else
    fail "student01 HTTP content" "Default page not found"
fi

http_response2=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8002 2>/dev/null || echo "000")
if [ "$http_response2" = "200" ]; then
    pass "student02 HTTP returns 200"
else
    fail "student02 HTTP" "Expected 200, got $http_response2"
fi

# Test 3: ttyd accessible (returns 401 without credentials, which proves it's running)
echo ""
echo "--- ttyd Tests ---"
ttyd_response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:7001 2>/dev/null || echo "000")
if [ "$ttyd_response" = "200" ] || [ "$ttyd_response" = "401" ]; then
    pass "student01 ttyd is responding (HTTP $ttyd_response)"
else
    fail "student01 ttyd" "Expected 200 or 401, got $ttyd_response"
fi

# Test 4: SSH accessible
echo ""
echo "--- SSH Tests ---"
if command -v sshpass &>/dev/null; then
    ssh_result=$(sshpass -p testpass123 ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 -p 2201 student@localhost whoami 2>/dev/null || echo "FAILED")
    if [ "$ssh_result" = "student" ]; then
        pass "student01 SSH login works"
    else
        fail "student01 SSH" "Expected 'student', got '$ssh_result'"
    fi
else
    echo -e "  ${YELLOW}SKIP${NC} SSH test (sshpass not installed)"
fi

# Test 5: Container-to-container communication
echo ""
echo "--- Network Tests ---"
ping_result=$(docker compose exec -T student01 ping -c 1 -W 3 student02 2>/dev/null && echo "OK" || echo "FAILED")
if echo "$ping_result" | grep -q "OK"; then
    pass "student01 can ping student02 by hostname"
else
    fail "Container-to-container ping" "student01 cannot reach student02"
fi

ping_result2=$(docker compose exec -T student02 ping -c 1 -W 3 student01 2>/dev/null && echo "OK" || echo "FAILED")
if echo "$ping_result2" | grep -q "OK"; then
    pass "student02 can ping student01 by hostname"
else
    fail "Container-to-container ping" "student02 cannot reach student01"
fi

# Test 6: Networking tools available
echo ""
echo "--- Tools Tests ---"
tools=("nmap" "tcpdump" "dig" "curl" "wget" "traceroute" "ip" "iptables" "python3" "vim" "nano")
for tool in "${tools[@]}"; do
    if docker compose exec -T student01 which "$tool" &>/dev/null; then
        pass "$tool is installed"
    else
        fail "$tool" "not found in container"
    fi
done

# Test 7: User 'student' exists and can write to /var/www/html
echo ""
echo "--- User Tests ---"
user_exists=$(docker compose exec -T student01 id student 2>/dev/null && echo "OK" || echo "FAILED")
if echo "$user_exists" | grep -q "OK"; then
    pass "User 'student' exists"
else
    fail "User student" "does not exist"
fi

web_writable=$(docker compose exec -T -u student student01 touch /var/www/html/test.txt 2>/dev/null && echo "OK" || echo "FAILED")
if [ "$web_writable" = "OK" ]; then
    pass "User 'student' can write to /var/www/html/"
else
    fail "Web directory" "student cannot write to /var/www/html/"
fi

# --- Summary ---
echo ""
echo "============================================"
echo -e " Results: ${GREEN}$PASS passed${NC}, ${RED}$FAIL failed${NC} (${TESTS_RUN} total)"
echo "============================================"

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
