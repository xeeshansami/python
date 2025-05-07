import paramiko
import os
import subprocess
from stat import S_ISDIR
import time

# SFTP connection details
hostname = '10.111.202.145'
port = 22
username = 'root'
password = 'root12'


# Configuration for fx_portal
fx_customer_config = {
    'remote_directory':     '/opt/9075_nginx_fxportalcustomer',
    'working_directory':    r'D:\JSProjects\fxPortal\fx-portal-customer',
    'local_directory':      r'D:\JSProjects\fxPortal\fx-portal-customer\dist',
    'backup_directory':     r'D:\JSProjects\fxPortal\backup\winscp_backup_customer',
    'exclude_dirs':         ['assets'],
    'git_branch':           'staging',
    'ng_build_cmd':         'npm run build:stage'
}

# Configuration for fx_portal
fx_client_config = {
    'remote_directory':     '/opt/9076_nginx_fxportalbackofice',
    'working_directory':    r'D:\JSProjects\fxPortal\fx-portal-client',
    'local_directory':      r'D:\JSProjects\fxPortal\fx-portal-client\dist',
    'backup_directory':     r'D:\JSProjects\fxPortal\backup\winscp_backup_client',
    'exclude_dirs':         ['assets'],
    'git_branch':           'staging',
    'ng_build_cmd':         'npm run build:stage'
}

# Group configurations into an array
configs = {
    '1': ('FX_Portal_customer', fx_customer_config),
    '2': ('FX_Portal_client', fx_client_config),
}


def run_command(command, cwd=None):
    """Run a shell command and check if it was successful. If not, stop the script."""
    try:
        result = subprocess.run(command, shell=True, cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"Command '{command}' executed successfully.")
        print("Output:", result.stdout.decode())
        return result
    except subprocess.CalledProcessError as e:
        print(f"Error executing command '{command}': {e.stderr.decode()}")
        exit(1)  # Stop the script if any command fails





def setup_local_environment(config):
    """Run Git and NPM setup commands."""
    print(f"Navigating to the working directory: {config['working_directory']}...")

    # Git checkout to the branch specified in the config
    print(f"Checking out to '{config['git_branch']}' branch...")
    run_command(f"git checkout {config['git_branch']}", cwd=config['working_directory'])

    # Git pull with rebase
    print("Pulling latest changes with rebase...")
    run_command("git pull --rebase", cwd=config['working_directory'])

    # Build Angular frontend using the command from the config
    print(f"Building Angular frontend with command: {config['ng_build_cmd']}... Please wait.")
    run_command(config['ng_build_cmd'], cwd=config['working_directory'])




def connect_sftp(config):
    """Establish an SFTP connection."""
    try:
        transport = paramiko.Transport((hostname, port))
        transport.connect(username=username, password=password)
        sftp = paramiko.SFTPClient.from_transport(transport)
        return sftp
    except Exception as e:
        print(f"Error connecting to SFTP server: {e}")
        exit(1)




def backup_remote_folders(sftp, config):
    """Backup the remote folder, excluding specified directories."""
    try:
        timestamp = time.strftime("%Y%m%d")  # Backup folder name based on date
        local_backup_root = os.path.join(config['backup_directory'], timestamp)

        # Ensure unique backup folder name
        folder_name = local_backup_root
        counter = 1
        while os.path.exists(folder_name):
            folder_name = f"{local_backup_root}_{counter}"
            counter += 1
        
        os.makedirs(folder_name, exist_ok=True)
        print(f"Backup folder created: {folder_name}")

        # Start the backup process
        copy_folder_contents_from_sftp(sftp, config['remote_directory'], folder_name, config['exclude_dirs'])

    except Exception as e:
        print(f"Error during backup: {e}")
        exit(1)




def copy_folder_contents_from_sftp(sftp, remote_folder_path, local_folder_path, exclude_dirs):
    """Recursively copy all contents from the remote folder to the local backup folder."""
    try:
        for item in sftp.listdir_attr(remote_folder_path):
            remote_item_path = remote_folder_path + '/' + item.filename
            local_item_path = os.path.join(local_folder_path, item.filename)

            # If it's a directory and should be excluded, skip it
            if S_ISDIR(item.st_mode):
                if item.filename in exclude_dirs:
                    print(f"Skipping directory: {remote_item_path} (excluded)")
                    continue
                os.makedirs(local_item_path, exist_ok=True)
                copy_folder_contents_from_sftp(sftp, remote_item_path, local_item_path, exclude_dirs)
            else:
                print(f"Copying file from remote: {remote_item_path} to local: {local_item_path}")
                sftp.get(remote_item_path, local_item_path)
                os.utime(local_item_path, (item.st_atime, item.st_mtime))  # Preserve timestamps

    except Exception as e:
        print(f"Error copying folder contents: {e}")
        exit(1)




def delete_files(sftp, remote_path):
    """Delete all files in the given remote directory (excluding directories)."""
    try:
        for file_attr in sftp.listdir_attr(remote_path):
            remote_file_path = remote_path + '/' + file_attr.filename
            if not S_ISDIR(file_attr.st_mode):
                print(f"Deleting file: {remote_file_path}")
                sftp.remove(remote_file_path)
    except Exception as e:
        print(f"Error deleting files: {e}")
        exit(1)




def copy_local_files(sftp, local_path, remote_path):
    """Copy all files from the local directory to the remote directory."""
    try:
        for filename in os.listdir(local_path):
            local_file_path = os.path.join(local_path, filename)
            if os.path.isfile(local_file_path):
                remote_file_path = os.path.join(remote_path, filename).replace(os.sep, '/')
                print(f"Copying file: {local_file_path} to {remote_file_path}")
                sftp.put(local_file_path, remote_file_path)
                local_mtime = os.path.getmtime(local_file_path)
                sftp.utime(remote_file_path, (local_mtime, local_mtime))  # Preserve modification time
    except Exception as e:
        print(f"Error copying files: {e}")
        exit(1)





def main():
    # Loop through the config options and print them dynamically
    print("Select the project to deploy:")
    for key, (name, _) in configs.items():
        print(f"{key} - {name}")

    choice = input("Enter your choice: ")

    # Check if the selected choice is valid
    if choice in configs:
        project_name, config = configs[choice]
        print(f"You have selected the '{project_name}' client for deployment.")
    else:
        print("Invalid selection. Exiting.")
        exit(1)


     # Run the local environment setup (Git & NPM commands)
    setup_local_environment(config)

    # Connect to the SFTP server
    sftp = connect_sftp(config)

    try:
        # Change to the target directory
        sftp.chdir(config['remote_directory'])

        # Start the backup process (optional, uncomment if needed)
        backup_remote_folders(sftp, config)

        # Delete all files in the remote directory (optional)
        delete_files(sftp, config['remote_directory'])

        # Copy all files from the local directory to the remote directory
        copy_local_files(sftp, config['local_directory'], config['remote_directory'])

    finally:
        sftp.close()  # Ensure the SFTP connection is closed
        print("SFTP connection closed.")

if __name__ == '__main__':
    main()