"""
Records management for Hawx Recon Agent.

Tracks executed commands, discovered services, and available tools for the recon workflow.
"""

import os
import yaml


class Records:
    """
    Stores and manages recon commands, discovered services, and available tools.
    Loads tool definitions from tools.yaml.
    """

    def __init__(self):
        """Initialize records for commands, services, and available tools."""
        # List of command lists for each workflow layer
        self.commands = [[], [], [], []]
        # List of discovered services (e.g., 'apache 2.4.41')
        self.services = []
        # Path to the YAML file containing tool definitions
        self.tools_yaml_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "configs", "tools.yaml")
        # List of all available tools (apt, pip, custom)
        self.available_tools = self.get_tools()

    def get_tools(self):
        """Load tool definitions from the YAML file."""
        # Load tool definitions from the YAML file
        with open(self.tools_yaml_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        tools = []
        # Add system and Python tools
        for section in ["apt", "pip"]:
            tools.extend(config.get(section, []))

        # Add custom tools (keys only)
        tools.extend(config.get("custom", {}).keys())
        return tools
