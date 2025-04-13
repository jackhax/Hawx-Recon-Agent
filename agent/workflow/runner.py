from workflow.output import execute_command


def run_layer(commands, layer_index, llm_client, base_dir, records, threads=None):
    current_recommended = []

    print(
        f"\n\033[1;36m[***] Starting Layer {layer_index} with {len(commands)} command(s)\033[0m\n"
    )

    for idx, cmd in enumerate(commands):
        print(f"\033[1;34m[>] Running [{idx+1}/{len(commands)}]: {cmd}\033[0m")
        parts = cmd.split()

        # if "nmap -sC -sV -p-" not in cmd:
        #     parts = llm_client.get_corrected_command(parts)

        # Run and post-process (log, summarize, etc.)
        resp = execute_command(parts, llm_client, base_dir, layer_index)
        if isinstance(resp, dict):
            current_recommended.extend(resp.get("recommended_steps", []))
            records.services.extend(resp.get("services_found", []))

        print(f"\033[1;32m[✓] Done: {cmd}\033[0m\n")

    return current_recommended
