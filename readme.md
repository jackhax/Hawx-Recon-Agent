# Hawx Recon Agent

An intelligent, autonomous reconnaissance system powered by Large Language Models (LLM) for offensive security workflows. Automates initial triage and guided follow-up based on live service data.

## 🚀 Quick Start

1. Install Docker:
   ```bash
   sudo apt install docker.io
   ```

2. Set up your environment:
   ```bash
   # Create .env file with your API key
   echo "LLM_API_KEY=your_llm_api_key_here" > .env

   # Create config.yaml
   mkdir -p configs
   cat > configs/config.yaml << EOF
   llm:
     provider: groq           # or openai, ollama
     model: qwen-2.5-coder-32b
     context_length: 8192

   ollama:
     host: http://host.docker.internal:11434
   EOF
   ```

3. Run the agent:
   ```bash
   python hawx.py <target>
   ```

## 🎯 Key Features

- 🤖 **LLM-Powered Analysis**: Intelligent command planning and triage
- 🔍 **Comprehensive Recon**: Automated service discovery and vulnerability assessment
- 🔐 **CVE Discovery**: Integrated with SearchSploit for exploit identification
- 📊 **Structured Output**: Clean, organized reports per target
- 🌐 **Flexible Targeting**: Supports IP addresses, domains, and web applications
- 🧹 **Noise Reduction**: Custom regex-based filtering via `configs/filter.yaml`
- 🔌 **VPN Support**: Optional OpenVPN integration for remote targets

## 🏗️ Architecture

```text
[Host] → hawx.py → [Docker Container] → entrypoint.sh → agent.py
                                                         ├── Initial Scan
                                                         ├── LLM Analysis
                                                         ├── Follow-up Tools
                                                         └── Report Generation
```

## 💻 Usage

```bash
python hawx.py [options] <target>
```

### Options

| Flag            | Description                                          |
|----------------|------------------------------------------------------|
| `--steps N`    | Number of recon layers (default: 1, max: 5)          |
| `--ovpn FILE`  | OpenVPN config file for remote targets               |
| `--hosts FILE` | Custom hosts file for domain resolution              |
| `--interactive`| Review commands before execution                      |
| `--timeout N`  | Global timeout multiplier                            |
| `--config FILE`| Custom layer0.yaml config path                       |
| `--test`       | Run in test mode                                     |

### Examples

```bash
# Basic usage
python hawx.py 10.10.11.58                    # IP target
python hawx.py dog.htb                        # Domain target
python hawx.py https://example.com            # Web target

# Advanced usage
python hawx.py --steps 3 --config custom_layer0.yaml 10.10.11.58
python hawx.py --interactive --timeout 1.5 https://target.edu
python hawx.py --steps 4 --ovpn vpn.ovpn --hosts hosts.txt target.com
```

## 🔄 Workflow

1. **Initial Enumeration**
   - Port scanning (nmap)
   - Service detection
   - Version identification

2. **LLM Analysis**
   - Service assessment
   - Tool selection
   - Attack path planning

3. **Follow-up Tools**
   | Service | Tools Used |
   |---------|------------|
   | HTTP    | httpx, gobuster, nikto |
   | FTP     | ftp-anon, manual checks |
   | SMB     | enum4linux, smbclient |
   | SSH     | Banner analysis |
   | SQL     | Basic auth testing |

4. **Report Generation**
   - Markdown summaries
   - CVE documentation
   - Attack path recommendations

## 📁 Output Structure

```
triage/<target>/
├── nmap_output.txt      # Initial scan results
├── httpx_output.txt     # Web service analysis
├── gobuster.txt         # Directory enumeration
├── exploits.txt        # Potential vulnerabilities
├── summary.md          # Detailed findings
└── summary_exec.md     # Executive summary
```

## ⚙️ Configuration

### Layer 0 Configuration

Customize initial reconnaissance in `configs/layer0.yaml`:

```yaml
host_mode:
  commands:
    - name: "nmap_full_scan"
      command: "nmap -sC -sV -p- {target}"
      timeout: 7200
      required: true

website_mode:
  commands:
    - name: "whatweb_scan"
      command: "whatweb {target}"
      timeout: 300
      required: true
```

### Output Filtering

Reduce noise with `configs/filter.yaml`:

```yaml
ffuf:
  - .*:: Progress:
gobuster:
  - ^Progress:
nikto:
  - OSVDB
```

## 🚀 Roadmap

- 🔬 Additional modules: nuclei, wpscan, bruteforce
- 🧾 PDF report export
- 📊 JSON/HTML output formats
- 🕵️ Passive recon capabilities

## 📄 License

MIT License – Use freely, responsibly, and at your own risk.

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute to this project.
