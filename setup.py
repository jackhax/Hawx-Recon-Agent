"""
Setup script for Hawx Recon Agent.

Installs required system (apt), Python (pip), and custom tools as defined in tools.yaml.
Intended to be run as root inside the Docker build or setup process.
"""

import os
import subprocess
import yaml


def load_config(path="/tmp/tools.yaml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)


def run_command(command, shell=False):
    print(f"\033[1;34m[+] Running:\033[0m {command}")
    try:
        subprocess.run(command, shell=shell, check=True)
    except subprocess.CalledProcessError as e:
        print(f"\033[91m[!] Failed:\033[0m {e}")


def install_apt_tools(packages):
    if not packages:
        return
    run_command(["apt-get", "update"])
    run_command(["apt-get", "install", "-y", "--no-install-recommends", *packages])
    run_command(["apt-get", "clean"])


def install_pip_tools(packages):
    if not packages:
        return
    run_command(
        ["pip3", "install", "--break-system-packages", "--no-cache-dir", *packages]
    )


def install_custom_commands(commands_dict):
    for name, cmd in commands_dict.items():
        print(f"\033[1;36m[+] Installing custom tool:\033[0m {name}")
        run_command(cmd, shell=True)


def main():
    if os.geteuid() != 0:
        print("\033[91m[!] Please run this script as root.\033[0m")
        return

    config = load_config()
    install_apt_tools(config.get("apt", []))
    install_pip_tools(config.get("pip", []))
    install_custom_commands(config.get("custom", {}))


if __name__ == "__main__":
    main()
