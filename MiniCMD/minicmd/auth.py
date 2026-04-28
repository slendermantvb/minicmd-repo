from .config import SSH_USER, SSH_PASSWORD

def auth(username, password):
    return username == SSH_USER and password == SSH_PASSWORD
