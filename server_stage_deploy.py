import paramiko
import subprocess
import os
from stat import S_ISDIR, ST_MTIME
import time

# SFTP connection details
hostname = '10.111.202.145' 
port = 22
username = 'root'
password = 'root12' 


# Configuration Groups
fx_portal_server = {
    'container': '9077_node_fxportal',
    'remote_directory': '/opt/9077_node_fxportal',
    'local_directory': r'D:\JSProjects\fxPortal\fx-portal-server',
    'folders_to_copy': ['routes'],
     # 'folders_to_copy': ['routes', 'util', 'functions'],
    'follow_lines': 22,
    'backup_directory': r'D:\JSProjects\fxPortal\backup\winscp_backup_server',
    'exclude_dirs': ['node_modules', 'node_modules_old','uploads_trackingId', 'uploads', 'logs'],
    'git_branch': 'staging',
}




# Config options dictionary that maps a key to (name, config)
configs = {
    '1': ('fx_portal_server', fx_portal_server),
    
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
        exit(1)





def setup_local_environment(config):
    """Run Git and NPM setup commands."""
    print(f"Navigating to the working directory: {config['local_directory']}...")

    # Git checkout
    print(f"Checking out to '{config['git_branch']}' branch...")
    run_command(f"git checkout {config['git_branch']}", cwd=config['local_directory'])

    # Git pull with rebase
    print("Pulling latest changes with rebase...")
    run_command("git pull --rebase", cwd=config['local_directory'])




def connect_sftp():
    try:
        transport = paramiko.Transport((hostname, port))
        transport.connect(username=username, password=password)
        sftp = paramiko.SFTPClient.from_transport(transport)
        return sftp
    except Exception as e:
        print(f"Error connecting to SFTP server: {e}")
        return None



def backup_remote_folders(sftp, remote_path, backup_directory, exclude_dirs=None):
    try:
        exclude_dirs = exclude_dirs or []
        timestamp = time.strftime("%Y%m%d")
        local_backup_root = os.path.join(backup_directory, timestamp)

        folder_name = local_backup_root
        counter = 1
        while os.path.exists(folder_name):
            folder_name = f"{local_backup_root}_{counter}"
            counter += 1

        os.makedirs(folder_name, exist_ok=True)
        print(f"Backup folder created: {folder_name}")
        copy_folder_contents_from_sftp(sftp, remote_path, folder_name, exclude_dirs)

    except Exception as e:
        print(f"Error during backup: {e}")
        exit(1)



def copy_folder_contents_from_sftp(sftp, remote_folder_path, local_folder_path, exclude_dirs):
    try:
        for item in sftp.listdir_attr(remote_folder_path):
            remote_item_path = remote_folder_path + '/' + item.filename
            local_item_path = os.path.join(local_folder_path, item.filename)

            remote_item_path = remote_item_path.replace(os.sep, '/')
            local_item_path = local_item_path.replace(os.sep, '/')

            if S_ISDIR(item.st_mode):
                if item.filename in exclude_dirs:
                    print(f"Skipping directory: {remote_item_path} (excluded)")
                    continue
                else:
                    print(f"Copying directory from remote: {remote_item_path} to local: {local_item_path}")
                    os.makedirs(local_item_path, exist_ok=True)
                    copy_folder_contents_from_sftp(sftp, remote_item_path, local_item_path, exclude_dirs)
            else:
                print(f"Copying file from remote: {remote_item_path} to local: {local_item_path}")
                sftp.get(remote_item_path, local_item_path)
                mtime = item.st_mtime
                atime = item.st_atime
                os.utime(local_item_path, (atime, mtime))

    except Exception as e:
        print(f"Error copying folder contents from SFTP: {e}")
        exit(1)




def delete_remote_folders(sftp, remote_path, folders_to_copy):
    try:
        for folder in sftp.listdir_attr(remote_path):
            remote_folder_path = remote_path + '/' + folder.filename
            if S_ISDIR(folder.st_mode):
                if folder.filename in folders_to_copy:
                    print(f"Deleting folder: {remote_folder_path}")
                    delete_folder_contents(sftp, remote_folder_path)
                    sftp.rmdir(remote_folder_path)
    except Exception as e:
        print(f"Error deleting folders: {e}")
        exit(1)




def delete_folder_contents(sftp, remote_folder_path):
    try:
        for file_attr in sftp.listdir_attr(remote_folder_path):
            remote_file_path = remote_folder_path + '/' + file_attr.filename
            if S_ISDIR(file_attr.st_mode):
                delete_folder_contents(sftp, remote_file_path)
                sftp.rmdir(remote_file_path)
            else:
                print(f"Deleting file: {remote_file_path}")
                sftp.remove(remote_file_path)
    except Exception as e:
        print(f"Error deleting folder contents: {e}")
        exit(1)




def create_remote_directory(sftp, remote_folder_path):
    dirs = remote_folder_path.split('/')
    path = ""
    for dir in dirs:
        path += dir + "/"
        try:
            sftp.stat(path)
        except FileNotFoundError:
            try:
                sftp.mkdir(path)
                print(f"Created folder: {path}")
            except Exception as e:
                print(f"Failed to create folder: {path}, error: {e}")
                continue




def copy_local_folders(sftp, local_path, remote_path, folders_to_copy):
    try:
        for folder_name in folders_to_copy:
            local_folder_path = os.path.join(local_path, folder_name)
            if os.path.isdir(local_folder_path):
                remote_folder_path = os.path.join(remote_path, folder_name).replace(os.sep, '/')
                create_remote_directory(sftp, remote_folder_path)
                copy_folder_contents(local_folder_path, sftp, remote_folder_path)
    except Exception as e:
        print(f"Error copying folders: {e}")
        exit(1)




def copy_folder_contents(local_folder_path, sftp, remote_folder_path):
    try:
        for item in os.listdir(local_folder_path):
            local_item_path = os.path.join(local_folder_path, item)
            remote_item_path = os.path.join(remote_folder_path, item).replace(os.sep, '/')

            if os.path.isdir(local_item_path):
                print(f"Copying directory: {local_item_path} to {remote_item_path}")
                create_remote_directory(sftp, remote_item_path)
                copy_folder_contents(local_item_path, sftp, remote_item_path)
            else:
                print(f"Copying file: {local_item_path} to {remote_item_path}")
                sftp.put(local_item_path, remote_item_path)
                mtime = os.stat(local_item_path).st_mtime
                atime = os.stat(local_item_path).st_atime
                sftp.utime(remote_item_path, (atime, mtime))

    except Exception as e:
        print(f"Error copying folder contents: {e}")
        exit(1)



def run_docker_restart_command(container, follow_lines):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname, username=username, password=password)

        stdin, stdout, stderr = ssh.exec_command(f"docker restart {container}")
        print("Docker restart command executed. Output:")
        print(stdout.read().decode())
        print("Errors (if any):")
        print(stderr.read().decode())

        print("Restarting container please wait....")
        time.sleep(5)

        stdin, stdout, stderr = ssh.exec_command(f'docker container logs --tail {follow_lines} {container}')
        print(f"Docker container logs (last {follow_lines} lines):")
        print(stdout.read().decode())
        print("Errors (if any):")
        print(stderr.read().decode())

        ssh.close()
    except Exception as e:
        print(f"Error running Docker restart command: {e}")
        exit(1)




def main():

    # Loop through the config options and print them dynamically
    print("Select the project to deploy:")
    for key, (name, _) in configs.items():
        print(f"{key} - {name}")

    choice = input("Enter your choice: ")

    # Early return if the selected choice is invalid
    if choice not in configs:
        print("Invalid selection. Exiting.")
        return  # Early return
    
     # If valid choice, proceed with the deployment
    project_name, config = configs[choice]
    print(f"You have selected the '{project_name}' for deployment.")

    # Run the local environment setup (Git & NPM commands)
    setup_local_environment(config)

    # Continue with the selected config
    sftp = connect_sftp()

    if sftp:
        try:
            # Change to the target directory on the remote server
            sftp.chdir(config['remote_directory'])

            # Start the backup process
            backup_remote_folders(sftp, config['remote_directory'], config['backup_directory'], config['exclude_dirs'])

            # Delete specified folders from the remote server
            delete_remote_folders(sftp, config['remote_directory'], config['folders_to_copy'])
            
            # Copy the same folders from the local machine to the remote server
            copy_local_folders(sftp, config['local_directory'], config['remote_directory'], config['folders_to_copy'])

            # After the copy operation, run the Docker restart command
            run_docker_restart_command(config['container'], config['follow_lines'])
        
        finally:
            sftp.close()  # Close the SFTP connection
            print("SFTP connection closed.")

if __name__ == '__main__':
    main()