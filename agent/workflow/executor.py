"""
Workflow executor for Hawx Recon Agent.

Orchestrates the multi-layer reconnaissance workflow, manages command execution,
service discovery, and report generation for a given target.
"""

import sys
import os
import yaml
from typing import Dict, List
from .runner import run_layer
from .output import run_searchsploit, export_summary_to_pdf
from ..utils.records import Records
from ..utils.target import (
    initialize_target_variables,
    evaluate_condition,
    substitute_variables,
    update_open_ports,
)
import difflib


class ReconExecutor:
    """
    Executes the full reconnaissance workflow for a target machine.

    Handles command management, service tracking, and report generation across multiple layers.
    """

    def __init__(self, llm_client, target, interactive=False, target_mode="host"):
        """Initialize the ReconExecutor with LLM client, target, and mode."""
        # LLM client for prompt generation and summarization
        self.llm_client = llm_client
        # Target machine IP or hostname
        self.target = target
        # Whether to prompt user for each command (interactive mode)
        self.interactive = interactive
        # Target mode ('host' or 'website')
        self.target_mode = target_mode
        if self.target_mode == "website":
            if not (
                str(target).startswith("http://") or str(target).startswith("https://")
            ):
                print(
                    "[!] For website mode, the target must start with http:// or https:// (protocol is mandatory)"
                )
                sys.exit(1)
        # Directory for storing recon data for this target
        self.base_dir = os.path.join(
            "/mnt/triage",
            target if target_mode == "host" else self._get_domain(target),
        )
        os.makedirs(self.base_dir, exist_ok=True)
        # Records object to track commands and services
        self.records = Records()
        # Load layer0 configuration
        self.layer0_config = self._load_layer0_config()
        # Initialize target variables
        self.target_vars = initialize_target_variables(target, self.layer0_config)

    def _get_domain(self, url: str) -> str:
        """Extract the domain from a URL."""
        import re

        m = re.match(r"https?://([^/]+)", url)
        return m.group(1) if m else url

    def _load_layer0_config(self) -> Dict:
        """Load and validate the layer0.yaml configuration."""
        config_path = os.path.join(
            os.path.dirname(__file__), "../configs", "layer0.yaml"
        )
        try:
            with open(config_path, "r") as f:
                config = yaml.safe_load(f)

            # Basic validation
            for mode in ["host_mode", "website_mode"]:
                if mode not in config:
                    print(f"[!] Warning: {mode} not found in layer0.yaml")
                    config[mode] = {"commands": []}
                elif not isinstance(config[mode].get("commands"), list):
                    print(f"[!] Warning: Invalid commands format in {mode}")
                    config[mode]["commands"] = []

            return config
        except Exception as e:
            print(f"[!] Error loading layer0.yaml: {e}")
            # Return default configuration
            return {
                "host_mode": {
                    "commands": [
                        {"command": "nmap -sC -sV -p- {target}", "required": True}
                    ]
                },
                "website_mode": {
                    "commands": [
                        {"command": "whatweb {target}", "required": True},
                        {"command": "subfinder -d {domain}", "required": False},
                    ]
                },
                "global": {"max_retries": 2, "parallel": False},
            }

    def _get_layer0_commands(self) -> List[str]:
        """Get the appropriate layer0 commands based on target mode and conditions."""
        mode_key = f"{self.target_mode}_mode"
        commands = []

        for cmd_config in self.layer0_config.get(mode_key, {}).get("commands", []):
            if not isinstance(cmd_config, dict):
                continue

            # Check all conditions are met
            conditions = cmd_config.get("conditions", [{"type": "always"}])
            if all(evaluate_condition(cond, self.target_vars) for cond in conditions):
                cmd = cmd_config.get("command", "")
                if cmd:
                    # Substitute all variables
                    cmd = substitute_variables(cmd, self.target_vars)
                    commands.append(cmd)

        return commands

    def _interactive_tool_menu(self, tool_cmds):
        """Interactive menu for selecting which web recon tools to run."""
        # This menu is only shown if --interactive flag is used
        print(
            "\n[?] Select which web recon tools to run (space to toggle, enter to confirm):"
        )
        selected = [True] * len(tool_cmds)
        tool_names = [cmd.split()[0] for cmd in tool_cmds]
        while True:
            for i, (tool, sel) in enumerate(zip(tool_names, selected)):
                mark = "[x]" if sel else "[ ]"
                print(f"  {i+1}. {mark} {tool} : {tool_cmds[i]}")
            print(
                "  (Type numbers separated by space to toggle, or press enter to continue)"
            )
            inp = input("  > ").strip()
            if not inp:
                break
            for num in inp.split():
                if num.isdigit():
                    idx = int(num) - 1
                    if 0 <= idx < len(selected):
                        selected[idx] = not selected[idx]
            print()
        return [cmd for cmd, sel in zip(tool_cmds, selected) if sel]

    def _is_fuzzy_duplicate(self, cmd, all_prev_cmds, threshold=0.85):
        """Return True if cmd is similar to any in all_prev_cmds above threshold."""
        for prev in all_prev_cmds:
            ratio = difflib.SequenceMatcher(None, cmd, prev).ratio()
            if ratio >= threshold:
                return True
        return False

    def add_commands(self, commands, layer):
        """Store deduplicated and fuzzy-matched commands for the given workflow layer."""
        # Gather all previously executed commands from all layers up to this one
        all_prev_cmds = []
        for i in range(layer):
            if i < len(self.records.commands):
                all_prev_cmds.extend(self.records.commands[i])
        # Filter out fuzzy duplicates
        unique_cmds = [
            cmd for cmd in commands if not self._is_fuzzy_duplicate(cmd, all_prev_cmds)
        ]
        self.records.commands[layer] = unique_cmds
        deduped = self.llm_client.deduplicate_commands(self.records.commands, layer)
        final = deduped.get("deduplicated_commands", unique_cmds)
        self.records.commands[layer] = final

    def add_services(self, services):
        """Add discovered services to the records."""
        self.records.services.extend(services)

    def workflow(self, steps=3):
        """Run the full recon workflow for the target."""
        # Get layer0 commands from config
        layer0_cmds = self._get_layer0_commands()
        if self.interactive:
            layer0_cmds = self._interactive_tool_menu(layer0_cmds)

        # Run layer 0 commands
        layer0_output = run_layer(
            layer0_cmds,
            0,  # Layer 0 is initial scan
            self.llm_client,
            self.base_dir,
            self.records,
            self.interactive,
        )

        # Update target variables based on scan results
        if self.target_mode == "host":
            nmap_log_dir = os.path.join(self.base_dir, "logs")
            nmap_logs = [f for f in os.listdir(nmap_log_dir) if f.startswith("nmap_")]
            for log in nmap_logs:
                with open(os.path.join(nmap_log_dir, log), "r", encoding="utf-8") as f:
                    update_open_ports(self.target_vars, f.read())

            # Check web ports and adjust layer 1 commands accordingly
            open_ports = self.target_vars.get("open_ports", set())
            if 80 in open_ports or 443 in open_ports:
                proto = None
                if 443 in open_ports:
                    # Try HTTPS first
                    import subprocess

                    try:
                        resp = subprocess.run(
                            ["curl", "-I", f"https://{self.target}"],
                            capture_output=True,
                            text=True,
                            timeout=10,
                            check=False,
                        )
                        if "HTTP/" in resp.stdout:
                            proto = "https"
                    except Exception:
                        pass
                if not proto and 80 in open_ports:
                    try:
                        resp = subprocess.run(
                            ["curl", "-I", f"http://{self.target}"],
                            capture_output=True,
                            text=True,
                            timeout=10,
                            check=False,
                        )
                        if "HTTP/" in resp.stdout:
                            proto = "http"
                    except Exception:
                        pass

                # If protocol found, add web recon commands for layer 1
                if proto:
                    web_url = f"{proto}://{self.target}"
                    base_domain = self._get_domain(web_url)
                    web_cmds = [
                        f"whatweb {web_url}",
                        f"subfinder -d {base_domain}",
                    ]
                    if self.interactive:
                        web_cmds = self._interactive_tool_menu(web_cmds)
                    # Add web commands to layer 1
                    self.add_commands(web_cmds, 1)

        self.add_commands(layer0_output, 1)  # Add recommendations to layer 1

        # Run additional workflow layers as specified
        # Layers 1-5 are for AI recommended steps
        for i in range(1, min(steps + 1, 6)):  # steps=3 runs layers 0,1,2,3
            cmds = self.records.commands[i]
            new_recs = run_layer(
                cmds, i, self.llm_client, self.base_dir, self.records, self.interactive
            )
            if i < 5:  # Only add recommendations up to layer 5
                self.add_commands(new_recs, i + 1)

        # If any services were found, run SearchSploit for CVE discovery
        if self.records.services:
            run_searchsploit(self.records.services, self.base_dir)

        # Generate executive summary and export to PDF
        self.llm_client.executive_summary(self.base_dir)
        export_summary_to_pdf(self.base_dir)
