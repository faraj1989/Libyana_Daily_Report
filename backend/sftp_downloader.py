#!/usr/bin/env python3
"""
Libyana NPM - SFTP Downloader (FIXED - No Duplicates)
Handles FTP connection, download and file organisation with duplicate prevention.
"""

import os
import zipfile
import logging
import re
from datetime import datetime
import paramiko

logger = logging.getLogger(__name__)


class SFTPDownloader:
    """Handles SFTP connection, download and file organisation with duplicate prevention."""

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

    def extract_date_from_filename(self, filename):
        """
        Extract date from filename.
        Returns date in YYYY-MM-DD format.
        """
        # Pattern for YYYYMMDD (8 digits)
        match = re.search(r'(\d{8})', filename)
        if match:
            date_str = match.group(1)
            try:
                dt = datetime.strptime(date_str, '%Y%m%d')
                return dt.strftime('%Y-%m-%d')
            except ValueError:
                pass

        # Pattern for YYYY-MM-DD
        match = re.search(r'(\d{4}-\d{2}-\d{2})', filename)
        if match:
            return match.group(1)

        return None

    def get_base_name_from_filename(self, filename):
        """
        Extract the base name of the file (without timestamp).
        Example: "PS CS Daily Traffic per site_2G_3G_4G_20260727121322-20260812105324.zip"
                 -> "PS CS Daily Traffic per site_2G_3G_4G"
        """
        # Remove extension
        name = filename.rsplit('.', 1)[0]

        # Remove timestamp suffix (_YYYYMMDDHHMMSS-YYYYMMDDHHMMSS)
        pattern = r'(_\d{14}-\d{14})$'
        name = re.sub(pattern, '', name)

        # Remove trailing underscores
        name = name.rstrip('_')

        return name

    def cleanup_old_duplicates(self, folder_path, base_name, extension='.zip'):
        """
        Keep only the most recent file with the given base name.
        Delete older duplicates.
        """
        if not os.path.exists(folder_path):
            return None

        # Find all files with this base name and extension
        files = []
        for f in os.listdir(folder_path):
            if f.startswith(base_name) and f.endswith(extension):
                file_path = os.path.join(folder_path, f)
                files.append((file_path, os.path.getmtime(file_path)))

        if not files:
            return None

        # Sort by modification time (newest first)
        files.sort(key=lambda x: x[1], reverse=True)

        # Keep the newest, delete the rest
        kept_file = files[0][0]
        for file_path, _ in files[1:]:
            try:
                os.remove(file_path)
                self.log(f"🗑️ Deleted duplicate: {os.path.basename(file_path)}")
            except Exception as e:
                self.log(f"⚠️ Could not delete {file_path}: {e}")

        return kept_file

    def download_and_organize(self, target_date=None):
        """
        Download and organize files from FTP.
        If target_date is specified (YYYY-MM-DD), only downloads files for that date.
        """
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
        self.log(f"📁 Found {len(zip_files)} zip files in remote directory.")

        if target_date:
            self.log(f"🎯 Target date: {target_date}")

        processed_count = 0
        skipped_count = 0

        for fname in zip_files:
            # Extract date from filename
            file_date = self.extract_date_from_filename(fname)

            if not file_date:
                # Try to get date from file modification time
                try:
                    file_stat = self.sftp.stat(fname)
                    mtime = file_stat.st_mtime
                    mtime_dt = datetime.fromtimestamp(mtime)
                    file_date = mtime_dt.strftime('%Y-%m-%d')
                    self.log(f"📅 Using mtime for {fname}: {file_date}")
                except Exception as e:
                    self.log(f"⚠️ Could not determine date for {fname}: {e}")
                    continue

            # Skip if target_date is specified and doesn't match
            if target_date and file_date != target_date:
                self.log(f"⏭️ Skipping {fname} (date {file_date} != {target_date})")
                skipped_count += 1
                continue

            # Get the base name (without timestamp)
            base_name = self.get_base_name_from_filename(fname)

            day_folder = os.path.join(self.local_root, file_date)
            zipped_folder = os.path.join(day_folder, 'zipped')
            unzipped_folder = os.path.join(day_folder, 'unzipped')
            os.makedirs(zipped_folder, exist_ok=True)
            os.makedirs(unzipped_folder, exist_ok=True)

            # ============================================================
            # CHECK FOR DUPLICATES IN ZIPPED FOLDER
            # ============================================================
            existing_zip = None
            for existing in os.listdir(zipped_folder):
                if existing.startswith(base_name) and existing.endswith('.zip'):
                    existing_zip = os.path.join(zipped_folder, existing)
                    break

            if existing_zip:
                try:
                    remote_mtime = self.sftp.stat(fname).st_mtime
                    local_mtime = os.path.getmtime(existing_zip)

                    if remote_mtime <= local_mtime:
                        self.log(f"⏭️ Skipping {fname} - already exists (local is newer)")
                        # Clean up any old duplicates in unzipped folder
                        self.cleanup_old_duplicates(unzipped_folder, base_name, '.csv')
                        skipped_count += 1
                        continue
                    else:
                        # Remote file is newer, delete the old one
                        try:
                            os.remove(existing_zip)
                            self.log(f"🗑️ Removed old zip: {os.path.basename(existing_zip)}")
                        except:
                            pass
                except Exception as e:
                    self.log(f"⚠️ Could not compare files: {e}")

            # ============================================================
            # DOWNLOAD THE FILE
            # ============================================================
            local_zip_path = os.path.join(zipped_folder, fname)
            self.log(f"📥 Downloading: {fname}")
            self.log(f"   📅 Date: {file_date}")
            self.log(f"   📁 Local: {local_zip_path}")

            try:
                # Download the file
                self.sftp.get(fname, local_zip_path)
                self.log(f"✅ Downloaded to {local_zip_path}")

                # ============================================================
                # CLEAN UP ANY OLD DUPLICATES AFTER DOWNLOAD
                # ============================================================
                self.cleanup_old_duplicates(zipped_folder, base_name, '.zip')

                # ============================================================
                # UNZIP THE FILE
                # ============================================================
                self.log(f"📂 Unzipping {local_zip_path}...")
                self._unzip_file(local_zip_path, unzipped_folder)

                # Clean up old CSV duplicates in unzipped folder
                self.cleanup_old_duplicates(unzipped_folder, base_name, '.csv')

                processed_count += 1
                self.log(f"✅ Done: {fname}")

            except Exception as e:
                self.log(f"❌ Failed to download/unzip {fname}: {e}", 'error')
                continue

        self.log(f"\n📊 Download Summary:")
        self.log(f"   ✅ Downloaded: {processed_count} files")
        self.log(f"   ⏭️ Skipped: {skipped_count} files")
        self.log(f"   📁 Local root: {self.local_root}")
        return True

    def _unzip_file(self, zip_path, extract_to):
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_to)
            self.log(f"✅ Unzipped to {extract_to}")
        except Exception as e:
            self.log(f"❌ Unzip failed: {e}", 'error')
            raise