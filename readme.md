# Hawx Recon Agent

## Overview

**Hawx Recon Agent** is an intelligent, autonomous reconnaissance system powered by a Large Language Model (LLM). Designed for offensive security workflows, it automates initial triage and guided follow-up based on live service data. The agent runs in a Dockerized environment and can optionally tunnel through OpenVPN. Output is structured, actionable, and neatly organized per target.

---

## Features

- 📡 Autonomous recon workflow
- 🤖 LLM-guided command planning and triage
- 🔍 CVE and exploit discovery using SearchSploit
- 🌐 Optional OpenVPN integration
- 🧠 Markdown summaries of recon
- 📂 Clean directory structure per target
- 🧹 Output filtering via `configs/filter.yaml` (custom regex-based noise reduction)
- 🧠 Modular codebase: `agent/llm/` (LLM logic), `agent/utils/` (utilities), `configs/` (YAML configs)
- 🌐 Hosts file injection for domain-based targeting

---

## Architecture

```text
[Host]
└── hawx.py
    ├── Parses flags (IP, --ovpn, --steps, --hosts, etc.)
    ├── Launches Docker container
    │   ├── Mounts current directory to /mnt
    │   └── Passes env vars
    ↓

[Inside Docker Container]
└── entrypoint.sh
    ├── Starts OpenVPN if provided
    ├── Verifies target connectivity
    ├── Injects custom hosts file to /etc/hosts
    └── Resolves domain from hosts file and launches agent.py

[agent.py]
├── Runs nmap on target
├── Parses and summarizes output
├── Picks follow-up tools
├── Stores all logs and recon data
└── Summarizes recon using LLM
```

---

## Agent Workflow

### 🔎 Initial Enumeration
- Nmap (`-sC -sV -p-`)
- Stores raw and structured output

### 🧠 Analysis + Planning
- LLM decides follow-up tools:
  - Web → `httpx`, `gobuster`, `nikto`
  - FTP/SSH/SMB → enumeration tools
- Deduplicates tools across layers

### 🧰 Follow-Up Tools
| Service | Toolset |
|---------|---------|
| HTTP    | httpx, gobuster, nikto |
| FTP     | ftp-anon, manual login |
| SMB     | enum4linux, smbclient |
| SSH     | Banner grab |
| SQL     | Basic login logic |
| Custom  | LLM-based tool picks |

### 🛡️ CVE Discovery
- SearchSploit per service/version
- LLM-based CVE summaries
- Output written to `exploits.txt`

### 📋 Executive Summary
- Clear Markdown (`summary.md`)
- Includes:
  - Ports/services
  - CVEs
  - Attack paths
  - Recommended tools

---

## Output Filtering with filter.yaml

You can reduce noise in tool outputs by specifying regex patterns in `configs/filter.yaml`. For each supported tool (e.g., ffuf, gobuster, nikto), add a list of regex patterns to filter out unwanted lines before logs and summaries are generated.

**Example `configs/filter.yaml`:**
```yaml
ffuf:
  - .*:: Progress:      # Filters all ffuf progress lines
gobuster:
  - ^Progress:          # Filters gobuster progress lines
nikto:
  - OSVDB               # Filters Nikto OSVDB noise
```

Patterns are applied per line, and only lines not matching any pattern are written to logs and used for summarization. This keeps your recon output clean and focused on actionable results.

---

## Directory Structure

```
triage/192.168.1.10/
├── nmap_output.txt
├── httpx_output.txt
├── gobuster.txt
├── exploits.txt
├── summary.md
└── summary_exec.md
```

---

## Setup

### 1. Install Docker
Ensure you have Docker installed and running:
```bash
sudo apt install docker.io
```

### 2. Create `.env` file with your API key
Create a `.env` file in the root of the repo:
```env
LLM_API_KEY=your_llm_api_key_here
```
> Only the API key is read from `.env`. All other config is in `configs/config.yaml`

### 3. Create `configs/config.yaml`
Create a `configs/config.yaml` in the configs directory (or mountable from outside):
```yaml
llm:
  provider: groq           # or openai, ollama
  model: qwen-2.5-coder-32b
  context_length: 8192

ollama:
  host: http://host.docker.internal:11434
```

---

## Usage

```bash
python hawx.py [--steps N] [--ovpn file.ovpn] [--hosts file.txt] [--interactive] <target>
```

- `<target>` can be an IP address, domain, or website URL (must include http:// or https:// for websites).
- The script will automatically detect if the target is a host (IP/domain) or a website.
- Example:
  ```bash
  python hawx.py 10.10.11.58
  python hawx.py dog.htb
  python hawx.py https://example.com
  python hawx.py --steps 2 --ovpn vpn.ovpn --hosts hosts.txt --interactive https://target.com
  python hawx.py --timeout 300 --test 10.10.11.58
  ```

> You can specify a hosts file like:
> ```
> 10.10.11.58 dog.htb
> ```
> The agent will resolve and use `dog.htb` instead of the raw IP wherever possible.

---

## LLM-Driven Workflow & Output Improvements

- The agent tracks all previously executed commands and instructs the LLM not to repeat them (DRY principle).
- The LLM is required to:
  - Only recommend commands that print directly to the console (no silent downloads or file-only output).
  - Include proof/evidence (e.g., IOC, banner, credential, etc.) for each key finding in summaries.
  - Extract service names and versions in a format suitable for SearchSploit (e.g., `apache 2.4.41`), not random strings or tool banners.
- The `summary.md` file now includes:
  - Tool name
  - Command executed
  - LLM summary (with proof)
  - Recommended next steps
  - Services found (suitable for SearchSploit)

## SearchSploit Integration

- SearchSploit is only run for non-common services, or for common services (like http, ssh, etc.) **if and only if a version number is present**.
- This reduces noise and focuses CVE lookups on actionable findings.

---

## Flags

| Flag            | Description                                                                 |
|-----------------|-----------------------------------------------------------------------------|
| `--steps`       | Number of recon layers (default: 1, max: 3)                                 |
| `--ovpn`        | OpenVPN config file                                                         |
| `--hosts`       | File to append to `/etc/hosts` inside container                             |
| `--force-build` | Rebuild Docker image before execution                                       |
| `--interactive` | Ask user's confirmation before executing recommended commands (interactive)  |
| `--test`        | Run in test mode (mounts tests/ into container)                             |
| `--timeout`     | Timeout for each command in seconds (default: 180)                          |
| `--help`        | Show usage help                                                             |

- The positional argument `<target>` is required and can be an IP address, domain, or website URL (must include http:// or https:// for websites).
- Example usage:
  ```bash
  python hawx.py 10.10.11.58
  python hawx.py dog.htb
  python hawx.py https://example.com
  python hawx.py --steps 2 --ovpn vpn.ovpn --hosts hosts.txt --interactive https://target.com
  python hawx.py --timeout 300 --test 10.10.11.58
  ```

---

## Roadmap

- 🔬 Add `nuclei`, `wpscan`, and brute-force modules
- 🧾 PDF export via Pandoc
- 📊 JSON + HTML output formats
- 🕵️ Passive recon plugin support

---

## License

MIT License – use freely, responsibly, and at your own risk.
