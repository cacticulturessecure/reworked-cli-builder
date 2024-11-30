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

# Create the Typer app with a name and description
app = typer.Typer(
    name="connection-manager",
    help="A CLI tool for managing SSH tunnels to remote servers"
)
console = Console()
config_manager = ConfigManager()

@app.command()
def setup():
    """Interactive setup for new connection"""
    console.print(Panel.fit("Connection Setup Wizard", style="bold blue"))
    
    async def interactive_setup():
        name = await inquirer.text(
            message="Enter connection name:",
            validate=lambda x: len(x) > 0 and x.isalnum(),
            invalid_message="Name must be non-empty and alphanumeric"
        ).execute_async()

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

        config = {
            "name": name,
            "host": host,
            "port": port,
        }
        return name, config

    name, config = asyncio.run(interactive_setup())
    
    with Progress() as progress:
        task = progress.add_task("Creating configuration...", total=100)
        config_manager.save_connection(name, config)
        progress.update(task, completed=100)
    
    console.print("[green]Setup complete![/green]")
    console.print("\n[blue]Next steps:[/blue]")
    console.print(f"1. Run 'python -m connection_manager setup-key {name}' to generate SSH key")

@app.command()
def setup_key(
    name: str = typer.Argument(..., help="Connection name"),
    force: bool = typer.Option(False, "--force", "-f", help="Force regenerate key even if it exists")
):
    """Generate SSH key for a connection"""
    config = config_manager.get_connection(name)
    if not config:
        console.print(f"[red]No connection found with name: {name}[/red]")
        return

    ssh_manager = SSHKeyManager()
    
    with Progress() as progress:
        task = progress.add_task("Generating SSH key...", total=100)
        
        # Generate SSH key
        key_path, pub_key_path = ssh_manager.generate_key(name, force=force)
        progress.update(task, completed=100)
    
    # Show the public key
    pub_key = pub_key_path.read_text().strip() if pub_key_path.exists() else None
    if pub_key:
        console.print("\n[yellow]Public key:[/yellow]")
        console.print(Panel(pub_key, title="Add this to ~/.ssh/authorized_keys on the server"))
        console.print("\n[blue]Next steps:[/blue]")
        console.print("1. Add this public key to ~/.ssh/authorized_keys on your server")
        console.print(f"2. Run 'python -m connection_manager verify-key {name}' to test the connection")

@app.command()
def verify_key(
    name: str = typer.Argument(..., help="Connection name"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show verbose SSH output")
):
    """Verify SSH key connection"""
    config = config_manager.get_connection(name)
    if not config:
        console.print(f"[red]No connection found with name: {name}[/red]")
        return

    ssh_manager = SSHKeyManager()
    key_path = ssh_manager.get_key_path(name)
    
    if not key_path.exists():
        console.print(f"[red]No SSH key found for {name}. Run 'setup-key {name}' first.[/red]")
        return
    
    console.print("[yellow]Testing SSH connection...[/yellow]")
    if ssh_manager.test_connection(config['host'], config['port'], key_path, verbose=verbose):
        console.print("[green]SSH connection successful![/green]")
        console.print("\n[blue]Next steps:[/blue]")
        console.print(f"Run 'python -m connection_manager connect {name}' to establish the tunnel")
    else:
        console.print("[red]SSH connection failed. Please verify your key is properly set up on the server.[/red]")

@app.command()
def list():
    """List all configured connections"""
    connections = config_manager.load_connections()
    if not connections:
        console.print("[yellow]No connections configured yet.[/yellow]")
        return

    table = Table(title="Configured Connections")
    table.add_column("Name", style="cyan")
    table.add_column("Host", style="green")
    table.add_column("Port", style="blue")
    
    for name, config in connections.items():
        table.add_row(
            name,
            config.get("host", "unknown"),
            str(config.get("port", "unknown"))
        )
    
    console.print(table)

@app.command()
def connect(
    name: str = typer.Argument(..., help="Connection name"),
    local_port: int = typer.Option(11434, "--local-port", "-l", help="Local port for Ollama"),
    foreground: bool = typer.Option(False, "--foreground", "-f", help="Run in foreground mode")
):
    """Connect to a configured server"""
    config = config_manager.get_connection(name)
    if not config:
        console.print(f"[red]No connection found with name: {name}[/red]")
        return

    ssh_manager = SSHKeyManager()
    key_path = ssh_manager.get_key_path(name)
    
    if not key_path.exists():
        console.print(f"[red]No SSH key found for {name}. Run 'setup-key {name}' first.[/red]")
        return
    
    with Progress() as progress:
        task = progress.add_task(f"Connecting to {name}...", total=100)
        
        # Setup the tunnel
        tunnel_process = ssh_manager.setup_tunnel(
            config['host'],
            config['port'],
            key_path,
            local_port=local_port
        )
        
        if tunnel_process is None:
            console.print("[red]Failed to establish tunnel.[/red]")
            return
        
        progress.update(task, completed=100)

    console.print(f"[green]Successfully connected to {name}![/green]")
    console.print(f"[blue]Ollama is available at http://localhost:{local_port}[/blue]")
    
    if foreground:
        console.print("\nPress Ctrl+C to disconnect...")
        try:
            tunnel_process.wait()
        except KeyboardInterrupt:
            tunnel_process.terminate()
            console.print("\n[yellow]Connection terminated.[/yellow]")

def main():
    app()

if __name__ == "__main__":
    main()
