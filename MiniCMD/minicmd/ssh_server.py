import asyncio
import asyncssh

from .config import *
from .logger import log_event, log_error
from .executor import run
from .auth import auth
from .state import MiniCMDState
from .fs import prompt_path


def _peer_ip(conn):
    try:
        peer = conn.get_extra_info('peername')
        if isinstance(peer, (list, tuple)) and peer:
            return peer[0]
    except Exception:
        pass
    return None


def _allow_no_password(conn):
    if not SSH_NO_PASSWORD:
        return False
    ip = _peer_ip(conn)
    if SSH_NO_PASSWORD_SCOPE == 'unsafe':
        return True
    return ip in ('127.0.0.1', '::1', None)


class Server(asyncssh.SSHServer):

    def connection_made(self, conn):
        self.conn = conn
        log_event(f'conexion nueva from {_peer_ip(conn)}')

    def connection_lost(self, exc):
        if exc:
            log_error('server connection_lost', exc)

    def begin_auth(self, username):
        if _allow_no_password(self.conn):
            self.conn._minicmd_username = username or SSH_USER
            return False
        return True

    def password_auth_supported(self):
        return not _allow_no_password(self.conn)

    def validate_password(self, username, password):
        try:
            ok = auth(username, password)
            if ok:
                self.conn._minicmd_username = username
            log_event(f"auth {'ok' if ok else 'fail'} user={username}")
            return ok
        except Exception as e:
            log_error('validate_password crash', e)
            return False


class Session(asyncssh.SSHServerSession):

    def __init__(self):
        self.buffer = ''
        self.chan = None
        self.user = SSH_USER
        self.state = MiniCMDState(SSH_USER)

    def connection_made(self, chan):
        self.chan = chan
        try:
            conn = chan.get_extra_info('connection')
            self.user = getattr(conn, '_minicmd_username', SSH_USER)
        except Exception:
            self.user = SSH_USER
        self.state = MiniCMDState(self.user)
        log_event(f'session started user={self.user}')

    def shell_requested(self):
        return True

    def session_started(self):
        self.chan.write('MiniCMD SSH modular\n')
        self.chan.write('Escribe help para ver comandos.\n')
        self.prompt()

    def data_received(self, data, datatype):
        try:
            for c in data:
                if c in ('\r', '\n'):
                    self.chan.write('\n')
                    out = run(self.buffer.strip(), self.state)
                    if out:
                        self.chan.write(out + ('\n' if not out.endswith('\n') else ''))
                    self.buffer = ''
                    if not self.state.running:
                        self.chan.exit(0)
                        return
                    self.prompt()
                elif c == '\x7f':
                    if self.buffer:
                        self.buffer = self.buffer[:-1]
                        self.chan.write('\b \b')
                elif c == '\x03':
                    self.buffer = ''
                    self.chan.write('^C\n')
                    self.prompt()
                else:
                    self.buffer += c
                    self.chan.write(c)
        except Exception as e:
            log_error('SSH crash', e)
            self.chan.write('\nError interno\n')
            self.prompt()

    def prompt(self):
        self.chan.write(f'{self.user}@mini:{prompt_path(self.state)}$ ')


async def _run():
    await asyncssh.create_server(Server, SSH_HOST, SSH_PORT, session_factory=Session)
    await asyncio.Future()


def start():
    print('MiniCMD SSH iniciado')
    print(f'Host: {SSH_HOST}')
    print(f'Puerto: {SSH_PORT}')
    print(f'No-password: {SSH_NO_PASSWORD} scope={SSH_NO_PASSWORD_SCOPE}')
    asyncio.run(_run())
