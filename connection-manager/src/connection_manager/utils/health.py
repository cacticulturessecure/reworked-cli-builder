import requests
from typing import Optional, Tuple
from rich.console import Console

console = Console()

def check_ollama_health(port: int) -> Tuple[bool, Optional[str]]:
    """Check if Ollama is responding on the given port"""
    try:
        response = requests.get(f"http://localhost:{port}/api/tags", timeout=5)
        if response.status_code == 200:
            return True, None
        return False, f"Ollama returned status code: {response.status_code}"
    except requests.exceptions.ConnectionError:
        return False, "Could not connect to Ollama"
    except requests.exceptions.Timeout:
        return False, "Connection to Ollama timed out"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"

def verify_port_available(port: int) -> Tuple[bool, Optional[str]]:
    """Check if a port is available for use"""
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(('127.0.0.1', port))
        return True, None
    except socket.error:
        return False, f"Port {port} is already in use"
    finally:
        sock.close()
