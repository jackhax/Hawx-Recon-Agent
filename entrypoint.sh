#!/bin/bash

set -e

echo ""
echo "=== 🛰️  HTB Agent Container Started ==="
echo ""

echo "[*] Checking mounted files in /mnt..."
ls -l /mnt
echo ""

echo "[*] Starting OpenVPN using config: $OVPN_FILE"
openvpn --config "$OVPN_FILE" --daemon
echo "[*] OpenVPN daemon started."
echo ""

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
echo ""

echo "=== 🌐 VPN Interface Details ==="
ip -4 addr show dev tun0 | grep inet || echo "[!] No IP assigned to tun0"
echo ""
echo "=== 🧭 Routing Table ==="
ip route
echo ""

echo "[*] Testing external connectivity (DNS)..."
if nslookup google.com > /dev/null 2>&1; then
    echo "[+] ✅ DNS resolution is working."
else
    echo "[!] ❌ DNS resolution failed."
fi
echo ""

echo "[*] Probing target: $TARGET_IP"
TCP_OK=false

echo "[*] 🔌 Checking TCP port 80..."
if nc -vz "$TARGET_IP" 80; then
    echo "[+] Port 80 is open"
    TCP_OK=true
else
    echo "[!] Port 80 is closed"
fi

echo "[*] 🔌 Checking TCP port 22..."
if nc -vz "$TARGET_IP" 22; then
    echo "[+] Port 22 is open"
    TCP_OK=true
else
    echo "[!] Port 22 is closed"
fi
echo ""

echo "[*] Performing traceroute to $TARGET_IP..."
traceroute "$TARGET_IP" || echo "[!] Traceroute failed"
echo ""

echo "[*] Network interfaces:"
ip a
echo ""

if [[ "$TCP_OK" == true ]]; then
    echo "[+] ✅ VPN and target connectivity confirmed via TCP."
else
    echo "[!] ❌ No open ports reachable on $TARGET_IP. Box may be down or firewalled."
    exit 1
fi
echo ""

if [[ -n "$MACHINE_NAME" ]]; then
    echo "[*] Mapping $MACHINE_NAME.htb to $TARGET_IP in /etc/hosts"
    echo "$TARGET_IP $MACHINE_NAME.htb" >> /etc/hosts
    echo "[+] Host mapping added."
    echo ""
fi

echo "[*] 🚀 Launching LLM agent (agent.py)..."
python3 /opt/agent/agent.py
