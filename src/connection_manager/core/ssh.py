import subprocess
import time  # Add this import
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

    def get_key_path(self, connection_name: str) -> Path:
        """Get the path to the private key"""
        return self.keys_dir / f"{connection_name}"

    def generate_key(self, connection_name: str, force: bool = False) -> Tuple[Path, Path]:
        """Generate SSH key pair for a connection"""
        key_path = self.keys_dir / f"{connection_name}"
        pub_key_path = self.keys_dir / f"{connection_name}.pub"
        
        if key_path.exists() and not force:
            return key_path, pub_key_path
            
        subprocess.run([
            "ssh-keygen",
            "-t", "ed25519",
            "-f", str(key_path),
            "-N", ""  # Empty passphrase
        ], check=True)
        
        # Set correct permissions
        key_path.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 600
        pub_key_path.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IROTH | stat.S_IRGRP)  # 644
        
        return key_path, pub_key_path

    def test_connection(self, host: str, port: int, key_path: Path, verbose: bool = False) -> bool:
        """Test SSH connection with key"""
        try:
            cmd = [
                "ssh",
                "-i", str(key_path),
                "-p", str(port),
                "-o", "BatchMode=yes",
                "-o", "StrictHostKeyChecking=no",
                "-o", "ConnectTimeout=10"
            ]
            
            if verbose:
                cmd.append("-v")
                
            cmd.extend([
                f"root@{host}",
                "echo 'Connection test successful'"
            ])
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True
            )
            
            if verbose and result.stderr:
                console.print(f"[yellow]SSH Debug Output:[/yellow]\n{result.stderr}")
                
            return result.returncode == 0
        except Exception as e:
            console.print(f"[red]Connection test failed: {e}[/red]")
            return False

    def setup_tunnel(self, host: str, port: int, key_path: Path,
                    local_port: int = 11434, remote_port: int = 11434) -> Optional[subprocess.Popen]:
        """Create SSH tunnel for Ollama"""
        console.print("[yellow]Setting up SSH tunnel...[/yellow]")
        try:
            process = subprocess.Popen([
                "ssh",
                "-i", str(key_path),
                "-N",  # Don't execute remote command
                "-v",  # Verbose output
                "-o", "StrictHostKeyChecking=no",
                "-o", "ExitOnForwardFailure=yes",
                "-L", f"{local_port}:localhost:{remote_port}",
                "-p", str(port),
                f"root@{host}"
            ], stderr=subprocess.PIPE)
            
            # Wait a moment to check if the process is still running
            time.sleep(2)
            if process.poll() is not None:
                _, stderr = process.communicate()
                console.print(f"[red]Tunnel setup failed: {stderr.decode()}[/red]")
                return None
                
            console.print("[green]SSH tunnel established successfully![/green]")
            return process
        except Exception as e:
            console.print(f"[red]Failed to setup tunnel: {e}[/red]")
            return None
