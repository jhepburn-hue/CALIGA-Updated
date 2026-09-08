import json
import re

import os
config_path = os.path.join(os.path.dirname(__file__), "config.json")


def load_config(config_path: str = config_path, config_name: str = "devices") -> dict:
    """Load configuration from a JSON file with comments."""
    try:
        with open(config_path, 'r', encoding='utf-8') as config_file:
            content = config_file.read()
            content = re.sub(r'\/\/.*', '', content)  # Remove single line comments
            content = re.sub(r'\/\*[\s\S]*?\*\/', '', content)  # Remove multi-line comments
            configs = json.loads(content)
            if config_name == 'devices':
                return configs['devices']
            device_config = configs['devices'].get(config_name)
            if not device_config:
                raise ValueError(f"No configuration found for device: {config_name}")
            return device_config
    except Exception as e:
        raise RuntimeError(f"Error loading configuration: {e}")
