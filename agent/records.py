import yaml


class Records:
    def __init__(self):
        self.commands = [[], [], [], []]
        self.services = []
        self.tools_yaml_path = "tools.yaml"
        self.available_tools = self.get_tools()

    def get_tools(self):
        with open(self.tools_yaml_path, "r") as f:
            config = yaml.safe_load(f)

        tools = []
        for section in ["apt", "pip"]:
            tools.extend(config.get(section, []))

        tools.extend(config.get("custom", {}).keys())
        return tools
