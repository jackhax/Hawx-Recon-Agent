#!/usr/bin/env python3
import argparse
import os
import re
import subprocess
import sys

# --- Constants ---
IMAGE_NAME = "hawx-agent"
BASE_IMAGE_NAME = "hawx-recon-base:latest"

# --- Helpers ---


def is_valid_ipv4(target):
    return re.match(r"^([0-9]{1,3}\.){3}[0-9]{1,3}$", target)


def is_valid_ipv6(target):
    return re.match(r"^([0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}$", target)


def is_valid_domain(target):
    return re.match(r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", target)


def is_valid_url(target):
    return re.match(r"^https?://[^/]+", target)


def load_llm_api_key():
    if not os.path.exists('.env'):
        print("[!] .env file is required but not found.")
        sys.exit(1)
    with open('.env') as f:
        for line in f:
            if line.strip().startswith('LLM_API_KEY='):
                return line.strip().split('=', 1)[1]
    print("[!] LLM_API_KEY missing in .env")
    sys.exit(1)


def build_image_if_needed(image_name, dockerfile=None, force=False):
    result = subprocess.run(
        ["docker", "images", "-q", image_name], capture_output=True, text=True)
    if force or not result.stdout.strip():
        print(f"[*] Building Docker image '{image_name}'...")
        cmd = [
            "docker", "build",
            "--platform=linux/amd64",
            "-t", image_name
        ]
        if dockerfile:
            cmd += ["-f", dockerfile]
        cmd.append(".")
        subprocess.check_call(cmd)
    else:
        print(
            f"[*] Docker image '{image_name}' already exists. Skipping build.")


def resolve_ip_from_hosts_file(ip, hosts_file):
    """Attempt to resolve an IP address to a hostname using a hosts file."""
    if not os.path.exists(hosts_file):
        return None

    with open(hosts_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                parts = line.split()
                if len(parts) >= 2 and parts[0] == ip:
                    return parts[1]  # Return the first hostname for this IP
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Hawx Recon Agent CLI",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
Examples:
  hawx.py 10.10.11.58
  hawx.py example.com
  hawx.py https://example.com
"""
    )
    parser.add_argument('target', metavar='TARGET',
                        help='Target IP, domain, or website URL')
    parser.add_argument('--force-build', action='store_true',
                        help='Rebuild the Docker image before execution.')
    parser.add_argument('--steps', type=int, default=1, choices=range(1, 4),
                        help='Number of layers of commands to execute (default: 1, max: 3).')
    parser.add_argument('--ovpn', metavar='FILE',
                        help='Optional OpenVPN config file.')
    parser.add_argument('--hosts', metavar='FILE',
                        help='Optional file whose contents are appended to /etc/hosts inside container.')
    parser.add_argument('--interactive', action='store_true',
                        help='Run in interactive LLM-assisted mode.')
    parser.add_argument('--test', action='store_true',
                        help='Run in test mode.')
    parser.add_argument('--timeout', type=int, default=180,
                        help='Timeout for each command in seconds (default: 180).')
    args = parser.parse_args()

    # --- Target validation ---
    target = args.target
    if is_valid_ipv4(target):
        target_mode = "host"
        # If hosts file is provided, try to resolve the IP to a hostname
        if args.hosts:
            hostname = resolve_ip_from_hosts_file(target, args.hosts)
            if hostname:
                print(f"[*] Resolved {target} to {hostname} from hosts file")
                target = hostname
    elif is_valid_ipv6(target):
        target_mode = "host"
    elif is_valid_url(target):
        target_mode = "website"
    elif is_valid_domain(target):
        target_mode = "host"
    else:
        print(f"[!] Invalid target: {target}")
        sys.exit(1)

    # --- Clean workspace ---
    triage_dir = None
    if target_mode == "host":
        triage_dir = os.path.join("triage", target)
    elif target_mode == "website":
        domain = re.sub(r"^https?://([^/]+).*", r"\1", target)
        triage_dir = os.path.join("triage", domain)
    if triage_dir and os.path.exists(triage_dir):
        import shutil
        shutil.rmtree(triage_dir)

    # --- Load LLM_API_KEY ---
    llm_api_key = load_llm_api_key()

    # --- Docker volume and env setup ---
    docker_net_opts = ["--cap-add=NET_ADMIN", "--device",
                       "/dev/net/tun", "-v", f"{os.getcwd()}:/mnt"]
    docker_ovpn_env = []
    if args.ovpn:
        if not os.path.isfile(args.ovpn):
            print(f"[!] Error: OVPN file '{args.ovpn}' does not exist.")
            sys.exit(1)
        abs_ovpn = os.path.abspath(args.ovpn)
        rel_ovpn = os.path.relpath(abs_ovpn, os.getcwd())
        docker_ovpn_env += ["-e", f"OVPN_FILE=/mnt/{rel_ovpn}"]
    if args.test:
        docker_net_opts += ["-v", f"{os.getcwd()}/tests:/mnt/tests"]
    if args.hosts:
        if not os.path.isfile(args.hosts):
            print(f"[!] Hosts file '{args.hosts}' does not exist.")
            sys.exit(1)
        abs_hosts = os.path.abspath(args.hosts)
        rel_hosts = os.path.relpath(abs_hosts, os.getcwd())
        docker_net_opts += ["-v",
                            f"{os.getcwd()}/{rel_hosts}:/mnt/custom_hosts"]
        docker_ovpn_env += ["-e", "CUSTOM_HOSTS_FILE=/mnt/custom_hosts"]

    # --- Build main image if needed ---
    build_image_if_needed(IMAGE_NAME, force=args.force_build)

    # --- Compose Docker run command ---
    docker_cmd = [
        "docker", "run", "--rm", "-it",
        *docker_net_opts,
        "-e", f"STEPS={args.steps}",
        "-e", f"LLM_API_KEY={llm_api_key}",
        "-e", f"TIMEOUT={args.timeout}"
    ]
    if target_mode == "host":
        docker_cmd += ["-e", f"TARGET_HOST={target}"]
    if target_mode == "website":
        docker_cmd += ["-e", f"TARGET_WEBSITE={target}"]
    if args.interactive:
        docker_cmd += ["-e", "INTERACTIVE=true"]
    if docker_ovpn_env:
        docker_cmd += docker_ovpn_env
    if args.test:
        docker_cmd += ["-e", "TEST_MODE=true"]
    docker_cmd.append(IMAGE_NAME)

    print("[*] Running container...")
    subprocess.run(docker_cmd, check=True)


if __name__ == "__main__":
    main()
