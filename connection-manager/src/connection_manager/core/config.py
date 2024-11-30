import json
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

class ConfigManager:
    def __init__(self):
        self.config_dir = Path.home() / ".connections"
        self.config_file = self.config_dir / "config.json"
        self.keys_dir = self.config_dir / "keys"
        self._ensure_dirs()

    def _ensure_dirs(self):
        self.config_dir.mkdir(exist_ok=True)
        self.keys_dir.mkdir(exist_ok=True)
        if not self.config_file.exists():
            self.config_file.write_text("{}")

    def save_connection(self, name: str, config: Dict):
        connections = self.load_connections()
        config['last_modified'] = datetime.now().isoformat()
        connections[name] = config
        self.config_file.write_text(json.dumps(connections, indent=2))

    def load_connections(self) -> Dict:
        return json.loads(self.config_file.read_text())

    def get_connection(self, name: str) -> Optional[Dict]:
        return self.load_connections().get(name)

    def delete_connection(self, name: str) -> bool:
        connections = self.load_connections()
        if name in connections:
            del connections[name]
            self.config_file.write_text(json.dumps(connections, indent=2))
            return True
        return False
