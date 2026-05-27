import json
import os

REGISTRY_FILE = "registry.json"

def load_registry():
    if not os.path.exists(REGISTRY_FILE):
        return {}
    try:
        with open(REGISTRY_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_registry(registry_data):
    with open(REGISTRY_FILE, "w") as f:
        json.dump(registry_data, f, indent=4)
