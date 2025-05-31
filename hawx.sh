#!/bin/bash

set -euo pipefail

IMAGE_NAME="hawx-agent"
FORCE_BUILD=false
STEPS=1
OVPN_FILE=""
TARGET=""
INTERACTIVE=false
TEST_MODE=false
HOSTS_FILE=""
HOST=""
WEBSITE=""

function show_help() {
    echo ""
    echo "Usage: $0 [--force-build] [--steps N] [--ovpn FILE] [--hosts FILE] [--interactive] <ip|domain|url>"
    echo ""
    echo "Options:"
    echo "  --force-build   Rebuild the Docker image before execution."
    echo "  --steps N       Number of layers of commands to execute (default: 1, max: 3)."
    echo "  --ovpn FILE     Optional OpenVPN config file."
    echo "  --hosts FILE    Optional file whose contents are appended to /etc/hosts inside container."
    echo "  --interactive   Run in interactive LLM-assisted mode."
    echo "  --help          Show this help message and exit."
    echo ""
    echo "Example:"
    echo "  $0 10.10.11.58"
    echo "  $0 example.com"
    echo "  $0 https://example.com"
    exit 0
}

# === Parse flags and positional target ===
POSITIONAL=()
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
        --hosts)
            if [[ -z "${2:-}" || "$2" =~ ^-- ]]; then
                echo "[!] Missing value for --hosts"
                exit 1
            fi
            HOSTS_FILE="$2"
            if [[ ! -f "$HOSTS_FILE" ]]; then
                echo "[!] Hosts file '$HOSTS_FILE' does not exist."
                exit 1
            fi
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
        *)
            POSITIONAL+=("$1")
            shift
            ;;
    esac

done

set -- "${POSITIONAL[@]}"

if [[ $# -lt 1 ]]; then
    echo "[!] You must specify a target (IP, domain, or website URL)."
    show_help
fi
TARGET="$1"

# === Target validation ===
# Check if it's a valid IPv4 or IPv6
if [[ "$TARGET" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
    # IPv4
    VALID_TARGET=true
    TARGET_MODE="host"
elif [[ "$TARGET" =~ ^([0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}$ ]]; then
    # IPv6
    VALID_TARGET=true
    TARGET_MODE="host"
elif [[ "$TARGET" =~ ^https?:// ]]; then
    # Website URL
    # Validate protocol and domain
    if [[ "$TARGET" =~ ^https?://[^/]+ ]]; then
        VALID_TARGET=true
        TARGET_MODE="website"
    else
        echo "[!] Invalid website URL: $TARGET"
        exit 1
    fi
elif [[ "$TARGET" =~ ^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]]; then
    # Domain
    VALID_TARGET=true
    TARGET_MODE="host"
else
    echo "[!] Invalid target: $TARGET"
    exit 1
fi

# === Clean workspace ===
if [[ -n "$HOST" ]]; then
    rm -rf triage/"$HOST"
fi
if [[ -n "$WEBSITE" ]]; then
    # Use domain as folder name (strip protocol and path)
    DOMAIN=$(echo "$WEBSITE" | sed -E 's~https?://([^/]+).*~\1~')
    rm -rf triage/"$DOMAIN"
fi

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

# Mount tests directory only for test mode
if [[ "$TEST_MODE" == true ]]; then
    DOCKER_NET_OPTS+=" -v \"$(pwd)/tests\":/mnt/tests"
fi

# Mount hosts file if provided
if [[ -n "$HOSTS_FILE" ]]; then
    ABS_HOSTS_FILE="$(cd "$(dirname "$HOSTS_FILE")" && pwd)/$(basename "$HOSTS_FILE")"
    REL_HOSTS_FILE="${ABS_HOSTS_FILE#$(pwd)/}"
    DOCKER_NET_OPTS+=" -v \"$(pwd)/$REL_HOSTS_FILE\":/mnt/custom_hosts"
    DOCKER_OVPN_ENV+=" -e CUSTOM_HOSTS_FILE=\"/mnt/custom_hosts\""
fi

# === Build Docker image if needed ===
if [[ "$FORCE_BUILD" == true || "$(docker images -q "$IMAGE_NAME" 2>/dev/null)" == "" ]]; then
    echo "[*] Building Docker image '$IMAGE_NAME'..."
    docker build --platform=linux/amd64 -t "$IMAGE_NAME" .
else
    echo "[*] Docker image '$IMAGE_NAME' already exists. Skipping build."
fi

# === Compose Docker run command ===
DOCKER_CMD="docker run --rm -it \
$DOCKER_NET_OPTS \
-e STEPS=\"$STEPS\" \
-e LLM_API_KEY=\"$LLM_API_KEY\""
if [[ "$TARGET_MODE" == "host" ]]; then
    DOCKER_CMD+=" -e TARGET_HOST=\"$TARGET\""
fi
if [[ "$TARGET_MODE" == "website" ]]; then
    DOCKER_CMD+=" -e TARGET_WEBSITE=\"$TARGET\""
fi
if [[ "$INTERACTIVE" == true ]]; then
    DOCKER_CMD+=" -e INTERACTIVE=true"
fi
if [[ -n "$DOCKER_OVPN_ENV" ]]; then
    DOCKER_CMD+=" $DOCKER_OVPN_ENV"
fi
if [[ "$TEST_MODE" == true ]]; then
    DOCKER_CMD+=" -e TEST_MODE=true"
fi

DOCKER_CMD+=" $IMAGE_NAME"

# === Execute container ===
echo "[*] Running container..."
eval "$DOCKER_CMD"