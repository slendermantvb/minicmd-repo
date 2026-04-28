import os
from .config import ROOT


def prompt_path(state):
    if state.cwd:
        return '/system/' + state.cwd.replace('\\', '/')
    return '/system'


def safe_path(state, extra=''):
    base = (ROOT / state.cwd).resolve()
    final = (base / extra).resolve()
    try:
        final.relative_to(ROOT.resolve())
    except ValueError:
        state.cwd = ''
        raise ValueError('Acceso denegado fuera de /system')
    return final


def cd(state, target):
    if target in ['\\', '/', 'C:\\system', 'c:\\system', '/system']:
        state.cwd = ''
        return ''
    if target == '..':
        parent = os.path.dirname(state.cwd).replace('\\', '/')
        state.cwd = '' if parent == '.' else parent
        return ''
    new_path = safe_path(state, target)
    if not new_path.is_dir():
        return 'La carpeta no existe.'
    relative = os.path.relpath(new_path, ROOT)
    state.cwd = '' if relative == '.' else relative.replace('\\', '/')
    return ''
