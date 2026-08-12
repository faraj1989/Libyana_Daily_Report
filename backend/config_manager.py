#!/usr/bin/env python3
"""
Libyana NPM - Config Manager
Handles FTP configuration securely.
"""

import os
import json
import base64
import logging

logger = logging.getLogger(__name__)

CONFIG_FILE = "ftp_config.json"


class ConfigManager:
    """Manage FTP configuration securely."""
    def __init__(self, config_file=CONFIG_FILE):
        self.config_file = config_file
        self.config = {}
        self.load()

    def load(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    raw = json.load(f)
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
        key = 0x5A
        return base64.b64encode(bytes([ord(c) ^ key for c in text])).decode()

    def _xor_decrypt(self, encoded):
        key = 0x5A
        decoded = base64.b64decode(encoded).decode()
        return ''.join(chr(ord(c) ^ key) for c in decoded)