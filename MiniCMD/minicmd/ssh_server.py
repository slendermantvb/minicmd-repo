import asyncio
import asyncssh

from .config import *
from .logger import log_event, log_error
from .executor import run
from .auth import auth
from .state import MiniCMDState
from .fs import prompt_path

KEX_ALGS = [
    'curve25519-sha256',
    'curve25519-sha256@libssh.org',
    'ecdh-sha2-nistp256',
    'ecdh-sha2-nistp384',
    'diffie-hellman-group14-sha256',
    'diffie-hellman-group16-sha512',
]

ENCRYPTION_ALGS = [
    'chacha20-poly1305@openssh.com',
    'aes128-gcm@openssh.com',
    'aes256-gcm@openssh.com',
    'aes128-ctr',
    'aes256-ctr',
]

MAC_ALGS = [
    'hmac-sha2-256-etm@openssh.com',
    'hmac-sha2-512-etm@openssh.com',
    'hmac-sha2-256',
    'hmac-sha2-512',
]

SIGNATURE_ALGS = [
    'ssh-ed25519',
    'rsa-sha2-512',
    'rsa-sha2-256',
]


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


def ensure_host_key():
    if not HOST_KEY_FILE.exists():
        try:
            key = asyncssh.generate_private_key('ssh-ed25519')
        except Exception:
            key = asyncssh.generate_private_key('ssh-rsa', 3072)
        HOST_KEY_FILE.write_text(key.export_private_key().decode('utf-8'), encoding='utf-8')
    return str(HOST_KEY_FILE)


class Server(asyncssh.SSHServer):

    def connection_made(self, conn):
        self.conn = conn
        log_event(f'conexion nueva from {_peer_ip(conn)}')

    def connection_lost(self, exc):
        if exc:
            log_error('server connection_lost', exc)
        else:
            log_event('server connection closed')

    def begin_auth(self, username):
        try:
            if _allow_no_password(self.conn):
                self.conn._minicmd_username = username or SSH_USER
                log_event(f'auth bypass user={username or SSH_USER}')
                return False
        except Exception as e:
            log_error('begin_auth crash', e)
        return True

    def password_auth_supported(self):
        try:
            return not _allow_no_password(self.conn)
        except Exception:
            return True

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
        self._last_was_cr = False

    def connection_made(self, chan):
        self.chan = chan
        try:
            conn = chan.get_extra_info('connection')
            self.user = getattr(conn, '_minicmd_username', SSH_USER)
        except Exception:
            self.user = SSH_USER
        self.state = MiniCMDState(self.user)
        log_event(f'session started user={self.user}')

    def connection_lost(self, exc):
        if exc:
            log_error(f'session lost user={self.user}', exc)
        else:
            log_event(f'session closed user={self.user}')

    def pty_requested(self, term_type, term_size, term_modes):
        return True

    def shell_requested(self):
        return True

    def exec_requested(self, command):
        try:
            out = run(command, self.state)
            if out:
                self.chan.write(out + ('\n' if not out.endswith('\n') else ''))
            self.chan.exit(0)
        except Exception as e:
            log_error('exec_requested crash', e)
            self.chan.write('Error interno\n')
            self.chan.exit(1)
        return True

    def session_started(self):
        try:
            self.chan.write('MiniCMD SSH modular\n')
            self.chan.write('Escribe help para ver comandos.\n')
            self.prompt()
        except Exception as e:
            log_error('session_started crash', e)
            try:
                self.chan.write('Error iniciando sesion\n')
            except Exception:
                pass

    def data_received(self, data, datatype):
        try:
            for c in data:
                if c == '\r':
                    self._last_was_cr = True
                    self._submit_line()
                elif c == '\n':
                    if self._last_was_cr:
                        self._last_was_cr = False
                        continue
                    self._submit_line()
                else:
                    self._last_was_cr = False
                    self._handle_char(c)
        except Exception as e:
            log_error('SSH crash', e)
            try:
                self.chan.write('\nError interno\n')
                self.prompt()
            except Exception:
                pass

    def _submit_line(self):
        self.chan.write('\n')
        line = self.buffer.strip()
        self.buffer = ''
        out = run(line, self.state)
        if out:
            self.chan.write(out + ('\n' if not out.endswith('\n') else ''))
        if not self.state.running:
            self.chan.exit(0)
            return
        self.prompt()

    def _handle_char(self, c):
        if c == '\x7f':
            if self.buffer:
                self.buffer = self.buffer[:-1]
                self.chan.write('\b \b')
        elif c == '\x03':
            self.buffer = ''
            self.chan.write('^C\n')
            self.prompt()
        elif c == '\x04':
            self.chan.write('\nCerrando sesion.\n')
            self.chan.exit(0)
        else:
            self.buffer += c
            self.chan.write(c)

    def eof_received(self):
        return False

    def prompt(self):
        self.chan.write(f'{self.user}@mini:{prompt_path(self.state)}$ ')


async def _run():
    key_file = ensure_host_key()
    await asyncssh.create_server(
        Server,
        SSH_HOST,
        SSH_PORT,
        server_host_keys=[key_file],
        session_factory=Session,
        kex_algs=KEX_ALGS,
        encryption_algs=ENCRYPTION_ALGS,
        mac_algs=MAC_ALGS,
        signature_algs=SIGNATURE_ALGS,
    )
    await asyncio.Future()


def start():
    print('MiniCMD SSH iniciado')
    print(f'Host: {SSH_HOST}')
    print(f'Puerto: {SSH_PORT}')
    print(f'No-password: {SSH_NO_PASSWORD} scope={SSH_NO_PASSWORD_SCOPE}')
    print(f'Conectar: ssh {SSH_USER}@127.0.0.1 -p {SSH_PORT}')
    print('Si cambiaste host key vieja, borra MiniCMD/minicmd_ssh_host_key y reinicia.')
    asyncio.run(_run())
