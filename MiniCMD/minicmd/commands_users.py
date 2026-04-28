from .permissions import is_admin
from .users_store import load_users, save_users, user_info


def run_users(cmd, args, state):
    if cmd == 'users':
        users = load_users()
        lines = []
        for name, info in users.get('users', {}).items():
            admin = 'yes' if info.get('admin') else 'no'
            lines.append(f"{name:<12} group={info.get('group','users'):<10} admin={admin}")
        return '\n'.join(lines)
    if cmd == 'groups':
        users = load_users()
        lines = []
        for group, members in users.get('groups', {}).items():
            lines.append(f"{group}: {', '.join(members)}")
        return '\n'.join(lines)
    if cmd == 'groupadd':
        if len(args) != 1:
            return 'Uso: groupadd <grupo>'
        if not is_admin(state, user_info):
            return 'Solo admin/sudo puede crear grupos.'
        users = load_users()
        users.setdefault('groups', {}).setdefault(args[0], [])
        save_users(users)
        return f'Grupo creado: {args[0]}'
    return None
