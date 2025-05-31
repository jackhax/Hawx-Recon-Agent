"""
Workflow executor for Hawx Recon Agent.

Orchestrates the multi-layer reconnaissance workflow, manages command execution,
service discovery, and report generation for a given target.
"""

import os
from workflow.runner import run_layer
from workflow.output import run_searchsploit
from records import Records
from workflow.output import export_summary_to_pdf


class ReconExecutor:
    """
    Executes the full reconnaissance workflow for a target machine.

    Handles command management, service tracking, and report generation across multiple layers.
    """

    def __init__(self, llm_client, target, interactive=False, target_mode="host"):
        # LLM client for prompt generation and summarization
        self.llm_client = llm_client
        # Target machine IP or hostname
        self.target = target
        # Whether to prompt user for each command (interactive mode)
        self.interactive = interactive
        # Target mode ('host' or 'website')
        self.target_mode = target_mode
        if self.target_mode == "website":
            if not (str(target).startswith("http://") or str(target).startswith("https://")):
                print(
                    "[!] For website mode, the target must start with http:// or https:// (protocol is mandatory)")
                exit(1)
        # Directory for storing recon data for this target
        self.base_dir = os.path.join(
            "/mnt/triage",
            target if target_mode == "host" else self._get_domain(target),
        )
        os.makedirs(self.base_dir, exist_ok=True)
        # Records object to track commands and services
        self.records = Records()

    def _get_domain(self, url):
        import re

        m = re.match(r"https?://([^/]+)", url)
        return m.group(1) if m else url

    def add_commands(self, commands, layer):
        # Store deduplicated commands for the given workflow layer
        self.records.commands[layer] = commands
        deduped = self.llm_client.deduplicate_commands(
            self.records.commands, layer)
        final = deduped.get("deduplicated_commands", commands)
        self.records.commands[layer] = final

    def add_services(self, services):
        # Add discovered services to the records
        self.records.services.extend(services)

    def _interactive_tool_menu(self, tool_cmds):
        # This menu is only shown if --interactive flag is used
        print(
            "\n[?] Select which web recon tools to run (space to toggle, enter to confirm):")
        selected = [True] * len(tool_cmds)
        tool_names = [cmd.split()[0] for cmd in tool_cmds]
        while True:
            for i, (tool, sel) in enumerate(zip(tool_names, selected)):
                mark = '[x]' if sel else '[ ]'
                print(f"  {i+1}. {mark} {tool} : {tool_cmds[i]}")
            print(
                "  (Type numbers separated by space to toggle, or press enter to continue)")
            inp = input("  > ").strip()
            if not inp:
                break
            for num in inp.split():
                if num.isdigit():
                    idx = int(num)-1
                    if 0 <= idx < len(selected):
                        selected[idx] = not selected[idx]
            print()
        return [cmd for cmd, sel in zip(tool_cmds, selected) if sel]

    def workflow(self, steps=1):
        if self.target_mode == "host":
            # Start with nmap
            nmap_cmds = [f"nmap -sC -sV -p- {self.target}"]
            recommended = run_layer(
                nmap_cmds,
                -1,
                self.llm_client,
                self.base_dir,
                self.records,
                self.interactive,
            )
            self.add_commands(recommended, 0)

            # Check if nmap found port 80 or 443, then probe protocol
            nmap_log_dir = os.path.join(self.base_dir, "logs")
            nmap_logs = [f for f in os.listdir(
                nmap_log_dir) if f.startswith("nmap_")]
            found_http = False
            found_https = False
            for log in nmap_logs:
                with open(os.path.join(nmap_log_dir, log), "r", encoding="utf-8") as f:
                    content = f.read()
                    if "80/tcp" in content:
                        found_http = True
                    if "443/tcp" in content:
                        found_https = True
            # Probe protocol if web ports found
            if found_http or found_https:
                proto = None
                if found_https:
                    # Try HTTPS first
                    import subprocess

                    try:
                        resp = subprocess.run(
                            ["curl", "-I", f"https://{self.target}"],
                            capture_output=True,
                            text=True,
                            timeout=10,
                        )
                        if "HTTP/" in resp.stdout:
                            proto = "https"
                    except Exception:
                        pass
                if not proto and found_http:
                    try:
                        resp = subprocess.run(
                            ["curl", "-I", f"http://{self.target}"],
                            capture_output=True,
                            text=True,
                            timeout=10,
                        )
                        if "HTTP/" in resp.stdout:
                            proto = "http"
                    except Exception:
                        pass
                # If protocol found, add web recon commands for next layer
                if proto:
                    web_url = f"{proto}://{self.target}"
                    base_domain = self._get_domain(web_url)
                    web_cmds = [
                        f"whatweb {web_url}",
                        f"curl -I {web_url}",
                        # f"ffuf -u {web_url} -H 'Host: FUZZ' -w /usr/share/seclists/Discovery/DNS/namelist.txt -fs 0",
                        f"ffuf -u {web_url}/FUZZ -w /usr/share/seclists/Discovery/Web-Content/big.txt",
                        f"dnsrecon -d {base_domain} -D /usr/share/seclists/Discovery/DNS/namelist.txt -t brt"
                    ]
                    if self.interactive:
                        web_cmds = self._interactive_tool_menu(web_cmds)
                    self.add_commands(web_cmds, 1)
        elif self.target_mode == "website":
            # Start with web recon tools
            base_domain = self._get_domain(self.target)
            web_cmds = [
                f"whatweb {self.target}",
                f"curl -I {self.target}",
                # f"ffuf -u {self.target} -H 'Host: FUZZ' -w /usr/share/seclists/Discovery/DNS/namelist.txt -fs 0",
                f"ffuf -u {self.target}/FUZZ -w /usr/share/seclists/Discovery/Web-Content/big.txt",
                f"dnsrecon -d {base_domain} -D /usr/share/seclists/Discovery/DNS/namelist.txt -t brt"
            ]
            if self.interactive:
                web_cmds = self._interactive_tool_menu(web_cmds)
            recommended = run_layer(
                web_cmds,
                -1,
                self.llm_client,
                self.base_dir,
                self.records,
                self.interactive,
            )
            self.add_commands(recommended, 0)
        else:
            raise ValueError("target_mode must be 'host' or 'website'")

        # Run additional workflow layers as specified
        for i in range(steps):
            cmds = self.records.commands[i]
            new_recs = run_layer(
                cmds, i, self.llm_client, self.base_dir, self.records, self.interactive
            )
            self.add_commands(new_recs, i + 1)

        # If any services were found, run SearchSploit for CVE discovery
        if self.records.services:
            run_searchsploit(self.records.services, self.base_dir)

        # Generate executive summary and export to PDF
        self.llm_client.executive_summary(self.target)
        export_summary_to_pdf(self.base_dir)
