#!/bin/bash

set -e

echo "=== 🛰️  HTB Agent Container Started ==="
echo ""

# Checking mounted files
echo "[*] Checking mounted files in /mnt..."
ls -l /mnt
echo ""

# === Start VPN only if OVPN_FILE is provided ===
if [[ -n "${OVPN_FILE:-}" ]]; then
    echo "[*] Starting OpenVPN using config: $OVPN_FILE"
    openvpn --config "$OVPN_FILE" --daemon

    echo "[*] Waiting for VPN connection (interface tun0)..."
    RETRIES=15
    while ! ip a | grep -q "tun0"; do
        sleep 1
        ((RETRIES--))
        if [[ $RETRIES -eq 0 ]]; then
            echo "[!] ❌ tun0 did not appear. VPN failed to establish."
            exit 1
        fi
    done
    echo "[+] ✅ VPN interface tun0 is now up."
else
    echo "[*] Skipping VPN setup (no OVPN file provided)."
fi

# Probe target IP
echo "[*] Probing target: $TARGET_IP"
TCP_OK=false

echo "[*] Running Nmap ping scan to validate host is up..."
if nmap -sn "$TARGET_IP" | grep -q "Host is up"; then
    echo "[+] Nmap confirms host is up"
    TCP_OK=true
else
    echo "[!] Nmap could not confirm host is up"
fi

if [[ "$TCP_OK" == true ]]; then
    echo "[+] ✅ VPN and target connectivity confirmed via TCP."
else
    echo "[!] ❌ No open ports reachable on $TARGET_IP. Box may be down or firewalled."
    exit 1
fi
echo ""

# Add machine name to /etc/hosts if provided
if [[ -n "${MACHINE_NAME:-}" && "$TARGET_IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "[*] Mapping $MACHINE_NAME.htb to $TARGET_IP in /etc/hosts"
    echo "$TARGET_IP $MACHINE_NAME.htb" >> /etc/hosts
    echo "[+] Host mapping added."
    echo ""
elif [[ -n "${MACHINE_NAME:-}" ]]; then
    echo "[!] Skipping /etc/hosts mapping: '$TARGET_IP' is not an IPv4 address."
fi

# Cap STEPS at 3
if [[ -z "${STEPS:-}" ]]; then
    STEPS=1
fi

if [[ "$STEPS" -gt 3 ]]; then
    echo "[!] STEPS capped at 3. Setting to 3."
    STEPS=3
fi

# Check LLM_API_KEY
if [[ -z "${LLM_API_KEY:-}" ]]; then
    echo "[!] LLM_API_KEY environment variable is required."
    exit 1
fi

# Pass INTERACTIVE as third param to agent
INTERACTIVE_FLAG="${INTERACTIVE:-false}"

clear

# Run unit tests if TEST_MODE is enabled
# Run unit tests if TEST_MODE is enabled
if [[ "${TEST_MODE:-}" == "true" ]]; then
    echo "=== 🧪 Running tests in container ==="
    export PYTHONPATH=/opt/agent  # This points to the directory containing records.py etc.
    echo "PYTHONPATH set to: $PYTHONPATH"
    cd /mnt/tests || exit 1
    pytest -s --disable-warnings -q
    exit $?
fi


python3 /opt/agent/main.py "$TARGET_IP" "$STEPS" "$INTERACTIVE_FLAG"
