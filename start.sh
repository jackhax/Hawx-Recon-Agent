#!/bin/bash

set -e

rm -rf reports/ 
rm -rf summaries/

IMAGE_NAME="htb-agent"
FORCE_BUILD=false

# === Load environment variables from .env file ===
if [[ ! -f .env ]]; then
    echo "[!] .env file is required but not found."
    exit 1
fi

# Export environment variables from .env
export $(grep -v '^#' .env | xargs)

# Ensure required environment variables are set
if [[ -z "$LLM_API_KEY" ]]; then
    echo "[!] LLM_API_KEY is missing or empty in .env"
    exit 1
fi

if [[ -z "$LLM_PROVIDER" ]]; then
    echo "[!] LLM_PROVIDER is missing or empty in .env"
    exit 1
fi

# === Parse flags ===
while [[ "$1" =~ ^-- ]]; do
    case "$1" in
        --force-build) FORCE_BUILD=true ;;
        *) echo "[!] Unknown flag: $1" && exit 1 ;;
    esac
    shift
done

# === Parse positional arguments ===
TARGET_IP="$1"
OVPN_FILE="$2"
MACHINE_NAME="$3"

# === Validate inputs ===
if [[ -z "$TARGET_IP" || -z "$OVPN_FILE" ]]; then
    echo "Usage: $0 [--force-build] <target_ip> <path_to_ovpn_file> [machine_name]"
    exit 1
fi

if [[ ! -f "$OVPN_FILE" ]]; then
    echo "[!] Error: OVPN file '$OVPN_FILE' does not exist."
    exit 1
fi

# === Normalize OVPN file path for Docker mount ===
ABS_OVPN_FILE="$(cd "$(dirname "$OVPN_FILE")" && pwd)/$(basename "$OVPN_FILE")"
REL_OVPN_FILE="${ABS_OVPN_FILE#$(pwd)/}"

# === Build Docker image if needed ===
if [[ "$FORCE_BUILD" == true || "$(docker images -q $IMAGE_NAME 2> /dev/null)" == "" ]]; then
    echo "[*] Building Docker image '$IMAGE_NAME'..."
    docker build -t "$IMAGE_NAME" .
else
    echo "[*] Docker image '$IMAGE_NAME' already exists. Skipping build."
fi

# === Prepare the Docker run command ===
DOCKER_CMD="docker run --rm -it \
  --cap-add=NET_ADMIN \
  --device /dev/net/tun \
  -v \"$(pwd)\":/mnt \
  -e TARGET_IP=\"$TARGET_IP\" \
  -e OVPN_FILE=\"/mnt/$REL_OVPN_FILE\""

# Pass environment variables (e.g., LLM_API_KEY, LLM_PROVIDER) into Docker container
for VAR in $(grep -v '^#' .env | cut -d= -f1); do
  DOCKER_CMD+=" -e $VAR=\"${!VAR}\""
done

if [[ -n "$MACHINE_NAME" ]]; then
    DOCKER_CMD+=" -e MACHINE_NAME=\"$MACHINE_NAME\""
fi

DOCKER_CMD+=" $IMAGE_NAME"

# === Run the container ===
echo "[*] Running container..."
eval "$DOCKER_CMD"