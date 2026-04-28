from .config import USERS_FILE
from .storage import load_json, save_json


def load_users():
    data = load_json(USERS_FILE, None)
    if not data:
        data = {
            'users': {
                'admin': {
                    'password': 'minicmd123',
                    'group': 'root',
                    'groups': ['root'],
                    'admin': True
                }
            },
            'groups': {
                'root': ['admin'],
                'users': []
            }
        }
        save_json(USERS_FILE, data)
    data.setdefault('users', {})
    data.setdefault('groups', {})
    return data


def save_users(data):
    save_json(USERS_FILE, data)


def user_info(username):
    return load_users().get('users', {}).get(username)


def user_groups(username):
    info = user_info(username) or {}
    groups = set(info.get('groups', []))
    if info.get('group'):
        groups.add(info.get('group'))
    return groups
