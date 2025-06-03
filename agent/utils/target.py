"""
Target manipulation utilities for Hawx Recon Agent.

Provides functions for target resolution, transformation, and condition evaluation.
"""

import re
import socket
from typing import Dict, Set


def resolve_ip(target: str) -> str:
    """Resolve hostname to IP address."""
    # Remove scheme if present
    hostname = re.sub(r'^https?://', '', target)
    # Remove path and query components
    hostname = hostname.split('/')[0]

    try:
        if re.match(r'^(\d{1,3}\.){3}\d{1,3}$', hostname):
            return hostname
        return socket.gethostbyname(hostname)
    except socket.gaierror:
        return ''


def initialize_target_variables(target: str, layer0_config: Dict) -> Dict[str, str]:
    """Initialize all target-related variables using regex patterns."""
    target_vars = {
        'target': target,
        'ip': resolve_ip(target),
        'open_ports': set()  # Will be populated during nmap scan
    }

    # Apply all transformations from config
    transformations = layer0_config.get('transformations', {})
    for var_name, transform in transformations.items():
        pattern = transform.get('pattern')
        group = transform.get('group', 1)
        if pattern:
            match = re.search(pattern, target)
            if match and len(match.groups()) >= group:
                target_vars[var_name] = match.group(group)

    return target_vars


def evaluate_condition(condition: Dict, target_vars: Dict[str, str]) -> bool:
    """Evaluate if a command should run based on its conditions."""
    cond_type = condition.get('type')

    if cond_type == 'always':
        return True

    elif cond_type == 'has_subdomain':
        return bool(target_vars.get('subdomain'))

    elif cond_type == 'is_ip':
        target = target_vars.get('target', '')
        return bool(re.match(r'^(\d{1,3}\.){3}\d{1,3}$', target))

    elif cond_type == 'port_open':
        port = condition.get('port')
        open_ports = target_vars.get('open_ports', set())
        return port in open_ports

    elif cond_type == 'custom_regex':
        pattern = condition.get('pattern')
        if pattern:
            target = target_vars.get('target', '')
            return bool(re.search(pattern, target))

    return False


def substitute_variables(command: str, target_vars: Dict[str, str]) -> str:
    """Substitute all target variables in command string."""
    for var_name, value in target_vars.items():
        if isinstance(value, (str, int)):
            command = command.replace(f"{{{var_name}}}", str(value))
    return command


def update_open_ports(target_vars: Dict[str, str], nmap_output: str) -> None:
    """Update open ports from nmap scan output."""
    port_pattern = re.compile(r'(\d+)/tcp\s+open')
    open_ports = target_vars.get('open_ports', set())
    if isinstance(open_ports, set):
        for match in port_pattern.finditer(nmap_output):
            open_ports.add(int(match.group(1)))
