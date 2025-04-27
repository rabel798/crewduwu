import os
from git import Repo
import shutil
import time
import stat

def handle_remove_readonly(func, path, exc):
    """Handle permission issues when removing files"""
    os.chmod(path, stat.S_IWRITE)
    func(path)

def upload_folder_to_github(source_folder, github_url, username, token):
    temp_dir = "temp_git_folder"
    
    try:
        # Remove temp directory if it exists
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, onerror=handle_remove_readonly)
        
        # Construct the authenticated URL
        repo_name = github_url.split('/')[-1]
        auth_url = f"https://{username}:{token}@github.com/{username}/{repo_name}"
        
        print(f"Cloning repository...")
        repo = Repo.clone_from(auth_url, temp_dir)
        
        # Get list of all files and directories first
        all_items = []
        for root, dirs, files in os.walk(source_folder):
            # Skip .git directory
            if '.git' in root:
                continue
                
            # Add directories
            for dir_name in dirs:
                if '.git' not in dir_name:
                    source_dir = os.path.join(root, dir_name)
                    rel_path = os.path.relpath(source_dir, source_folder)
                    all_items.append(('dir', rel_path))
            
            # Add files
            for file_name in files:
                source_file = os.path.join(root, file_name)
                rel_path = os.path.relpath(source_file, source_folder)
                all_items.append(('file', rel_path))

        # Process all items
        total_items = len(all_items)
        for index, (item_type, rel_path) in enumerate(all_items, 1):
            try:
                if item_type == 'dir':
                    dest_dir = os.path.join(temp_dir, rel_path)
                    if not os.path.exists(dest_dir):
                        os.makedirs(dest_dir)
                        repo.index.add([rel_path])
                        repo.index.commit(f"Created directory: {rel_path}")
                        print(f"[{index}/{total_items}] Committed directory: {rel_path}")
                else:
                    source_file = os.path.join(source_folder, rel_path)
                    dest_file = os.path.join(temp_dir, rel_path)
                    
                    # Ensure directory exists
                    os.makedirs(os.path.dirname(dest_file), exist_ok=True)
                    
                    # Copy file
                    shutil.copy2(source_file, dest_file)
                    
                    # Create commit for this file
                    repo.index.add([rel_path])
                    repo.index.commit(f"Added file: {rel_path}")
                    print(f"[{index}/{total_items}] Committed file: {rel_path}")

                # Push after each commit
                if index == total_items:  # Only push on the last item
                    print("\nPushing all commits to GitHub...")
                    origin = repo.remote('origin')
                    origin.push()

            except Exception as e:
                print(f"Error processing {rel_path}: {str(e)}")
                continue

        print("\nAll files have been successfully pushed to GitHub!")
        
    except Exception as e:
        print(f"An error occurred: {str(e)}")
    
    finally:
        # Cleanup with delay and error handling
        print("Cleaning up...")
        try:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, onerror=handle_remove_readonly)
        except Exception as e:
            print(f"Cleanup error (can be ignored): {str(e)}")

def main():
    # Get inputs from user
    source_folder = input("Enter the path to your source folder: ").strip()
    github_url = input("Enter the GitHub repository URL: ").strip()
    username = input("Enter your GitHub username: ").strip()
    token = input("Enter your GitHub personal access token: ").strip()
    
    # Validate source folder
    if not os.path.exists(source_folder):
        print(f"Source folder {source_folder} does not exist!")
        return
    
    upload_folder_to_github(source_folder, github_url, username, token)

if __name__ == "__main__":
    main()