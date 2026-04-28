from .users_store import load_users, save_users


def add_account(name, secret, group='users'):
    data = load_users()
    if name in data.get('users', {}):
        return False, 'Usuario ya existe.'
    data.setdefault('groups', {}).setdefault(group, [])
    if name not in data['groups'][group]:
        data['groups'][group].append(name)
    data.setdefault('users', {})[name] = {
        'password': secret,
        'group': group,
        'groups': [group],
        'admin': False
    }
    save_users(data)
    return True, f'Usuario creado: {name}'


def set_account_secret(name, secret):
    data = load_users()
    if name not in data.get('users', {}):
        return False, 'Usuario no existe.'
    data['users'][name]['password'] = secret
    save_users(data)
    return True, 'Password actualizado.'
