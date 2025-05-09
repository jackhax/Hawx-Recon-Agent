"""
Command runner for Hawx Recon Agent workflow layers.

Executes a list of recon commands for a given layer, supports interactive modification,
and collects recommended next steps and discovered services.
"""

import readline  # Add this at the top
import shlex
from workflow.output import execute_command


def run_layer(commands, layer_index, llm_client, base_dir, records, interactive=False):
    # Run all commands for a given workflow layer, optionally interactively
    current_recommended = []
    print(
        f"\n\033[1;36m[***] Starting Layer {layer_index} with {len(commands)} command(s)\033[0m\n"
    )

    skip_prompt = False  # Flag for "yes to all"

    for idx, cmd in enumerate(commands):
        print(f"\033[1;34m[>] Command [{idx+1}/{len(commands)}]: {cmd}\033[0m")

        # Interactive prompt for user approval/modification of each command
        if interactive and not skip_prompt:
            while True:
                user_input = input(
                    "\033[1;33m    Run? [Enter = yes | m = modify | s = skip | Y = yes to all] > \033[0m"
                ).strip()
                if user_input == "":
                    break  # proceed
                elif user_input.lower() == "s":
                    print("    ⏩ Skipping.\n")
                    cmd = None
                    break
                elif user_input.lower() == "m":
                    # Allow user to modify the command before execution
                    def prefill_hook():
                        readline.insert_text(cmd)
                        readline.redisplay()

                    readline.set_pre_input_hook(prefill_hook)
                    try:
                        new_cmd = input("    Modify command: ").strip()
                    finally:
                        readline.set_pre_input_hook()  # Clear hook
                    if new_cmd:
                        cmd = new_cmd
                        break
                elif user_input == "Y":
                    skip_prompt = True
                    break
                else:
                    print("    Invalid input. Try again.")

        if not cmd:
            continue  # Skip if command was skipped

        parts = shlex.split(cmd)

        # Run the command and post-process (log, summarize, etc.)
        resp = execute_command(parts, llm_client, base_dir, layer_index)
        if isinstance(resp, dict):
            # Collect recommended next steps and discovered services
            current_recommended.extend(resp.get("recommended_steps", []))
            records.services.extend(resp.get("services_found", []))

        print(f"\033[1;32m[✓] Done: {cmd}\033[0m\n")

    return current_recommended
