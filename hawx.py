#!/usr/bin/env python3
import argparse
import os
import re
import subprocess
import sys
import yaml
import filecmp


def generate_dependency_files():
    """Generate dependency files from tools.yaml"""
    tools_yaml_path = os.path.join("configs", "tools.yaml")
    if not os.path.exists(tools_yaml_path):
        print("[!] tools.yaml not found in configs directory")
        return

    # Read tools.yaml
    with open(tools_yaml_path, 'r') as f:
        tools_config = yaml.safe_load(f)

    # Get apt packages directly from the apt key
    apt_packages = tools_config.get('apt', [])

    # Get pip requirements directly from the pip key
    pip_requirements = tools_config.get('pip', [])

    # Get custom installation commands from the custom key
    custom_installs = []
    for tool, command in tools_config.get('custom', {}).items():
        custom_installs.append(f"# Installing {tool}")
        custom_installs.append(command)
        custom_installs.append("")  # Add empty line for readability

    # Write requirements_runtime.txt.tmp
    with open('requirements_runtime.txt.tmp', 'w') as f:
        f.write('\n'.join(sorted(pip_requirements)) +
                '\n' if pip_requirements else '')

    # Write apt_install.sh.tmp
    with open('apt_install.sh.tmp', 'w') as f:
        f.write('#!/bin/bash\n\n')
        f.write('apt-get update && apt-get install -y --fix-missing \\\n')
        f.write('    ' + ' \\\n    '.join(sorted(apt_packages)) +
                '\n' if apt_packages else '')

    # Write custom_install.sh.tmp
    with open('custom_install.sh.tmp', 'w') as f:
        f.write('#!/bin/bash\n\n')
        if custom_installs:
            f.write('\n'.join(custom_installs).strip() + '\n')

    # Compare and replace files if different
    files_to_check = [
        ('requirements_runtime.txt.tmp', 'requirements_runtime.txt'),
        ('apt_install.sh.tmp', 'apt_install.sh'),
        ('custom_install.sh.tmp', 'custom_install.sh')
    ]

    for tmp_file, target_file in files_to_check:
        if not os.path.exists(target_file) or not filecmp.cmp(tmp_file, target_file, shallow=False):
            os.replace(tmp_file, target_file)
            os.chmod(target_file, 0o755)  # Make scripts executable
            print(f"[*] Updated {target_file}")
        else:
            os.remove(tmp_file)
            print(f"[*] No changes needed for {target_file}")


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
    if not os.path.exists(".env"):
        print("[!] .env file is required but not found.")
        sys.exit(1)
    with open(".env") as f:
        for line in f:
            if line.strip().startswith("LLM_API_KEY="):
                return line.strip().split("=", 1)[1]
    print("[!] LLM_API_KEY missing in .env")
    sys.exit(1)


def build_image(image_name, dockerfile=None):
    """Always build the Docker image."""
    print(f"[*] Building Docker image '{image_name}'...")
    cmd = ["docker", "build", "--platform=linux/amd64", "-t", image_name]
    if dockerfile:
        cmd += ["-f", dockerfile]
    cmd.append(".")
    subprocess.check_call(cmd)


def resolve_ip_from_hosts_file(ip, hosts_file):
    """Attempt to resolve an IP address to a hostname using a hosts file."""
    if not os.path.exists(hosts_file):
        return None

    with open(hosts_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
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
""",
    )
    parser.add_argument(
        "target", metavar="TARGET", help="Target IP, domain, or website URL"
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=3,
        choices=range(1, 6),
        help="Number of layers of commands to execute (default: 3, max: 5).",
    )
    parser.add_argument("--ovpn", metavar="FILE",
                        help="Optional OpenVPN config file.")
    parser.add_argument(
        "--hosts",
        metavar="FILE",
        help="Optional file whose contents are appended to /etc/hosts inside container.",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run in interactive LLM-assisted mode.",
    )
    parser.add_argument("--test", action="store_true",
                        help="Run in test mode.")
    parser.add_argument(
        "--timeout",
        type=int,
        default=180,
        help="Timeout for each command in seconds (default: 180).",
    )
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
    docker_net_opts = [
        "--cap-add=NET_ADMIN",
        "--device",
        "/dev/net/tun",
        "-v",
        f"{os.getcwd()}:/mnt",
    ]
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

    # --- Generate dependency files ---
    generate_dependency_files()

    # --- Build main image if needed ---
    build_image(IMAGE_NAME)

    # --- Compose Docker run command ---
    docker_cmd = [
        "docker",
        "run",
        "--rm",
        "-it",
        *docker_net_opts,
        "-e",
        f"STEPS={args.steps}",
        "-e",
        f"LLM_API_KEY={llm_api_key}",
        "-e",
        f"TIMEOUT={args.timeout}",
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
