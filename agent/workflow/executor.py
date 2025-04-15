import os
from workflow.runner import run_layer
from workflow.output import run_searchsploit
from records import Records
from workflow.output import export_summary_to_pdf


class ReconExecutor:
    def __init__(self, llm_client, target, interactive=False):
        self.llm_client = llm_client
        self.target = target
        self.interactive = interactive
        self.base_dir = os.path.join("/mnt/triage", target)
        os.makedirs(self.base_dir, exist_ok=True)
        self.records = Records()

    def add_commands(self, commands, layer):
        self.records.commands[layer] = commands
        deduped = self.llm_client.deduplicate_commands(self.records.commands, layer)
        final = deduped.get("deduplicated_commands", commands)
        self.records.commands[layer] = final

    def add_services(self, services):
        self.records.services.extend(services)

    def workflow(self, steps=1):
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

        for i in range(steps):
            cmds = self.records.commands[i]
            new_recs = run_layer(
                cmds, i, self.llm_client, self.base_dir, self.records, self.interactive
            )
            self.add_commands(new_recs, i + 1)

        if self.records.services:
            run_searchsploit(self.records.services, self.base_dir)

        self.llm_client.executive_summary(self.target)
        export_summary_to_pdf(self.base_dir)
