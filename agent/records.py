class Records:
    def __init__(self):
        self.commands = [[], [], [], []]
        self.services = []
        self.available_tools = self.get_tools()

    def get_tools(self):
        return [
            "openvpn",
            "nmap",
            "gobuster",
            "ffuf",
            "httpie",
            "whatweb",
            "wpscan",
            "dnsutils",
            "dig",
            "dnsrecon",
            "smtp-user-enum",
            "swaks",
            "lftp",
            "ftp",
            "hydra",
            "onesixtyone",
            "snmp",
            "snmpcheck",
            "smbclient",
            "smbmap",
            "enum4linux",
            "rpcbind",
            "nbtscan",
            "seclists",
            "curl",
            "wget",
            "git",
            "unzip",
            "iproute2",
            "net-tools",
            "traceroute",
            "python3",
            "python3-pip",
            "golang",
            "netcat-traditional",
        ]
