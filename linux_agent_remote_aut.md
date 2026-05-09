# About
Site24x7 Linux agent remote agent automation 
## Requirements:

- **python**
- **pip**
- **paramiko** 
- **sshd service**


##  Configuration Files 
- **servers.csv** - Maintains the credentials of remote servers.
- **remote_automation.cfg** -  Maintains the paths and agent installation url.
- **agent_install_input.json** - Maintains the agent installation params for the remote servers.
 
##  Usage 
Execute the below command to start agent automation in the configured remote servers.

    python3 linux_agent_remote_aut.py

By default, created folders and files will be cleared in the remote server after execution. If you want to keep them, use the --no-cleanup argument to the script.

    
    python3 linux_agent_remote_aut.py --no-cleanup