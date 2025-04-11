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

---

## Architecture

```text
[Host]
└── start_agent.sh
    ├── Parses flags (IP, --ovpn, --steps, etc.)
    ├── Launches Docker container
    │   ├── Mounts current directory to /mnt
    │   └── Passes env vars
    ↓

[Inside Docker Container]
└── entrypoint.sh
    ├── Starts OpenVPN if provided
    ├── Verifies target connectivity
    ├── Maps hostname if specified
    └── Launches agent.py

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

## Usage

### 1. Prepare Environment

- Docker installed
- `.env` file in repo root:

```env
LLM_API_KEY=your_key
LLM_PROVIDER=groq
MODEL=qwen-2.5-coder-32b
```

### 2. Run the Agent

```bash
./start_agent.sh [--steps N] [--ovpn file.ovpn] [--hostname NAME] <target_ip/domain>
```

Examples:

```bash
./start_agent.sh 192.168.1.10
./start_agent.sh --steps 2 --ovpn vpn.ovpn --hostname target 192.168.1.10
```

---

## Flags

| Flag          | Description                                      |
|---------------|--------------------------------------------------|
| `--steps`     | Number of recon layers (default: 1, max: 3)      |
| `--ovpn`      | OpenVPN config file                              |
| `--hostname`  | Add target to `/etc/hosts` as `hostname.local`   |
| `--force-build` | Rebuild Docker image before execution         |
| `--help`      | Show usage help                                  |

---

## Roadmap

- 🔬 Add `nuclei`, `wpscan`, and brute-force modules
- 🧾 PDF export via Pandoc
- 📊 JSON + HTML output formats
- 🕵️ Passive recon plugin support

---

## License

MIT License – use freely, responsibly, and at your own risk.