#!/usr/bin/env python3
"""
Libyana NPM - SFTP Downloader with Admin GUI
Step 1: Download and organise files from FTP server.
Author: Automation Team
Date: 2026-07-30
"""

import os
import re
import sys
import zipfile
import logging
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from tkinter import filedialog
import paramiko
import base64
from datetime import datetime, timedelta
import json
from pathlib import Path
import threading
import queue

# Try to import tkcalendar for date picker
try:
    from tkcalendar import Calendar
    HAS_TKCALENDAR = True
except ImportError:
    HAS_TKCALENDAR = False

# ---------------------------- Configuration ----------------------------
CONFIG_FILE = "../ftp_config.json"
LOG_FILE = "../sftp_downloader.log"

# ---------------------------- Logging Setup ----------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ---------------------------- Config Manager ----------------------------
class ConfigManager:
    """Manage FTP configuration securely."""
    def __init__(self, config_file=CONFIG_FILE):
        self.config_file = config_file
        self.config = {}
        self.load()

    def load(self):
        """Load config from file, decrypt password."""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    raw = json.load(f)
                # Decrypt password (simple XOR obfuscation)
                if 'password_enc' in raw:
                    raw['password'] = self._xor_decrypt(raw['password_enc'])
                self.config = raw
                logger.info("Config loaded from %s", self.config_file)
            except Exception as e:
                logger.error("Failed to load config: %s", e)
                self.config = {}
        else:
            self.config = {}

    def save(self):
        """Save config, encrypt password."""
        data = self.config.copy()
        if 'password' in data:
            data['password_enc'] = self._xor_encrypt(data['password'])
            del data['password']
        try:
            with open(self.config_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info("Config saved to %s", self.config_file)
        except Exception as e:
            logger.error("Failed to save config: %s", e)

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value

    def _xor_encrypt(self, text):
        """Simple obfuscation (not cryptographically secure)."""
        key = 0x5A
        return base64.b64encode(bytes([ord(c) ^ key for c in text])).decode()

    def _xor_decrypt(self, encoded):
        key = 0x5A
        decoded = base64.b64decode(encoded).decode()
        return ''.join(chr(ord(c) ^ key) for c in decoded)

# ---------------------------- SFTP Downloader ----------------------------
class SFTPDownloader:
    """Handles SFTP connection, download and file organisation."""
    def __init__(self, host, port, username, password, remote_path, local_root, log_callback=None):
        self.host = host
        self.port = int(port)
        self.username = username
        self.password = password
        self.remote_path = remote_path
        self.local_root = local_root
        self.log_callback = log_callback  # function to log to GUI
        self.ssh = None
        self.sftp = None

    def log(self, msg, level='info'):
        if self.log_callback:
            self.log_callback(msg)
        else:
            logger.info(msg)

    def connect(self):
        """Establish SFTP connection."""
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

    def download_and_organize(self, target_date=None):
        """
        Download all files from remote_path and organise by date.
        Date is determined from the file's last modification time (mtime).
        If target_date is provided (YYYY-MM-DD), only process files with that mtime date.
        """
        if not self.sftp:
            self.log("SFTP session not active. Call connect() first.", 'error')
            return False

        # Change to remote directory
        try:
            self.sftp.chdir(self.remote_path)
        except Exception as e:
            self.log(f"Failed to change to remote directory {self.remote_path}: {e}", 'error')
            return False

        # List files
        try:
            files = self.sftp.listdir()
            self.log(f"Found {len(files)} files in remote directory.")
        except Exception as e:
            self.log(f"Failed to list remote files: {e}", 'error')
            return False

        # Filter only zip files (we expect all are zip)
        zip_files = [f for f in files if f.lower().endswith('.zip')]
        self.log(f"Found {len(zip_files)} zip files.")

        # Process each zip file
        processed_count = 0
        for fname in zip_files:
            # Get file stats to retrieve mtime
            try:
                file_stat = self.sftp.stat(fname)
                mtime = file_stat.st_mtime
                mtime_dt = datetime.fromtimestamp(mtime)
                file_date = mtime_dt.strftime('%Y-%m-%d')
            except Exception as e:
                self.log(f"Could not get mtime for {fname}: {e}", 'error')
                continue

            self.log(f"File: {fname}  (mtime: {file_date})")

            # If target_date specified, skip other dates
            if target_date and file_date != target_date:
                self.log(f"Skipping {fname} (mtime {file_date} != target {target_date})")
                continue

            # Build local paths based on mtime date
            day_folder = os.path.join(self.local_root, file_date)
            zipped_folder = os.path.join(day_folder, 'zipped')
            unzipped_folder = os.path.join(day_folder, 'unzipped')
            os.makedirs(zipped_folder, exist_ok=True)
            os.makedirs(unzipped_folder, exist_ok=True)

            local_zip_path = os.path.join(zipped_folder, fname)

            # Check if already downloaded
            if os.path.exists(local_zip_path):
                self.log(f"File already exists: {local_zip_path}, skipping download.")
                # If unzipped folder empty, unzip
                if not os.listdir(unzipped_folder):
                    self.log(f"Unzipping {local_zip_path} to {unzipped_folder}...")
                    self._unzip_file(local_zip_path, unzipped_folder)
                else:
                    self.log(f"Unzipped files already exist in {unzipped_folder}, skipping.")
                continue

            # Download
            self.log(f"Downloading {fname} ...")
            try:
                self.sftp.get(fname, local_zip_path)
                self.log(f"Downloaded to {local_zip_path}")
                # Unzip
                self.log(f"Unzipping {local_zip_path} to {unzipped_folder}...")
                self._unzip_file(local_zip_path, unzipped_folder)
                processed_count += 1
            except Exception as e:
                self.log(f"Failed to download/unzip {fname}: {e}", 'error')
                continue

        self.log(f"Processed {processed_count} zip files for date{'' if not target_date else ' ' + target_date}.")
        return True

    def _unzip_file(self, zip_path, extract_to):
        """Extract zip file contents."""
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_to)
            self.log(f"Unzipped to {extract_to}")
        except Exception as e:
            self.log(f"Unzip failed: {e}", 'error')
            raise

# ---------------------------- GUI Application ----------------------------
class SFTPDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Libyana NPM - SFTP Downloader")
        self.root.geometry("800x750")
        self.root.resizable(True, True)

        self.config = ConfigManager()

        # GUI variables
        self.host_var = tk.StringVar(value=self.config.get('host', '10.171.68.77'))
        self.port_var = tk.StringVar(value=self.config.get('port', '22'))
        self.username_var = tk.StringVar(value=self.config.get('username', 'ftpuser'))
        self.password_var = tk.StringVar(value=self.config.get('password', ''))
        self.remote_path_var = tk.StringVar(value=self.config.get('remote_path', '/ftproot/Daily Report KPIs'))
        self.local_root_var = tk.StringVar(value=self.config.get('local_root', r'C:\Users\user\Desktop\FTP files\Daily Report KPIs 2026 update'))

        # Build UI
        self._build_widgets()

        # Log queue for thread-safe GUI updates
        self.log_queue = queue.Queue()
        self._poll_log_queue()

        # Bind close event to save config
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_widgets(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Configuration frame
        cfg_frame = ttk.LabelFrame(main_frame, text="FTP Configuration", padding="10")
        cfg_frame.pack(fill=tk.X, pady=5)

        # Row 0: Host
        ttk.Label(cfg_frame, text="Host:").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(cfg_frame, textvariable=self.host_var, width=40).grid(row=0, column=1, sticky=tk.W, padx=5)

        # Row 1: Port
        ttk.Label(cfg_frame, text="Port:").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Entry(cfg_frame, textvariable=self.port_var, width=10).grid(row=1, column=1, sticky=tk.W, padx=5)

        # Row 2: Username
        ttk.Label(cfg_frame, text="Username:").grid(row=2, column=0, sticky=tk.W, pady=2)
        ttk.Entry(cfg_frame, textvariable=self.username_var, width=40).grid(row=2, column=1, sticky=tk.W, padx=5)

        # Row 3: Password
        ttk.Label(cfg_frame, text="Password:").grid(row=3, column=0, sticky=tk.W, pady=2)
        ttk.Entry(cfg_frame, textvariable=self.password_var, width=40, show="*").grid(row=3, column=1, sticky=tk.W, padx=5)

        # Row 4: Remote Path
        ttk.Label(cfg_frame, text="Remote Path:").grid(row=4, column=0, sticky=tk.W, pady=2)
        ttk.Entry(cfg_frame, textvariable=self.remote_path_var, width=40).grid(row=4, column=1, sticky=tk.W, padx=5)

        # Row 5: Local Root
        ttk.Label(cfg_frame, text="Local Root:").grid(row=5, column=0, sticky=tk.W, pady=2)
        ttk.Entry(cfg_frame, textvariable=self.local_root_var, width=40).grid(row=5, column=1, sticky=tk.W, padx=5)
        ttk.Button(cfg_frame, text="Browse...", command=self._browse_local_root).grid(row=5, column=2, padx=5)

        # Buttons
        btn_frame = ttk.Frame(cfg_frame)
        btn_frame.grid(row=6, column=0, columnspan=3, pady=10)
        ttk.Button(btn_frame, text="Save Config", command=self._save_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Test Connection", command=self._test_connection).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Download & Organize", command=self._start_download).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Download for Specific Date", command=self._prompt_date_download).pack(side=tk.LEFT, padx=5)

        # Log area
        log_frame = ttk.LabelFrame(main_frame, text="Log Output", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # Create a frame for log text and copy button
        log_container = ttk.Frame(log_frame)
        log_container.pack(fill=tk.BOTH, expand=True)

        self.log_text = scrolledtext.ScrolledText(log_container, height=20, width=80, state='normal')
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        # Enable selection and copy (default is enabled, but we ensure it)
        self.log_text.configure(selectbackground='lightblue', selectforeground='black')
        # Configure tags for colors
        self.log_text.tag_config('error', foreground='red')
        self.log_text.tag_config('info', foreground='black')

        # Copy log button
        copy_btn = ttk.Button(log_container, text="📋 Copy Log", command=self._copy_log)
        copy_btn.pack(side=tk.RIGHT, padx=5, pady=5, anchor=tk.N)

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(fill=tk.X, pady=(5,0))

    def _copy_log(self):
        """Copy entire log text to clipboard."""
        self.root.clipboard_clear()
        self.root.clipboard_append(self.log_text.get(1.0, tk.END))
        self.status_var.set("Log copied to clipboard!")

    def _browse_local_root(self):
        path = filedialog.askdirectory(title="Select Local Root Directory")
        if path:
            self.local_root_var.set(path)

    def _save_config(self):
        self.config.set('host', self.host_var.get().strip())
        self.config.set('port', self.port_var.get().strip())
        self.config.set('username', self.username_var.get().strip())
        self.config.set('password', self.password_var.get())
        self.config.set('remote_path', self.remote_path_var.get().strip())
        self.config.set('local_root', self.local_root_var.get().strip())
        self.config.save()
        self._log("Configuration saved.")

    def _test_connection(self):
        """Test SFTP connection in a separate thread."""
        self.status_var.set("Testing connection...")
        self._run_thread(self._do_test_connection)

    def _do_test_connection(self):
        host = self.host_var.get().strip()
        port = self.port_var.get().strip()
        username = self.username_var.get().strip()
        password = self.password_var.get()
        remote_path = self.remote_path_var.get().strip()

        downloader = SFTPDownloader(host, port, username, password, remote_path, "", log_callback=self._log)
        try:
            if downloader.connect():
                self._log("Connection successful.")
                try:
                    downloader.sftp.chdir(remote_path)
                    files = downloader.sftp.listdir()
                    self._log(f"Remote directory contains {len(files)} items.")
                except Exception as e:
                    self._log(f"Could not list remote directory: {e}", 'error')
                downloader.disconnect()
            else:
                self._log("Connection failed.", 'error')
        except Exception as e:
            self._log(f"Test error: {e}", 'error')
        finally:
            self.status_var.set("Ready")

    def _start_download(self):
        """Start download process in a separate thread."""
        self.status_var.set("Downloading...")
        self._run_thread(self._do_download)

    def _do_download(self):
        host = self.host_var.get().strip()
        port = self.port_var.get().strip()
        username = self.username_var.get().strip()
        password = self.password_var.get()
        remote_path = self.remote_path_var.get().strip()
        local_root = self.local_root_var.get().strip()

        downloader = SFTPDownloader(host, port, username, password, remote_path, local_root, log_callback=self._log)
        try:
            if downloader.connect():
                downloader.download_and_organize()
                downloader.disconnect()
                self._log("Download process completed.")
            else:
                self._log("Download aborted due to connection failure.", 'error')
        except Exception as e:
            self._log(f"Download error: {e}", 'error')
        finally:
            self.status_var.set("Ready")

    def _prompt_date_download(self):
        """Ask user for a specific date using a calendar picker."""
        if HAS_TKCALENDAR:
            self._show_calendar_dialog()
        else:
            self._show_manual_date_dialog()

    def _show_calendar_dialog(self):
        """Open a popup with a calendar widget to select a date."""
        top = tk.Toplevel(self.root)
        top.title("Select Date")
        top.geometry("300x250")
        top.grab_set()  # modal

        cal = Calendar(top, selectmode='day', year=datetime.now().year, month=datetime.now().month, day=datetime.now().day)
        cal.pack(pady=10)

        def confirm():
            date_obj = cal.selection_get()
            date_str = date_obj.strftime("%Y-%m-%d")
            top.destroy()
            self.status_var.set(f"Downloading for {date_str}...")
            self._run_thread(lambda: self._do_download_date(date_str))

        btn_frame = ttk.Frame(top)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="Confirm", command=confirm).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=top.destroy).pack(side=tk.LEFT, padx=5)

    def _show_manual_date_dialog(self):
        """Fallback: simple entry for date."""
        date_str = tk.simpledialog.askstring(
            "Date",
            "Enter date (YYYY-MM-DD):\n\n(Install tkcalendar for a calendar picker)",
            parent=self.root
        )
        if date_str:
            try:
                datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                messagebox.showerror("Invalid Date", "Please use format YYYY-MM-DD")
                return
            self.status_var.set(f"Downloading for {date_str}...")
            self._run_thread(lambda: self._do_download_date(date_str))

    def _do_download_date(self, date_str):
        host = self.host_var.get().strip()
        port = self.port_var.get().strip()
        username = self.username_var.get().strip()
        password = self.password_var.get()
        remote_path = self.remote_path_var.get().strip()
        local_root = self.local_root_var.get().strip()

        downloader = SFTPDownloader(host, port, username, password, remote_path, local_root, log_callback=self._log)
        try:
            if downloader.connect():
                downloader.download_and_organize(target_date=date_str)
                downloader.disconnect()
                self._log(f"Download for {date_str} completed.")
            else:
                self._log("Download aborted.", 'error')
        except Exception as e:
            self._log(f"Download error: {e}", 'error')
        finally:
            self.status_var.set("Ready")

    def _run_thread(self, target):
        """Run a function in a separate thread and catch exceptions."""
        def wrapper():
            try:
                target()
            except Exception as e:
                self._log(f"Unexpected error: {e}", 'error')
                self.status_var.set("Error")
        threading.Thread(target=wrapper, daemon=True).start()

    def _log(self, message, level='info'):
        """Add message to log queue for GUI update."""
        self.log_queue.put((message, level))

    def _poll_log_queue(self):
        """Periodically check log queue and update GUI."""
        try:
            while True:
                msg, level = self.log_queue.get_nowait()
                self.log_text.insert(tk.END, msg + "\n", level)
                self.log_text.see(tk.END)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self._poll_log_queue)

    def _on_close(self):
        self._save_config()
        self.root.destroy()

# ---------------------------- Main Entry ----------------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = SFTPDownloaderApp(root)
    root.mainloop()