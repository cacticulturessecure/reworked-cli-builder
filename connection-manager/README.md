# Connection Manager

A CLI tool for managing SSH tunnels to remote servers, with specific support for Ollama GPU servers.

## Features
- Interactive setup wizard
- SSH key management
- Background daemon mode
- Connection status monitoring
- Port availability checking
- Multiple connection support

## Installation
```bash
pip install -e .
Usage
Setup a new connection
bashCopypython -m connection_manager setup
List configured connections
bashCopypython -m connection_manager list
Connect to a server
bashCopy# Background mode (default)
python -m connection_manager connect <name>

# Foreground mode
python -m connection_manager connect <name> --foreground

# Custom port
python -m connection_manager connect <name> --local-port 8080
Check connection status
bashCopypython -m connection_manager status
Stop a connection
bashCopypython -m connection_manager stop <name>
Delete a connection
bashCopypython -m connection_manager delete <name>
Configuration
Configurations are stored in ~/.connections/:

config.json: Connection configurations
keys/: SSH keys
pids/: Process IDs for daemon mode

Development
To contribute:

Clone the repository
Create a virtual environment
Install dependencies: pip install -e .
Make changes
Test thoroughly

License
MIT
