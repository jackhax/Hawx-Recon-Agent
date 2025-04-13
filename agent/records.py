class Records:
    def __init__(self):
        self.commands = [[], [], [], []]
        self.services = []
        self.available_tools = self.get_tools()

    def get_tools(self):
        return [
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
            "nikto",
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
            "unzip",
            "iproute2",
            "net-tools",
            "traceroute",
            "netcat-traditional",
        ]
