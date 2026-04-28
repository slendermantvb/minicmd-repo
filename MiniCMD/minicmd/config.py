import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).resolve().parents[1]

ROOT = BASE_DIR / "system"
COMMADS = BASE_DIR / "commads"
LOGS = BASE_DIR / "logs"
DB_FILE = COMMADS / ".installed.json"
USERS_FILE = BASE_DIR / "users.json"
PERMS_FILE = BASE_DIR / "permissions.json"
HOST_KEY_FILE = BASE_DIR / "minicmd_ssh_host_key"
ERROR_LOG_FILE = LOGS / "errors.log"
SESSION_LOG_FILE = LOGS / "sessions.log"

ROOT.mkdir(exist_ok=True)
COMMADS.mkdir(exist_ok=True)
LOGS.mkdir(exist_ok=True)

SSH_HOST = os.environ.get("MINICMD_SSH_HOST", "0.0.0.0")
SSH_PORT = int(os.environ.get("MINICMD_SSH_PORT", "2222"))
SSH_USER = os.environ.get("MINICMD_SSH_USER", "admin")
SSH_PASSWORD = os.environ.get("MINICMD_SSH_PASSWORD", "minicmd123")
SUDO_PASSWORD = os.environ.get("MINICMD_SUDO_PASSWORD", "1234")
MAX_COMMAND_LEN = int(os.environ.get("MINICMD_MAX_COMMAND_LEN", "4096"))
GITHUB_RAW_BASE = os.environ.get("MINICMD_REPO_RAW", "https://raw.githubusercontent.com/animix-software/minicmd-repo/main/commads")

# Solo para pruebas. Por defecto esta apagado.
# local: permite entrar sin password solo desde 127.0.0.1 / ::1.
# unsafe: permite sin password desde cualquier IP. No recomendado.
SSH_NO_PASSWORD = os.environ.get("MINICMD_SSH_NO_PASSWORD", "0").lower() in ["1", "true", "yes", "on"]
SSH_NO_PASSWORD_SCOPE = os.environ.get("MINICMD_SSH_NO_PASSWORD_SCOPE", "local").lower()
