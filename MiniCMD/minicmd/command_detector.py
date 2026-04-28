from difflib import get_close_matches
from .config import COMMADS
from .apt_manager import get_index

INTERNAL_COMMANDS = {
    'help', 'cls', 'pwd', 'whoami', 'id', 'history', 'exit', 'sudo',
    'apt', 'chat',
    'users', 'groups', 'groupadd', 'useradd', 'passwd',
    'ls', 'cd', 'mkdir', 'touch', 'cat', 'write', 'append', 'rm', 'rmdir', 'chmod', 'chown'
}

ALIASES = {
    'clear': 'cls',
    'dir': 'ls',
    'del': 'rm',
    'erase': 'rm',
    'md': 'mkdir',
    'rd': 'rmdir',
    'type': 'cat',
    'echo': 'write',
    'll': 'ls -l',
    'me': 'whoami',
    '?': 'help',
}


def external_commands():
    found = set()
    if COMMADS.exists():
        for item in COMMADS.iterdir():
            if item.is_dir() and (item / 'main.py').exists():
                found.add(item.name.lower())
    return found


def repo_commands():
    found = set()
    for item in get_index():
        if isinstance(item, str):
            found.add(item.lower())
        elif isinstance(item, dict) and item.get('name'):
            found.add(str(item.get('name')).lower())
    return found


def normalize_command(cmd, args):
    original = cmd
    if cmd in ALIASES:
        mapped = ALIASES[cmd]
        parts = mapped.split()
        return parts[0], parts[1:] + args, original
    return cmd, args, original


def detect_command(cmd):
    if cmd in INTERNAL_COMMANDS:
        return 'internal'
    if cmd in external_commands():
        return 'external'
    if cmd in repo_commands():
        return 'available'
    return 'missing'


def suggestion(cmd):
    names = sorted(INTERNAL_COMMANDS | external_commands() | repo_commands() | set(ALIASES.keys()))
    matches = get_close_matches(cmd, names, n=3, cutoff=0.55)
    lines = [f'Comando no encontrado: {cmd}']
    if cmd in repo_commands():
        lines.append(f'Disponible para instalar: sudo apt install {cmd}')
    if matches:
        lines.append('Quizas quisiste decir: ' + ', '.join(matches))
    lines.append('Usa help o apt list para ver comandos disponibles.')
    return '\n'.join(lines)
