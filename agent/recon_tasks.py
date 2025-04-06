import subprocess
import os


import subprocess
import os


def nmap_scan(machine_ip, output_dir="/mnt/nmap_reports"):
    """
    Run an Nmap scan on the given machine IP, saving the result in XML format.
    :param machine_ip: Target machine IP to scan.
    :param output_dir: Directory where the Nmap XML report will be saved.
    :return: Path to the saved Nmap XML report.
    """
    # Ensure the output directory exists
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Define the output file path
    output_file = os.path.join(
        output_dir, f"nmap_scan_{machine_ip.replace('.', '_')}.xml")

    # Print output path for debugging
    print(f"[+] Saving Nmap output to: {output_file}")

    # Define the Nmap command with the necessary options
    nmap_command = [
        "nmap", "-sC", "-sV", "-oX", output_file, machine_ip
    ]

    try:
        # Run the Nmap command using subprocess
        log_file = os.path.join(
            output_dir, f"nmap_scan_{machine_ip.replace('.', '_')}_log.txt")
        with open(log_file, "w") as log:
            # Run the Nmap command using subprocess and capture stdout and stderr in the log file
            subprocess.run(nmap_command, check=True,
                           stdout=log, stderr=subprocess.STDOUT)
        print(f"[+] Nmap scan completed. Results saved to {output_file}")
        return output_file
    except subprocess.CalledProcessError as e:
        print(f"[!] Error running Nmap scan: {e}")
        return None
