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

    def __init__(self, llm_client, target, interactive=False):
        # LLM client for prompt generation and summarization
        self.llm_client = llm_client
        # Target machine IP or hostname
        self.target = target
        # Whether to prompt user for each command (interactive mode)
        self.interactive = interactive
        # Directory for storing recon data for this target
        self.base_dir = os.path.join("/mnt/triage", target)
        os.makedirs(self.base_dir, exist_ok=True)
        # Records object to track commands and services
        self.records = Records()

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

    def workflow(self, steps=1):
        # Start with an exhaustive nmap scan as the first layer
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
