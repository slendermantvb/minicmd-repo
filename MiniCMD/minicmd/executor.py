import shlex

from .commands_system import run_system, HELP as SYSTEM_HELP
from .commands_apt import run_apt
from .commands_files import run_files
from .commands_users import run_users
from .legacy_runner import run_legacy
from .state import MiniCMDState
from .users_store import user_info, user_groups

_DEFAULT_STATE = MiniCMDState()


def run(command, state=None):
    if state is None:
        state = _DEFAULT_STATE
    return execute(command, state)


def execute(command, state):
    command = (command or '').strip()
    if not command:
        return ''

    state.history.append(command)
    state.history = state.history[-100:]

    try:
        parts = shlex.split(command)
    except Exception:
        return 'Error: comillas invalidas.'

    if not parts:
        return ''

    cmd = parts[0].lower()
    args = parts[1:]

    if cmd == 'help':
        base = run_system(cmd, args, state, user_info, user_groups)
        extra = [
            '',
            'Archivos:',
            '  ls [-l] [ruta], cd <ruta>, mkdir <dir>, touch <file>',
            '  cat <file>, write <file> <texto>, append <file> <texto>',
            '  rm <file>, rmdir <dir>, chmod 755 <ruta>, chown user[:group] <ruta>',
            '',
            'Usuarios:',
            '  users, groups, groupadd <grupo>, useradd <user> <pass> [grupo]',
            '',
            'APT:',
            '  apt list',
            '  sudo 1234',
            '  sudo apt install <comando>',
            '',
            'Legacy:',
            '  comandos en commads/<comando>/main.py funcionan igual',
        ]
        return base + '\n' + '\n'.join(extra)

    try:
        for handler in (
            lambda: run_apt(cmd, args, state),
            lambda: run_system(cmd, args, state, user_info, user_groups),
            lambda: run_users(cmd, args, state),
            lambda: run_files(cmd, args, state, user_info, user_groups),
        ):
            result = handler()
            if result is not None:
                return result

        legacy = run_legacy(state, cmd, args)
        if legacy is not None:
            return legacy

        return f'Comando no encontrado: {cmd}'

    except PermissionError as e:
        return f'Permiso denegado: {e}'
    except Exception as e:
        return f'Error: {e}'
