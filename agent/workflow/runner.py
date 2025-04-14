import readline  # Add this at the top
import shlex
from workflow.output import execute_command


def run_layer(commands, layer_index, llm_client, base_dir, records, interactive=False):
    current_recommended = []

    print(
        f"\n\033[1;36m[***] Starting Layer {layer_index} with {len(commands)} command(s)\033[0m\n"
    )

    for idx, cmd in enumerate(commands):
        print(f"\033[1;34m[>] Command [{idx+1}/{len(commands)}]: {cmd}\033[0m")

        # Interactive prompt
        if interactive:
            while True:
                user_input = input(
                    "\033[1;33m    Run? [Enter = yes | m = modify | s = skip] > \033[0m"
                ).strip().lower()
                if user_input == "":
                    break  # proceed
                elif user_input == "s":
                    print("    ⏩ Skipping.\n")
                    cmd = None
                    break
                elif user_input == "m":
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
                else:
                    print("    Invalid input. Try again.")

        if not cmd:
            continue

        parts = shlex.split(cmd)

        # Run and post-process (log, summarize, etc.)
        resp = execute_command(parts, llm_client, base_dir, layer_index)
        if isinstance(resp, dict):
            current_recommended.extend(resp.get("recommended_steps", []))
            records.services.extend(resp.get("services_found", []))

        print(f"\033[1;32m[✓] Done: {cmd}\033[0m\n")

    return current_recommended
