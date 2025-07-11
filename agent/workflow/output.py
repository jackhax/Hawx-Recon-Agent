"""
Output and reporting utilities for Hawx Recon Agent.

Handles command execution, output logging, summary generation, SearchSploit integration,
and PDF expo            # For layer 0 (initial scan), use 5x timeout
            if layer == 0:
                timeout = timeout * 5of executive summaries.
"""

import os
import json
import uuid
import time
import subprocess
from datetime import datetime
import shutil
import yaml
import re
import shlex


def print_banner():
    """Print the ASCII art banner for branding and user feedback."""
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


term_width = shutil.get_terminal_size((80, 20)).columns

# Global cache for filter patterns (now compiled regex)
_filter_patterns = None

ansi_escape = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def clean_line(line):
    """Remove ANSI escape codes and non-printable/control characters except newline and tab."""
    line = ansi_escape.sub("", line)
    line = "".join(c for c in line if c.isprintable() or c in "\n\t")
    return line


def load_filter_patterns():
    """Load and compile regex filter patterns from configs/filter.yaml."""
    global _filter_patterns
    if _filter_patterns is not None:
        return _filter_patterns
    filter_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "../configs", "filter.yaml"
    )
    if not os.path.exists(filter_path):
        _filter_patterns = {}
        return _filter_patterns
    with open(filter_path, "r", encoding="utf-8") as f:
        raw_patterns = yaml.safe_load(f) or {}
    _filter_patterns = {}
    for tool, patterns in raw_patterns.items():
        _filter_patterns[tool] = [re.compile(pat) for pat in patterns]
    return _filter_patterns


def should_filter_line(tool, line):
    """Return True if the line should be filtered for the given tool."""
    patterns = load_filter_patterns().get(tool, [])
    for regex in patterns:
        if regex.search(line):
            return True
    return False


def filter_log_for_llm(tool, log_text):
    """Filter log lines for a given tool using filter.yaml patterns (for LLM input only)."""
    patterns = load_filter_patterns().get(tool, [])
    filtered_lines = []
    for line in log_text.splitlines():
        if not any(regex.search(line) for regex in patterns):
            filtered_lines.append(line)
    return "\n".join(filtered_lines)


def execute_command(command_parts, llm_client, base_dir, layer):
    """Execute a single recon command and handle output, logging, and LLM summarization."""
    # Get the first part before any shell operator as the tool name
    tool = command_parts[0]
    os.makedirs(base_dir, exist_ok=True)
    os.makedirs(os.path.join(base_dir, "logs"), exist_ok=True)

    timestamp = datetime.utcnow().isoformat()
    output_file = os.path.join(base_dir, "logs", f"{tool}_{uuid.uuid4().hex[:8]}.txt")
    metadata_file = os.path.join(base_dir, "metadata.json")

    # Collect all previously executed commands for DRY logic
    previous_commands = []
    if os.path.exists(metadata_file):
        try:
            with open(metadata_file, "r", encoding="utf-8") as mf:
                meta = json.load(mf)
                for entry in meta:
                    if isinstance(entry, dict) and "command" in entry:
                        # Flatten command list to string for DRY
                        previous_commands.append(" ".join(entry["command"]))
        except Exception:
            pass

    start_time = time.time()
    try:
        with open(output_file, "w", encoding="utf-8") as out:
            # Write the executed command at the top of the file
            out.write(
                f"# Command: {' '.join(shlex.quote(part) for part in command_parts)}\n\n"
            )

            # Check if command contains shell operators and execute accordingly
            use_shell = any(
                op in " ".join(command_parts) for op in ["&&", "||", "|", ";", ">", "<"]
            )

            if use_shell:
                # If shell operators are present, join command parts and run with shell=True
                cmd = " ".join(command_parts)
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    text=True,
                    shell=True,
                )
            else:
                # Otherwise run as array of args without shell
                process = subprocess.Popen(
                    command_parts,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    text=True,
                )

            last_line = ""
            last_update = time.time()
            # Get inactivity timeout from environment (seconds)
            try:
                timeout = int(os.environ.get("TIMEOUT", "180"))
            except ValueError:
                timeout = 180

            # For layer 1 (initial scan), use 5x timeout
            if layer == 1:
                timeout = timeout * 5

            from select import select

            while True:
                # Wait up to 1 second for output
                rlist, _, _ = select([process.stdout], [], [], 1.0)
                # Check time since last output
                time_since_update = time.time() - last_update
                if rlist:
                    line = process.stdout.readline()
                    if not line:
                        break
                    if not should_filter_line(tool, line):
                        ascii_line = clean_line(line)
                        out.write(ascii_line)
                        out.flush()
                        last_line = ascii_line.strip()
                        last_update = time.time()
                        # Clear the line before printing new output
                        print(f"\r{' ' * (term_width-1)}\r", end="", flush=True)
                        print(f"    {last_line[:term_width - 4]}", end="", flush=True)
                else:
                    # No output in this iteration, check inactivity timeout
                    if timeout and time_since_update > timeout:
                        print(
                            f"\n[!] No output for {timeout} seconds, terminating process..."
                        )
                        process.terminate()
                        try:
                            # Give it 5 seconds to terminate gracefully
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()  # Force kill if it doesn't terminate
                        out.write(
                            f"\nProcess terminated due to {timeout}s inactivity timeout\n"
                        )
                        return []

                if process.poll() is not None:
                    break

            print()  # newline after command completes
            # Wait for process to exit if not already
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.terminate()
                out.write("\nProcess terminated after completion wait timeout\n")
                return []

    except subprocess.TimeoutExpired:
        # Handle command timeout (5 minutes)
        process.terminate()
        with open(output_file, "a", encoding="utf-8") as out:
            out.write("Process terminated due to 5-minute timeout\n")
        return []

    except Exception as exc:
        print(f"[!] Command execution error: {exc}")
        return []

    duration = round(time.time() - start_time, 2)
    # Summarize command output and recommend next steps using LLM
    # Instead of filtering at log time, filter here for LLM input only
    with open(output_file, "r", encoding="utf-8") as f:
        raw_log = f.read()
    filtered_log = filter_log_for_llm(tool, raw_log)

    # === Retrieve similar commands/summaries for LLM context ===
    similar_context = None

    resp = llm_client.post_step(
        command_parts,
        None,
        previous_commands=previous_commands,
        command_output_override=filtered_log,
        similar_context=similar_context,
    )
    if not isinstance(resp, dict):
        return []

    # === Metadata Logging ===
    meta_entry = {
        "tool": tool,
        "timestamp": timestamp,
        "command": command_parts,
        "output_file": output_file,
        "execution_time": duration,
        "layer": layer,
    }

    try:
        # Append metadata for this command to the metadata file
        if os.path.exists(metadata_file):
            with open(metadata_file, "r", encoding="utf-8") as mf:
                existing_meta = json.load(mf)
        else:
            existing_meta = []
        existing_meta.append(meta_entry)
        with open(metadata_file, "w", encoding="utf-8") as mf:
            json.dump(existing_meta, mf, indent=2)
    except Exception as exc:
        print(f"[!] Metadata logging error: {exc}")

    # === Markdown Summary ===
    summary_text = resp.get("summary", "")
    recommended = resp.get("recommended_steps", [])
    services_found = resp.get("services_found", [])

    summary_file = os.path.join(base_dir, "summary.md")
    try:
        # Append a markdown summary for this tool to the summary file
        with open(summary_file, "a", encoding="utf-8") as sf:
            sf.write(f"## {tool}\n\n")
            sf.write(
                f"**Command Executed:**\n\n    {' '.join(shlex.quote(part) for part in command_parts)}\n\n"
            )
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
    except Exception as exc:
        print(f"[!] Markdown summary error: {exc}")

    # === JSON Summary ===
    json_data_file = os.path.join(base_dir, "summary_data.json")
    tool_data = {
        "tool": tool,
        "summary": summary_text,
        "recommended_steps": recommended,
        "services_found": services_found,
    }

    try:
        # Append tool summary data to the JSON summary file
        existing_data = []
        if os.path.exists(json_data_file):
            with open(json_data_file, "r", encoding="utf-8") as jf:
                existing_data = json.load(jf)
        existing_data.append(tool_data)
        with open(json_data_file, "w", encoding="utf-8") as jf:
            json.dump(existing_data, jf, indent=2)
    except Exception as exc:
        print(f"[!] JSON summary error: {exc}")

    return resp


def run_searchsploit(services, base_dir):
    """Run SearchSploit for each discovered service and append results to exploits.txt, skipping common services unless they have a version number."""
    output_file = os.path.join(base_dir, "exploits.txt")
    COMMON_SERVICES = {
        "http",
        "https",
        "ssh",
        "ftp",
        "smtp",
        "dns",
        "smb",
        "pop3",
        "imap",
        "ntp",
        "rdp",
        "mysql",
        "mssql",
        "postgres",
        "oracle",
        "telnet",
        "ldap",
        "snmp",
        "rpc",
        "nfs",
        "kerberos",
        "dhcp",
        "vnc",
        "cups",
        "printer",
        "rsync",
        "netbios",
    }
    with open(output_file, "a", encoding="utf-8") as f:
        for svc in services:
            svc_lower = svc.lower()
            # If the service is common and does NOT have a version number, skip it
            if any(common in svc_lower for common in COMMON_SERVICES):
                # Check for a version number (e.g., 'http 2.4.41' or 'ssh 7.9p1')
                import re

                if not re.search(
                    r"\\b(?:"
                    + "|".join(COMMON_SERVICES)
                    + ")\\b\\s*[0-9]+[.0-9a-zA-Z_-]*",
                    svc_lower,
                ):
                    continue  # Skip if no version number
            try:
                result = subprocess.run(
                    ["searchsploit", svc],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                )
                f.write(f"### {svc} ###\n")
                f.write(result.stdout + "\n")
            except Exception as exc:
                f.write(f"Error running searchsploit for {svc}: {exc}\n")


def export_summary_to_pdf(base_dir):
    """Convert the executive summary markdown file to PDF using WeasyPrint."""
    md_path = os.path.join(base_dir, "summary_exec.md")
    pdf_path = os.path.join(base_dir, "summary_exec.pdf")

    if not os.path.exists(md_path):
        print("[!] Cannot export to PDF: summary_exec.md not found.")
        return

    try:
        import markdown
        from weasyprint import HTML

        with open(md_path, "r", encoding="utf-8") as f:
            md_content = f.read()
            html_content = markdown.markdown(md_content)

        HTML(string=html_content).write_pdf(pdf_path)
        print(f"[✓] PDF report generated: {pdf_path}")
    except Exception as exc:
        print(f"[!] PDF export failed: {exc}")
