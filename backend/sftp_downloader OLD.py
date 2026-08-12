#!/usr/bin/env python3
"""
Libyana NPM - SFTP Downloader
Handles FTP connection, download, and file organisation.
"""

import os
import zipfile
import logging
from datetime import datetime
import paramiko

logger = logging.getLogger(__name__)


class SFTPDownloader:
    """Handles SFTP connection, download and file organisation."""
    def __init__(self, host, port, username, password, remote_path, local_root, log_callback=None):
        self.host = host
        self.port = int(port)
        self.username = username
        self.password = password
        self.remote_path = remote_path
        self.local_root = local_root
        self.log_callback = log_callback
        self.ssh = None
        self.sftp = None

    def log(self, msg, level='info'):
        if self.log_callback:
            self.log_callback(msg)
        else:
            logger.info(msg)

    def connect(self):
        try:
            self.log(f"Connecting to {self.host}:{self.port} as {self.username}...")
            self.ssh = paramiko.SSHClient()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh.connect(self.host, port=self.port, username=self.username, password=self.password, timeout=30)
            self.sftp = self.ssh.open_sftp()
            self.log("SFTP connection established.")
            return True
        except Exception as e:
            self.log(f"SFTP connection failed: {e}", 'error')
            return False

    def disconnect(self):
        if self.sftp:
            self.sftp.close()
        if self.ssh:
            self.ssh.close()
        self.log("SFTP disconnected.")

    def list_remote_files(self):
        """List files in the remote directory."""
        if not self.sftp:
            self.log("SFTP session not active.", 'error')
            return []

        try:
            self.sftp.chdir(self.remote_path)
            files = self.sftp.listdir()
            self.log(f"Found {len(files)} files in remote directory.")
            return files
        except Exception as e:
            self.log(f"Failed to list remote files: {e}", 'error')
            return []

    def download_and_organize(self, target_date=None):
        if not self.sftp:
            self.log("SFTP session not active.", 'error')
            return False

        try:
            self.sftp.chdir(self.remote_path)
        except Exception as e:
            self.log(f"Failed to change to {self.remote_path}: {e}", 'error')
            return False

        try:
            files = self.sftp.listdir()
        except Exception as e:
            self.log(f"Failed to list remote files: {e}", 'error')
            return False

        zip_files = [f for f in files if f.lower().endswith('.zip')]
        self.log(f"Found {len(zip_files)} zip files.")

        processed_count = 0
        for fname in zip_files:
            try:
                file_stat = self.sftp.stat(fname)
                mtime = file_stat.st_mtime
                mtime_dt = datetime.fromtimestamp(mtime)
                file_date = mtime_dt.strftime('%Y-%m-%d')
            except Exception as e:
                self.log(f"Could not get mtime for {fname}: {e}", 'error')
                continue

            if target_date and file_date != target_date:
                continue

            day_folder = os.path.join(self.local_root, file_date)
            zipped_folder = os.path.join(day_folder, 'zipped')
            unzipped_folder = os.path.join(day_folder, 'unzipped')
            os.makedirs(zipped_folder, exist_ok=True)
            os.makedirs(unzipped_folder, exist_ok=True)

            local_zip_path = os.path.join(zipped_folder, fname)

            if os.path.exists(local_zip_path):
                self.log(f"File already exists: {local_zip_path}")
                if not os.listdir(unzipped_folder):
                    self.log(f"Unzipping {local_zip_path}...")
                    self._unzip_file(local_zip_path, unzipped_folder)
                continue

            self.log(f"Downloading {fname} ...")
            try:
                self.sftp.get(fname, local_zip_path)
                self.log(f"Downloaded to {local_zip_path}")
                self.log(f"Unzipping {local_zip_path}...")
                self._unzip_file(local_zip_path, unzipped_folder)
                processed_count += 1
            except Exception as e:
                self.log(f"Failed to download/unzip {fname}: {e}", 'error')
                continue

        self.log(f"Processed {processed_count} zip files.")
        return True

    def _unzip_file(self, zip_path, extract_to):
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_to)
            self.log(f"Unzipped to {extract_to}")
        except Exception as e:
            self.log(f"Unzip failed: {e}", 'error')
            raise