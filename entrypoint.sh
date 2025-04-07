#!/bin/bash

set -e

# Display starting message
echo "=== 🛰️  HTB Agent Container Started ==="
echo ""

# Checking mounted files
echo "[*] Checking mounted files in /mnt..."
ls -l /mnt
echo ""

# Start OpenVPN with config
echo "[*] Starting OpenVPN using config: $OVPN_FILE"
openvpn --config "$OVPN_FILE" --daemon
echo "[*] OpenVPN daemon started."

# Wait for VPN connection (interface tun0)
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

# Probe target IP
#TODO: Need more concrete probing
echo "[*] Probing target: $TARGET_IP"
TCP_OK=false

# Nmap quick ping scan
echo "[*] Running Nmap ping scan to validate host is up..."
if nmap -sn "$TARGET_IP" | grep -q "Host is up"; then
    echo "[+] Nmap confirms host is up"
    TCP_OK=true
else
    echo "[!] Nmap could not confirm host is up"
fi


# Confirm TCP connectivity
if [[ "$TCP_OK" == true ]]; then
    echo "[+] ✅ VPN and target connectivity confirmed via TCP."
else
    echo "[!] ❌ No open ports reachable on $TARGET_IP. Box may be down or firewalled."
    exit 1
fi
echo ""

# Add machine name to /etc/hosts if provided
if [[ -n "$MACHINE_NAME" ]]; then
    echo "[*] Mapping $MACHINE_NAME.htb to $TARGET_IP in /etc/hosts"
    echo "$TARGET_IP $MACHINE_NAME.htb" >> /etc/hosts
    echo "[+] Host mapping added."
    echo ""
fi


# Launch LLM agent (agent.py)
clear
echo "[*] 🚀 Launching LLM agent (agent.py)..."
python3 /opt/agent/main.py $TARGET_IP

