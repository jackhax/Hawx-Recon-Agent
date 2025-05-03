#!/bin/bash

set -euo pipefail

IMAGE_NAME="hawx-agent"
FORCE_BUILD=false
STEPS=1
OVPN_FILE=""
MACHINE_NAME=""
TARGET=""
INTERACTIVE=false
TEST_MODE=false

function show_help() {
    echo ""
    echo "Usage: $0 [--force-build] [--steps N] [--ovpn FILE] [--hostname NAME] [--interactive] <target>"
    echo ""
    echo "Options:"
    echo "  --force-build   Rebuild the Docker image before execution."
    echo "  --steps N       Number of layers of commands to execute (default: 1, max: 3)."
    echo "  --ovpn FILE     Optional OpenVPN config file."
    echo "  --hostname NAME Optional hostname to add to /etc/hosts."
    echo "  --interactive   Run in interactive LLM-assisted mode."
    echo "  --help          Show this help message and exit."
    echo ""
    echo "Example:"
    echo "  $0 --steps 2 --ovpn vpn.ovpn --hostname dog --interactive 10.10.11.58"
    exit 0
}

# === Parse flags ===
while [[ $# -gt 0 ]]; do
    case "$1" in
        --help)
            show_help
            ;;
        --force-build)
            FORCE_BUILD=true
            shift
            ;;
        --steps)
            if [[ -z "${2:-}" || "$2" =~ ^-- ]]; then
                echo "[!] Missing value for --steps"
                exit 1
            fi
            STEPS="$2"
            if ! [[ "$STEPS" =~ ^[0-9]+$ ]] || [[ "$STEPS" -lt 1 || "$STEPS" -gt 3 ]]; then
                echo "[!] --steps must be an integer between 1 and 3"
                exit 1
            fi
            shift 2
            ;;
        --ovpn)
            if [[ -z "${2:-}" || "$2" =~ ^-- ]]; then
                echo "[!] Missing value for --ovpn"
                exit 1
            fi
            OVPN_FILE="$2"
            shift 2
            ;;
        --hostname)
            if [[ -z "${2:-}" || "$2" =~ ^-- ]]; then
                echo "[!] Missing value for --hostname"
                exit 1
            fi
            MACHINE_NAME="$2"
            shift 2
            ;;
        --interactive)
            INTERACTIVE=true
            shift
            ;;
        --test)
            TEST_MODE=true
            shift
            ;;
        -*)
            echo "[!] Unknown flag: $1"
            exit 1
            ;;
        *)
            if [[ -n "$TARGET" ]]; then
                echo "[!] Error: Multiple targets specified. Only one target (IP or domain) is allowed."
                exit 1
            fi
            TARGET="$1"
            shift
            ;;

    esac
done

# === Validate required argument: TARGET ===
if [[ -z "$TARGET" ]]; then
    echo "[!] Missing target (IP or domain)."
    show_help
fi

if ! [[ "$TARGET" =~ ^([a-zA-Z0-9.-]+|\b([0-9]{1,3}\.){3}[0-9]{1,3}\b)$ ]]; then
    echo "[!] Invalid target format: $TARGET"
    exit 1
fi

# === Clean workspace ===
rm -rf triage/"$TARGET"

# === Load only LLM_API_KEY from .env ===
if [[ ! -f .env ]]; then
    echo "[!] .env file is required but not found."
    exit 1
fi

LLM_API_KEY=""
while IFS='=' read -r key value; do
    [[ -z "$key" || "$key" =~ ^# ]] && continue
    if [[ "$key" == "LLM_API_KEY" ]]; then
        LLM_API_KEY="$value"
    fi
done < .env

if [[ -z "$LLM_API_KEY" ]]; then
    echo "[!] LLM_API_KEY missing in .env"
    exit 1
fi

# === Normalize OVPN path if provided ===
DOCKER_OVPN_ENV=""
DOCKER_NET_OPTS="--cap-add=NET_ADMIN --device /dev/net/tun -v \"$(pwd)\":/mnt"
if [[ -n "$OVPN_FILE" ]]; then
    if [[ ! -f "$OVPN_FILE" ]]; then
        echo "[!] Error: OVPN file '$OVPN_FILE' does not exist."
        exit 1
    fi
    ABS_OVPN_FILE="$(cd "$(dirname "$OVPN_FILE")" && pwd)/$(basename "$OVPN_FILE")"
    REL_OVPN_FILE="${ABS_OVPN_FILE#$(pwd)/}"
    DOCKER_OVPN_ENV="-e OVPN_FILE=\"/mnt/$REL_OVPN_FILE\""
fi

# === Build Docker image if needed ===
if [[ "$FORCE_BUILD" == true || "$(docker images -q "$IMAGE_NAME" 2>/dev/null)" == "" ]]; then
    echo "[*] Building Docker image '$IMAGE_NAME'..."
    docker build --platform=linux/amd64 -t "$IMAGE_NAME" .
else
    echo "[*] Docker image '$IMAGE_NAME' already exists. Skipping build."
fi

# Mount tests directory only for test mode
if [[ "$TEST_MODE" == true ]]; then
    DOCKER_NET_OPTS+=" -v \"$(pwd)/tests\":/mnt/tests"
fi

# === Compose Docker run command ===
DOCKER_CMD="docker run --rm -it \
$DOCKER_NET_OPTS \
-e TARGET_IP=\"$TARGET\" \
-e STEPS=\"$STEPS\" \
-e LLM_API_KEY=\"$LLM_API_KEY\""

if [[ "$INTERACTIVE" == true ]]; then
    DOCKER_CMD+=" -e INTERACTIVE=true"
fi

if [[ -n "$DOCKER_OVPN_ENV" ]]; then
    DOCKER_CMD+=" $DOCKER_OVPN_ENV"
fi

if [[ -n "$MACHINE_NAME" ]]; then
    DOCKER_CMD+=" -e MACHINE_NAME=\"$MACHINE_NAME\""
fi

if [[ "$TEST_MODE" == true ]]; then
    DOCKER_CMD+=" -e TEST_MODE=true"
fi



DOCKER_CMD+=" $IMAGE_NAME"

# === Execute container ===
echo "[*] Running container..."
eval "$DOCKER_CMD"
