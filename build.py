#!/usr/bin/env python3
# build.py
# Packages the Webmin dnsmasq-dhcpleases module into a standard dnsmasq-dhcpleases.wbm.gz distribution file.

import os
import shutil
import tarfile

def build():
    workspace = '/Users/tonygauderman/Antigravity/webmin-dnsmasq-dhcpleases'
    build_temp = os.path.join(workspace, 'build_temp')
    module_dir = os.path.join(build_temp, 'dnsmasq-dhcpleases')
    
    print("Preparing package layout...")
    # Clean and recreate temporary build directories
    if os.path.exists(build_temp):
        shutil.rmtree(build_temp)
    os.makedirs(module_dir)
    
    # List of files and folders to package
    files_to_copy = [
        'module.info', 'config', 'config.info', 'dnsmasq-dhcpleases-lib.pl',
        'index.cgi', 'status_ajax.cgi', 'mac_lookup.cgi', 'save_reservation.cgi',
        'delete_reservation.cgi', 'delete_lease.cgi', 'action.cgi'
    ]
    dirs_to_copy = ['lang', 'images']
    
    # Copy files
    for f in files_to_copy:
        src = os.path.join(workspace, f)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(module_dir, f))
            # Set executable permissions for scripts
            if f.endswith('.cgi'):
                os.chmod(os.path.join(module_dir, f), 0o755)
            else:
                os.chmod(os.path.join(module_dir, f), 0o644)
        else:
            print(f"Warning: File {f} not found, skipping.")
            
    # Copy directories
    for d in dirs_to_copy:
        src = os.path.join(workspace, d)
        if os.path.exists(src):
            dest = os.path.join(module_dir, d)
            shutil.copytree(src, dest)
            # Ensure proper permissions inside directories
            for root, subdirs, files in os.walk(dest):
                for sd in subdirs:
                    os.chmod(os.path.join(root, sd), 0o755)
                for file in files:
                    os.chmod(os.path.join(root, file), 0o644)
                    
    output_filename = os.path.join(workspace, 'webmin-dnsmasq-dhcpleases.wbm.gz')
    print(f"Creating archive {output_filename}...")
    
    # Create gzipped tar archive with 'dnsmasq-dhcpleases' as the root directory
    original_cwd = os.getcwd()
    try:
        os.chdir(build_temp)
        with tarfile.open(output_filename, 'w:gz') as tar:
            tar.add('dnsmasq-dhcpleases')
    finally:
        os.chdir(original_cwd)
        
    # Clean up temp files
    shutil.rmtree(build_temp)
    print("Build complete! webmin-dnsmasq-dhcpleases.wbm.gz generated successfully.")

if __name__ == '__main__':
    build()
