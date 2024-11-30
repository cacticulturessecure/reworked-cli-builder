import subprocess
from pathlib import Path
import os
import stat
from typing import Optional, Tuple
from rich.console import Console

console = Console()

class SSHKeyManager:
    def __init__(self):
        self.config_dir = Path.home() / ".connections"
        self.keys_dir = self.config_dir / "keys"
        self.keys_dir.mkdir(exist_ok=True)

    def generate_key(self, connection_name: str) -> Tuple[Path, Path]:
        """Generate SSH key pair for a connection"""
        key_path = self.keys_dir / f"{connection_name}"
        pub_key_path = self.keys_dir / f"{connection_name}.pub"
        
        if not key_path.exists():
            subprocess.run([
                "ssh-keygen",
                "-t", "ed25519",
                "-f", str(key_path),
                "-N", ""  # Empty passphrase
            ], check=True)
            
            # Set correct permissions
            key_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
            pub_key_path.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IROTH | stat.S_IRGRP)
        
        return key_path, pub_key_path

    def get_public_key_content(self, connection_name: str) -> Optional[str]:
        """Get public key content for a connection"""
        pub_key_path = self.keys_dir / f"{connection_name}.pub"
        if pub_key_path.exists():
            return pub_key_path.read_text().strip()
        return None

    def test_connection(self, host: str, port: int, key_path: Path) -> bool:
        """Test SSH connection with key"""
        try:
            result = subprocess.run([
                "ssh",
                "-i", str(key_path),
                "-p", str(port),
                "-o", "BatchMode=yes",
                "-o", "StrictHostKeyChecking=accept-new",
                "-o", "ConnectTimeout=5",
                f"root@{host}",
                "echo 'Connection test successful'"
            ], capture_output=True, text=True)
            return result.returncode == 0
        except Exception as e:
            console.print(f"[red]Connection test failed: {e}[/red]")
            return False

    def setup_tunnel(self, host: str, port: int, key_path: Path,
                    local_port: int = 11434, remote_port: int = 11434) -> subprocess.Popen:
        """Create SSH tunnel for Ollama"""
        return subprocess.Popen([
            "ssh",
            "-i", str(key_path),
            "-N",  # Don't execute remote command
            "-L", f"{local_port}:localhost:{remote_port}",
            "-p", str(port),
            f"root@{host}"
        ])
