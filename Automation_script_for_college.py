import paramiko
import os
import csv
import requests
import time
import sys
import threading
import configparser
import traceback
import json
from datetime import datetime

CFG = None
INSTALL_PARAMS = {}

def read_config(cfg_file="bulk_install.cfg"):
    global CFG
    CFG = configparser.ConfigParser()
    CFG.read(cfg_file)
    

def read_json(json_file="agent_install_input.json"):
    global INSTALL_PARAMS
    try:
        with open(json_file, 'r') as f:
            data = json.load(f)
            INSTALL_PARAMS = data.get("install_params", {})
            log(f"Loaded install parameters for {len(INSTALL_PARAMS)} hosts from {json_file}")
    except Exception as e:
        log(f"Failed to read JSON file {json_file}: {e}")
        traceback.print_exc()


def log(message):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    thread_name = threading.current_thread().name
    padded_thread = f"{thread_name:<15}"
    print(f"{timestamp}  {padded_thread}  {message}")

def get_connection(host, user, password):
    try:
        log(f"Connecting to {host} via SSH...")
        ssh_obj = paramiko.SSHClient()
        ssh_obj.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_obj.connect(host, username=user, password=password)
        log(f"Connected to {host}")
        return ssh_obj
    except Exception as e:
        log(f"SSH connection to {host} failed: {e}")
        traceback.print_exc()
        return None

def close_connection(ssh_obj):
    try:
        if ssh_obj:
            ssh_obj.close()
            log("SSH connection closed.")
    except Exception as e:
        log(f"Error closing SSH connection: {e}")
        traceback.print_exc()

def download_agent(agent_url, local_filename):
    log(f"Checking access for: {agent_url}")
    try:
        head_response = requests.head(agent_url)
        if head_response.status_code == 401:
            log("Authentication required. Downloading with credentials...")
            response = requests.get(agent_url, auth=(CFG.get("Agent", "username"), CFG.get("Agent", "password")))
        else:
            log("No authentication required. Downloading...")
            response = requests.get(agent_url)
        response.raise_for_status()
        with open(local_filename, "wb") as f:
            f.write(response.content)
        log("Download complete.\n")
        return True
    except Exception as e:
        log(f"Error during download: {e}")
        traceback.print_exc()
        return False
        
def generate_and_transfer_install_json(host, ssh_obj, password, user, cmd):
    try:
        local_json_path = CFG.get("Paths", "local_json_path")
        
        # Dynamically get user's home directory path from config
        remote_path = CFG.get("Paths", "remote_folder").replace("{remote_username}", user)
        remote_final_path = os.path.join(remote_path, 'install_param.json')

        # Parse install args from command
        parts = cmd.strip().split()
        if 'bash' not in parts:
            raise ValueError("Command does not contain 'bash'")

        script_index = parts.index('bash') + 1
        args = parts[script_index + 1:]

        parsed = {}
        for arg in args:
            if '=' in arg:
                key, value = arg.split('=', 1)
                parsed[key] = value
            else:
                parsed[arg] = ""
                
        sftp = ssh_obj.open_sftp()
        # Ensure local directory exists
        os.makedirs(os.path.dirname(local_json_path), exist_ok=True)
        # Save JSON locally
        with open(local_json_path, 'w') as f:
            json.dump(parsed, f, indent=2)

        # Transfer to remote
        try:
            sftp.put(local_json_path, remote_final_path)
            log(f"[JSON] Moved to remote: {remote_final_path}")
        except Exception as e:
            log("error moving install_param.json to remote")
            tracebake.print_exc()
        finally:
            sftp.close()
        # Delete the file in local
        if os.path.exists(local_json_path):
            os.remove(local_json_path)
            log(f"[JSON] Deleted install_param{host}.json in local machine")

    except Exception as e:
        log(f"[JSON] Failed to generate or transfer install_param.json for {host}: {e}")
        traceback.print_exc()


def installagent(ssh_obj, host, user, password):
    remote_path = CFG.get("Paths", "remote_folder").replace("{remote_username}", user)
    local_script_path = CFG.get("Paths", "local_agent_script")
    device_key = CFG.get("Agent", "device_key")

    try:
        log(f"Creating remote folder {remote_path} ...")
        cmd = f"mkdir -p {remote_path}"
        stdin, stdout, stderr = ssh_obj.exec_command(cmd)
        stdout.channel.recv_exit_status()

        sftp = ssh_obj.open_sftp()
        remote_script_path = os.path.join(remote_path, os.path.basename(local_script_path))
        try:
            sftp.put(local_script_path, remote_script_path)
            log("agent install script moved to remote.")
        except Exception as e:
            log(f"Error during SFTP PUT (script): {e}")
            traceback.print_exc()
        sftp.close()

        cmd = f"chmod 755 {remote_script_path}"
        stdin, stdout, stderr = ssh_obj.exec_command(cmd)
        stdout.channel.recv_exit_status() 

        log("Running installer...")

        install_param = INSTALL_PARAMS.get(host, "")
        if install_param:
            log(f"Appending install parameters from JSON ")
        else:
            log(f"No additional install parameters found")

        remote_cmd = f"export TERM=xterm && echo '{password}' |" 
        install_cmd= f"sudo -S bash {remote_script_path} -i -f -key={device_key} -automation=true"
        cmd = " ".join([remote_cmd,install_cmd,install_param])
        stdin, stdout, stderr = ssh_obj.exec_command(cmd)
        exit_status = stdout.channel.recv_exit_status()
        if exit_status == 0:
            log("Installation completed successfully.")
        else:
            log(f"Installation failed with exit status: {exit_status}")
            log(stderr.read().decode())

    except Exception as e:
        log(f"Error during installation on {host}: {e}")
        traceback.print_exc()
    return cmd

def copy_automation_zip(ssh_obj, host, user, password):
    try:
        local_zip_path = CFG.get("Paths", "zip_file_to_copy")
        remote_path = CFG.get("Paths", "remote_folder").replace("{remote_username}", user)
        zip_filename = os.path.basename(local_zip_path)
        final_zip_path = os.path.join(remote_path, zip_filename)

        log(f"[ZIP] Transferring automation ZIP to {final_zip_path}...")
        sftp = ssh_obj.open_sftp()
        try:
            sftp.put(local_zip_path, final_zip_path)
        except Exception as e:
            log(f"[ZIP] Error during SFTP PUT (zip): {e}")
            traceback.print_exc()
        sftp.close()

        unzip_cmd = f"unzip -o {final_zip_path} -d {remote_path}"
        stdin, stdout, stderr = ssh_obj.exec_command(unzip_cmd)
        exit_status = stdout.channel.recv_exit_status()

        if exit_status == 0:
            log("Unzip completed successfully.")
        else:
            log(f"Unzip failed with exit status: {exit_status}")
            log(stderr.read().decode())

        log(f"[ZIP] Extraction completed.")
    except Exception as e:
        log(f"[ZIP] Error on {host}: {e}")
        traceback.print_exc()

def run_automation(ssh_obj, host, user, password):
    try:
        log(f"[RUN] waiting for 5 minutes before automation...")
        time.sleep(300)

        automation_dir = CFG.get("Paths", "automation_dir_on_remote").replace("{remote_username}", user)
        file_to_run = CFG.get("Paths", "automation_file_to_run")

        log(f"[RUN] Starting automation...")
        run_cmd = f"cd {automation_dir} && echo '{password}' | sudo -S python3 {file_to_run}"
        stdin, stdout, stderr = ssh_obj.exec_command(run_cmd)
        log(stdout.read().decode())
        exit_status = stdout.channel.recv_exit_status()

        if exit_status == 0:
            log("Automation completed successfully.")
        else:
            log(f"Automation failed with exit status: {exit_status}")
            log(stderr.read().decode())
            traceback.print_exc()

    except Exception as e:
        log(f"[RUN] Error during automation on {host}: {e}")
        traceback.print_exc()

def fetch_report_file(ssh_obj, host, user, password):
    try:
        fetch_output_dir = CFG.get("Paths", "fetch_output_dir")
        filename_prefix = CFG.get("Paths", "filename_prefix")
        automation_dir = CFG.get("Paths", "automation_dir_on_remote").replace("{remote_username}", user)

        log(f"Fetching report...")
        sftp = ssh_obj.open_sftp()
        try:
            files = sftp.listdir(automation_dir)
        except Exception as e:
            log(f"Error listing directory via SFTP: {e}")
            traceback.print_exc()
            return

        matched_files = [f for f in files if f.startswith(filename_prefix) and f.endswith('.xml')]
        if not matched_files:
            log(f"No matching XML files found...")
            return

        for filename in matched_files:
            remote_file_path = os.path.join(automation_dir, filename)
            local_path = os.path.join(fetch_output_dir, f"{host}_{filename}")
            try:
                sftp.get(remote_file_path, local_path)
                log(f"Fetched: {remote_file_path} → {local_path}")
            except Exception as e:
                log(f"Error fetching file {filename}: {e}")
                traceback.print_exc()
        sftp.close()
    except Exception as e:
        log(f"Failed to fetch report from {host}: {e}")
        traceback.print_exc()

def cleanup_remote_files(ssh_obj, host, user, password):
    try:
        remote_path = CFG.get("Paths", "remote_folder").replace("{remote_username}", user)
        log(f"[CLEANUP] Cleaning remote folder on {host}...")
        cleanup_cmd = f"rm -rf {remote_path}"
        stdin, stdout, stderr = ssh_obj.exec_command(cleanup_cmd)
        exit_status = stdout.channel.recv_exit_status()

        if exit_status == 0:
            log("Cleanup command executed successfully.")
        else:
            log(f"Cleanup failed with exit status: {exit_status}")
            log(stderr.read().decode())

        log(f"[CLEANUP] Completed...")
    except Exception as e:
        log(f"[CLEANUP] Error during cleanup on {host}: {e}")
        traceback.print_exc()

def handle_remote_machine(row, skip_cleanup=False):
    hostname = row['hostname'].strip()
    username = row['username'].strip()
    password = row['password'].strip()

    ssh_obj = get_connection(hostname, username, password)
    if not ssh_obj:
        log(f"Skipping {hostname} due to connection failure.")
        return

    sftp = None
    try:
        log(f"Starting tasks on {hostname}...")
        install_cmd = installagent(ssh_obj, hostname, username, password)
        copy_automation_zip(ssh_obj, hostname, username, password)
        
        local_json_path = CFG.get("Paths", "local_json_path")
        remote_path = CFG.get("Paths", "remote_folder").replace("{remote_username}", username)
        
        generate_and_transfer_install_json(cmd=install_cmd,host=hostname,ssh_obj=ssh_obj,password=password,user=username)
        
        run_automation(ssh_obj, hostname, username, password)
        fetch_report_file(ssh_obj, hostname, username, password)

        if not skip_cleanup:
            cleanup_remote_files(ssh_obj, hostname, username, password)
        else:
            log("Skipped cleanup.")

        log("Completed all steps.")
    except Exception as e:
        log(f"Error on {hostname}: {e}")
        traceback.print_exc()
    finally:
        if sftp:
            sftp.close()
        close_connection(ssh_obj)
        
def process_machines(skip_cleanup=False):
    agent_url = CFG.get("Agent", "url")
    local_script = CFG.get("Paths", "local_agent_script")
    csv_file = CFG.get("File", "csv_file")
    fetch_output_dir = CFG.get("Paths", "fetch_output_dir")

    if not download_agent(agent_url, local_script):
        return

    if not os.path.exists(csv_file):
        log(f"CSV file '{csv_file}' not found.")
        return

    os.makedirs(fetch_output_dir, exist_ok=True)

    with open(csv_file, newline='') as csvfile:
        reader = list(csv.DictReader(csvfile))
        threads = []

        for row in reader:
            t = threading.Thread(
                target=handle_remote_machine,
                name=row['hostname'].strip(),
                args=(row, skip_cleanup)
            )
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        log("All machines processed.")

if __name__ == "__main__":
    skip_cleanup = "--nocleanup" in sys.argv
    read_config()
    read_json()
    process_machines(skip_cleanup)
