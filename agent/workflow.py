import os
import json
import uuid
import time
import threading
import subprocess
import shutil
import concurrent.futures
import contextlib
from datetime import datetime
import records  # your records.py module

term_width = shutil.get_terminal_size((80, 20)).columns  # fallback to 80


def print_banner():
    print(
        r"""
██╗  ██╗ █████╗ ██╗    ██╗██╗  ██╗
██║  ██║██╔══██╗██║    ██║╚██╗██╔╝
███████║███████║██║ █╗ ██║ ╚███╔╝ 
██╔══██║██╔══██║██║███╗██║ ██╔██╗ 
██║  ██║██║  ██║╚███╔███╔╝██╔╝ ██╗
╚═╝  ╚═╝╚═╝  ╚═╝ ╚══╝╚══╝ ╚═╝  ╚═╝

 H A W X | LLM-based Autonomous Recon Agent ⚡
    """
    )


class ReconExecutor:
    def __init__(self, llm_client, target, threads=3):
        """
        :param llm_client: your LLM client instance
        :param target: IP or hostname
        :param threads: how many concurrent commands to run
        """
        self.llm_client = llm_client
        self.target = target
        self.threads = threads
        self.base_dir = os.path.join("/mnt/triage", target)
        os.makedirs(self.base_dir, exist_ok=True)

        # Holds commands, services, etc. from records.py
        self.records = records.Records()

    def execute(self, command_parts, llm_client, base_dir, layer):
        """
        Executes a command fully silently:
        - Writes entire stdout/stderr to a log file
        - Returns the LLM post_step response (dict) or empty list
        """
        tool = command_parts[0]
        os.makedirs(base_dir, exist_ok=True)
        os.makedirs(os.path.join(base_dir, "logs"), exist_ok=True)

        timestamp = datetime.utcnow().isoformat()
        output_file = os.path.join(
            base_dir, "logs", f"{tool}_{uuid.uuid4().hex[:8]}.txt"
        )
        metadata_file = os.path.join(base_dir, "metadata.json")

        start_time = time.time()
        try:
            with open(output_file, "w", encoding="utf-8") as out:
                process = subprocess.Popen(
                    command_parts,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                for line in process.stdout:
                    out.write(line)
                # Hard cap 300s total
                process.wait(timeout=300)

        except subprocess.TimeoutExpired:
            process.terminate()
            with open(output_file, "a", encoding="utf-8") as out:
                out.write("Process terminated due to 5-minute timeout\n")
            return []

        except Exception:
            # If anything else goes wrong, we just return empty
            return []

        duration = round(time.time() - start_time, 2)

        resp = llm_client.post_step(command_parts, output_file)
        if not isinstance(resp, dict):
            return []

        # Write metadata
        meta_entry = {
            "tool": tool,
            "timestamp": timestamp,
            "command": command_parts,
            "output_file": output_file,
            "execution_time": duration,
            "layer": layer,
        }
        try:
            if os.path.exists(metadata_file):
                with open(metadata_file, "r", encoding="utf-8") as mf:
                    existing_meta = json.load(mf)
            else:
                existing_meta = []
            existing_meta.append(meta_entry)
            with open(metadata_file, "w", encoding="utf-8") as mf:
                json.dump(existing_meta, mf, indent=2)
        except:
            pass

        # === NEW PART: Write both Markdown and JSON ===
        summary_text = resp.get("summary", "")
        recommended = resp.get("recommended_steps", [])
        services_found = resp.get("services_found", [])

        # 1) Append results to summary.md
        summary_file = os.path.join(base_dir, "summary.md")
        try:
            with open(summary_file, "a", encoding="utf-8") as sf:
                sf.write(f"## {tool}\n\n")
                sf.write("**Summary**\n\n")
                sf.write(summary_text + "\n\n")

                sf.write("**Recommended Steps**\n")
                for step in recommended:
                    sf.write(f"- {step}\n")
                sf.write("\n")

                sf.write("**Services Found**\n")
                if services_found:
                    for svc in services_found:
                        sf.write(f"- {svc}\n")
                else:
                    sf.write("- None\n")
                sf.write("\n\n")
        except:
            pass

        # 2) Also store results in summary_data.json as a list of objects
        json_data_file = os.path.join(base_dir, "summary_data.json")
        tool_data = {
            "tool": tool,
            "summary": summary_text,
            "recommended_steps": recommended,
            "services_found": services_found
        }

        try:
            existing_data = []
            if os.path.exists(json_data_file):
                with open(json_data_file, "r", encoding="utf-8") as jf:
                    existing_data = json.load(jf)

            existing_data.append(tool_data)
            with open(json_data_file, "w", encoding="utf-8") as jf:
                json.dump(existing_data, jf, indent=2)
        except:
            pass

        return resp

    def add_commands(self, commands, records_obj, layer, llm_client):
        """
        Insert commands into records_obj and deduplicate them.
        """
        records_obj.commands[layer] = commands
        deduped = llm_client.deduplicate_commands(records_obj.commands, layer)
        records_obj.commands[layer] = deduped["deduplicated_commands"]

    def add_services(self, services, records_obj):
        """
        Merge discovered services into records_obj.
        """
        records_obj.services.extend(services)

    def run_searchsploit(self, services, base_dir):
        """
        Logs searchsploit results to exploits.txt, no console prints.
        """
        output_file = os.path.join(base_dir, "exploits.txt")
        with open(output_file, "a", encoding="utf-8") as f:
            for svc in services:
                try:
                    result = subprocess.run(
                        ["searchsploit", svc],
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
                    f.write(f"### {svc} ###\n")
                    f.write(result.stdout + "\n")
                except Exception as e:
                    f.write(f"Error running searchsploit for {svc}: {e}\n")

    def _run_layer(self, commands, layer_index):
        """
        Runs a 'layer' of commands with single-line live tail per command,
        plus idle/total timeouts. Updates recommended steps & discovered
        services in real time. Returns the collected recommended commands
        for the next layer.
        """
        lock = threading.Lock()
        shutdown_event = threading.Event()
        current_recommended = []

        # Build a status dictionary: ID -> info
        status = {}
        for idx, cmd in enumerate(commands):
            cmd_id = f"L{layer_index}:{idx}"
            status[cmd_id] = {
                "state": "pending",
                "cmd": cmd,
                "line_count": 0,
                "last_line": "",
            }

        def run_command(cmd_id):
            with lock:
                status[cmd_id]["state"] = "running"

            raw_cmd = status[cmd_id]["cmd"]
            parts = raw_cmd.split()
            parts = self.llm_client.get_corrected_command(parts)

            # Start the process, with no stdin

            try:
                process = subprocess.Popen(
                    parts,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    stdin=subprocess.DEVNULL
                )
            except FileNotFoundError:
                with lock:
                    status[cmd_id]["state"] = "error"
                return  # skip post-processing

            IDLE_TIMEOUT = 30   # kill if no new lines for 30s
            TOTAL_TIMEOUT = 600  # kill if entire command takes 10min

            line_count = 0
            last_output_time = time.time()
            start_time = last_output_time

            try:
                while True:
                    # Attempt to read one line (non-blocking style)
                    line = process.stdout.readline()
                    if not line:
                        # No data at this moment
                        if process.poll() is not None:
                            # Process ended
                            break

                        now = time.time()
                        # If we exceed total runtime
                        if now - start_time > TOTAL_TIMEOUT:
                            process.terminate()
                            with lock:
                                status[cmd_id]["state"] = "error"
                            return

                        # If we exceed idle runtime
                        if now - last_output_time > IDLE_TIMEOUT:
                            process.terminate()
                            with lock:
                                status[cmd_id]["state"] = "error"
                            return

                        time.sleep(0.25)
                        continue

                    # We got a line of output
                    line_count += 1
                    snippet = line[:60].rstrip()

                    with lock:
                        status[cmd_id]["line_count"] = line_count
                        status[cmd_id]["last_line"] = snippet[:50]

                    last_output_time = time.time()

                # Process ended normally (no manual kill)
                resp = self.execute(parts, self.llm_client,
                                    self.base_dir, layer_index)
                if isinstance(resp, dict):
                    current_recommended.extend(
                        resp.get("recommended_steps", []))
                    self.add_services(
                        resp.get("services_found", []), self.records)

                with lock:
                    status[cmd_id]["state"] = "done"

            except Exception:
                # Catch all unexpected issues and mark error
                with lock:
                    status[cmd_id]["state"] = "error"

        def status_printer():
            """
            Displays [PENDING|RUNNING|DONE|ERROR] plus the last line snippet for each command,
            until all commands are done or error.
            """
            try:
                while not shutdown_event.is_set():
                    with lock:
                        print("\033c", end="")  # Clear screen
                        print_banner()
                        print(
                            f"=== Layer {layer_index} :: Command Status ===\n")
                        for cid, info in sorted(status.items()):
                            st = info["state"].upper()
                            cmd_text = info["cmd"]
                            line_ct = info["line_count"]
                            last_line = info["last_line"]

                            color_map = {
                                "PENDING": "\033[90m",
                                "RUNNING": "\033[34m",
                                "DONE": "\033[32m",
                                "ERROR": "\033[31m",
                            }
                            color = color_map.get(st, "\033[0m")
                            print(
                                f"{color}[{cid}][{st:>7}] {cmd_text} "
                                f"({line_ct}: {last_line})\033[0m"
                            )
                    # Check if all commands are done or error
                    with lock:
                        done_count = sum(
                            1 for v in status.values() if v["state"] in ("done", "error")
                        )
                        if done_count == len(status):
                            break

                    time.sleep(0.5)
            except ValueError:
                # Happens if stdout is closed early; ignore
                pass

        # Start the status printer
        printer = threading.Thread(target=status_printer, daemon=True)
        printer.start()

        # Run commands in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.threads) as executor:
            futures = [executor.submit(run_command, cid) for cid in status]
            for f in concurrent.futures.as_completed(futures):
                f.result()  # raise any exception in main thread

        # All commands done, stop the printer
        shutdown_event.set()
        printer.join()

        return current_recommended

    def workflow(self, steps=1):
        """
        Example workflow that:
        1) Baseline Nmap as layer -1,
        2) Runs user-specified number of steps,
        3) Merges recommended commands each layer,
        4) Runs searchsploit if we found services,
        5) Prints final summary from the LLM
        """

        # Baseline layer -1
        nmap_cmds = [f"nmap -sC -sV -p- {self.target}"]
        recommended_from_nmap = self._run_layer(nmap_cmds, -1)
        self.add_commands(recommended_from_nmap,
                          self.records, 0, self.llm_client)

        # For each step
        for i in range(steps):
            layer_cmds = self.records.commands[i]
            new_recs = self._run_layer(layer_cmds, i)
            self.add_commands(new_recs, self.records, i + 1, self.llm_client)

        # If any services discovered, run searchsploit
        if self.records.services:
            self.run_searchsploit(
                list(set(self.records.services)), self.base_dir)

        # Final summary
        self.llm_client.executive_summary(self.target)
