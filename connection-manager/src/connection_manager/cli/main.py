import typer
from typing import Optional
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.progress import Progress
from rich.panel import Panel
from InquirerPy import inquirer
from InquirerPy.base.control import Choice
import asyncio
import time
import json
import signal
import os
import atexit
from ..core.config import ConfigManager
from ..core.ssh import SSHKeyManager

app = typer.Typer()
console = Console()
config_manager = ConfigManager()

# Add PID management
def get_pid_file(name: str) -> Path:
    return Path.home() / ".connections" / "pids" / f"{name}.pid"

def save_pid(name: str, pid: int):
    pid_dir = Path.home() / ".connections" / "pids"
    pid_dir.mkdir(exist_ok=True)
    get_pid_file(name).write_text(str(pid))

def get_saved_pid(name: str) -> Optional[int]:
    pid_file = get_pid_file(name)
    if pid_file.exists():
        try:
            return int(pid_file.read_text())
        except ValueError:
            return None
    return None

def remove_pid_file(name: str):
    pid_file = get_pid_file(name)
    if pid_file.exists():
        pid_file.unlink()

def is_process_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

class ConnectionManager:
    def __init__(self):
        self.config_manager = ConfigManager()

    async def interactive_setup(self):
        # Get connection name
        name = await inquirer.text(
            message="Enter connection name:",
            validate=lambda x: len(x) > 0 and x.isalnum(),
            invalid_message="Name must be non-empty and alphanumeric"
        ).execute_async()

        # Server Selection/Configuration
        server_type = await inquirer.select(
            message="Select server type:",
            choices=[
                Choice("gpu", "GPU Server"),
                Choice("web", "Web Server"),
                Choice("custom", "Custom Server")
            ],
            default="gpu"
        ).execute_async()

        # Connection details
        host = await inquirer.text(
            message="Server hostname:",
            validate=lambda x: len(x) > 0,
            invalid_message="Hostname cannot be empty"
        ).execute_async()

        port = await inquirer.number(
            message="Server port:",
            min_allowed=1,
            max_allowed=65535,
            default=22
        ).execute_async()

        # Authentication method
        auth_method = await inquirer.select(
            message="Choose authentication method:",
            choices=[
                Choice("key", "SSH Key (Recommended)"),
                Choice("password", "Password"),
            ],
            default="key"
        ).execute_async()

        config = {
            "name": name,
            "type": server_type,
            "host": host,
            "port": port,
            "auth_method": auth_method
        }

        return name, config

@app.command()
def setup():
    """Interactive setup for new connection"""
    console.print(Panel.fit("Connection Setup Wizard", style="bold blue"))
    
    name, config = asyncio.run(ConnectionManager().interactive_setup())
    
    with Progress() as progress:
        task = progress.add_task("Creating configuration...", total=100)
        config_manager.save_connection(name, config)
        progress.update(task, completed=100)
    
    console.print("[green]Setup complete![/green]")
    show_config(config)

@app.command()
def list():
    """List all configured connections"""
    connections = config_manager.load_connections()
    
    if not connections:
        console.print("[yellow]No connections configured yet.[/yellow]")
        return

    table = Table(title="Configured Connections")
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="blue")
    table.add_column("Host", style="green")
    table.add_column("Last Modified", style="yellow")
    
    for name, config in connections.items():
        table.add_row(
            name,
            config.get("type", "unknown"),
            config.get("host", "unknown"),
            config.get("last_modified", "unknown")
        )
    
    console.print(table)


@app.command()
def connect(
    name: str = typer.Argument(..., help="Connection name"),
    verify: bool = typer.Option(True, "--verify/--no-verify", help="Verify connection before connecting"),
    local_port: int = typer.Option(11434, "--local-port", "-l", help="Local port for Ollama"),
    foreground: bool = typer.Option(False, "--foreground", "-f", help="Run in foreground instead of daemon mode")
):
    """Connect to a configured server"""
    # Check if already running
    if existing_pid := get_saved_pid(name):
        if is_process_running(existing_pid):
            console.print(f"[yellow]Connection {name} is already running (PID: {existing_pid})[/yellow]")
            return
        else:
            remove_pid_file(name)

    config = config_manager.get_connection(name)
    if not config:
        console.print(f"[red]No connection found with name: {name}[/red]")
        return

    ssh_manager = SSHKeyManager()
    
    with Progress() as progress:
        task = progress.add_task(f"Connecting to {name}...", total=100)
        
        # Generate/get SSH key
        key_path, pub_key_path = ssh_manager.generate_key(name)
        progress.update(task, advance=20)
        
        # Show public key and prompt for key setup
        pub_key = ssh_manager.get_public_key_content(name)
        if pub_key:
            console.print("\n[yellow]Public key:[/yellow]")
            console.print(Panel(pub_key, title="Add this to ~/.ssh/authorized_keys on the GPU server"))
            
            # Check if key verification should be attempted
            if verify:
                console.print("\n[yellow]Please add the public key to the server if you haven't already.[/yellow]")
                if typer.confirm("Have you added the public key to the server?", default=False):
                    progress.update(task, description="Testing SSH connection...")
                    if not ssh_manager.test_connection(config['host'], config['port'], key_path):
                        console.print("[red]SSH connection test failed. Please verify your key setup.[/red]")
                        return
                else:
                    console.print("[yellow]Please add the key and try connecting again.[/yellow]")
                    return

        progress.update(task, advance=30, description="Setting up Ollama tunnel...")
        
        # Check if port is already in use
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(('127.0.0.1', local_port))
        except socket.error:
            console.print(f"[red]Port {local_port} is already in use. Please choose a different port.[/red]")
            return
        finally:
            sock.close()
        
        if not foreground:
            # Fork process for daemon mode
            try:
                pid = os.fork()
                if pid > 0:
                    save_pid(name, pid)
                    console.print(f"[green]Connection started in background (PID: {pid})[/green]")
                    console.print(f"[blue]Ollama is available at http://localhost:{local_port}[/blue]")
                    console.print(f"\nUse 'python -m connection_manager status {name}' to check status")
                    console.print(f"Use 'python -m connection_manager stop {name}' to disconnect")
                    return
            except OSError as e:
                console.print(f"[red]Failed to create daemon process: {e}[/red]")
                return

        # Child process or foreground mode
        tunnel_process = ssh_manager.setup_tunnel(
            config['host'],
            config['port'],
            key_path,
            local_port=local_port
        )
        
        if tunnel_process.poll() is not None:
            console.print("[red]Failed to establish tunnel.[/red]")
            return
        
        progress.update(task, completed=100)

    if foreground:
        console.print(f"[green]Successfully connected to {name}![/green]")
        console.print(f"[blue]Ollama is available at http://localhost:{local_port}[/blue]")
        console.print("\nPress Ctrl+C to disconnect...")
        
    try:
        tunnel_process.wait()
    except KeyboardInterrupt:
        tunnel_process.terminate()
        console.print("\n[yellow]Connection terminated.[/yellow]")
    finally:
        if not foreground:
            remove_pid_file(name)

@app.command()
def status(name: Optional[str] = typer.Argument(None, help="Connection name")):
    """Check status of connections"""
    pid_dir = Path.home() / ".connections" / "pids"
    
    if not pid_dir.exists():
        console.print("[yellow]No active connections[/yellow]")
        return

    table = Table(title="Active Connections")
    table.add_column("Name", style="cyan")
    table.add_column("PID", style="blue")
    table.add_column("Status", style="green")

    def check_single_connection(name: str):
        pid = get_saved_pid(name)
        if pid and is_process_running(pid):
            return name, str(pid), "🟢 Running"
        remove_pid_file(name)
        return name, "-", "🔴 Stopped"

    if name:
        name, pid, status = check_single_connection(name)
        table.add_row(name, pid, status)
    else:
        for pid_file in pid_dir.glob("*.pid"):
            name = pid_file.stem
            name, pid, status = check_single_connection(name)
            table.add_row(name, pid, status)

    console.print(table)

@app.command()
def stop(
    name: str = typer.Argument(..., help="Connection name"),
    force: bool = typer.Option(False, "--force", "-f", help="Force stop without confirmation")
):
    """Stop a running connection"""
    pid = get_saved_pid(name)
    if not pid:
        console.print(f"[yellow]No active connection found for {name}[/yellow]")
        return

    if not is_process_running(pid):
        remove_pid_file(name)
        console.print(f"[yellow]Connection {name} is not running[/yellow]")
        return

    if not force and not typer.confirm(f"Stop connection {name} (PID: {pid})?"):
        return

    try:
        os.kill(pid, signal.SIGTERM)
        console.print(f"[green]Successfully stopped connection {name}[/green]")
    except OSError as e:
        console.print(f"[red]Failed to stop connection: {e}[/red]")
    finally:
        remove_pid_file(name)

@app.command()
def delete(
    name: str = typer.Argument(..., help="Connection name"),
    force: bool = typer.Option(False, "--force", "-f", help="Force deletion without confirmation")
):
    """Delete a connection configuration"""
    if not force:
        confirm = typer.confirm(f"Are you sure you want to delete connection '{name}'?")
        if not confirm:
            return

    if config_manager.delete_connection(name):
        console.print(f"[green]Successfully deleted connection: {name}[/green]")
    else:
        console.print(f"[red]No connection found with name: {name}[/red]")

def show_config(config: dict):
    """Display configuration details"""
    table = Table(title="Configuration Summary")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")
    
    for key, value in config.items():
        if key != "last_modified":  # Skip showing timestamp
            table.add_row(key, str(value))
    
    console.print(table)

if __name__ == "__main__":
    app()
