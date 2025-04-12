import os
import json
import subprocess
import shutil
import uuid
import records as r
import os
import time
import json
import subprocess
import uuid
from datetime import datetime

term_width = shutil.get_terminal_size((80, 20)).columns  # fallback to 80


class ReconExecutor:
    def __init__(self, llm_client, target):
        self.llm_client = llm_client
        self.target = target
        self.base_dir = os.path.join("/mnt/triage", target)
        self.records = r.Records()
        os.makedirs(self.base_dir, exist_ok=True)

    def execute(self, command, llm_client, base_dir, layer):

        tool = command[0]
        os.makedirs(base_dir, exist_ok=True)

        timestamp = datetime.utcnow().isoformat()
        output_file = os.path.join(
            base_dir, f"{tool}_{str(uuid.uuid4())[:8]}.txt")
        summary_file = os.path.join(base_dir, "summary.md")
        metadata_file = os.path.join(base_dir, "metadata.json")
        max_lines = 9

        print(f"\n\033[1;34m[+] Executing:\033[0m {' '.join(command)}")
        print("\033[1;34m[>] Running and capturing output...\033[0m")

        start_time = time.time()
        line_count = 0
        status = "success"

        try:
            with open(output_file, "w", encoding="utf-8") as out:
                process = subprocess.Popen(
                    command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
                )
                for line in process.stdout:
                    out.write(line)

                    if line_count < max_lines:
                        print(line, end='')
                    elif line_count == max_lines:
                        print("\033[1;33m[>] Output truncated...\033[0m")
                    else:
                        print(
                            f"\033[1;33m[>] ...{line_count - max_lines + 1} lines hidden\033[0m", end='\r')

                    line_count += 1

                process.wait(timeout=300)

        except subprocess.TimeoutExpired:
            status = "timeout"
            process.terminate()
            with open(output_file, "a", encoding="utf-8") as out:
                out.write("Process terminated due to 5-minute timeout\n")
            print(
                "\033[1;31m[!] Process terminated due to 5-minute timeout\033[0m")
            return []

        except Exception as e:
            status = f"error: {str(e)}"
            print(f"\033[1;31m[!] Error running {tool}:\033[0m {e}")
            return []

        duration = round(time.time() - start_time, 2)
        print(f"\n\033[1;34m[>] Parsing results and calling LLM...\033[0m")
        resp = llm_client.post_step(command, output_file)

        # Save metadata
        metadata_entry = {
            "tool": tool,
            "timestamp": timestamp,
            "command": command,
            "output_file": output_file,
            "execution_time": duration,
            "layer": layer
        }

        try:
            if os.path.exists(metadata_file):
                with open(metadata_file, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
            else:
                metadata = []

            metadata.append(metadata_entry)

            with open(metadata_file, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)
        except Exception as e:
            print(f"\033[1;31m[!] Failed to write metadata: {e}\033[0m")

        # Print results
        print("\033[1;32m[>] LLM Response:\033[0m")
        print("\n--- Summary ---")
        print(resp.get("summary", "No summary provided."))

        recommended = resp.get("recommended_steps", [])
        if recommended:
            print("\n--- Recommended Next Commands ---")
            for cmd in recommended:
                print(f"- {cmd}")
        else:
            print("\n[!] No recommended steps.")

        services = resp.get("services_found", [])
        if services:
            print("\n--- Services found ---")
            for service in services:
                print(f"- {service}")
        else:
            print("\n[!] No new services found.")

        with open(summary_file, "a", encoding="utf-8") as f:
            f.write(f"## {tool}\n")
            f.write('Summary:\n' + resp['summary'] + "\nRecommended steps:\n" +
                    '\n'.join(resp['recommended_steps']) + "\n\n")

        return resp

    def run_searchsploit(self, services, base_dir):
        output_file = os.path.join(base_dir, "exploits.txt")
        with open(output_file, "a", encoding="utf-8") as f:
            for service in services:
                print(f"[*] Running searchsploit for: {service}")
                try:
                    result = subprocess.run(
                        ["searchsploit", service], capture_output=True, text=True, timeout=60
                    )
                    f.write(f"### {service} ###\n")
                    f.write(result.stdout + "\n")
                except Exception as e:
                    f.write(f"Error running searchsploit for {service}: {e}\n")

    def add_commands(self, commands, records, layer, llm_client):
        records.commands[layer] = commands
        deduplicated_commands = llm_client.deduplicate_commands(
            records.commands, layer)
        records.commands[layer] = deduplicated_commands['deduplicated_commands']

    def add_services(self, services, records):
        records.services.extend(services)

    def workflow(self, llm_client, target, steps=1):
        base_dir = self.base_dir
        records = self.records

        nmap_command = ["nmap", "-sC", "-sV", "-p-", target]
        response = self.execute(nmap_command, llm_client, base_dir, 4)

        if isinstance(response, dict):
            recommended_steps = response.get("recommended_steps", [])
            self.add_commands(recommended_steps, records, 0, llm_client)
            services = response.get("services_found", [])
            self.add_services(services, records)

        for i in range(0, steps):
            current_recommended_commands = []
            for cmd in records.commands[i]:
                print("\n" + "=" * term_width + "\n")
                command = cmd.split()
                command = llm_client.get_corrected_command(command)
                result = self.execute(command, llm_client, base_dir, i)
                if isinstance(result, dict):
                    current_recommended_commands.extend(
                        result.get("recommended_steps", []))
                    self.add_services(result.get(
                        "services_found", []), records)
            self.add_commands(current_recommended_commands,
                              records, i+1, llm_client)
        print('[*] Executing searchsploit with ', records.services)
        if records.services:
            self.run_searchsploit(list(set(records.services)), base_dir)

        llm_client.executive_summary(target)
