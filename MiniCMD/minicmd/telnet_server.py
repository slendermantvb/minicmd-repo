import asyncio
import os

from .executor import run
from .state import MiniCMDState
from .fs import prompt_path
from .logger import log_event, log_error

TELNET_HOST = os.environ.get('MINICMD_TELNET_HOST', '0.0.0.0')
TELNET_PORT = int(os.environ.get('MINICMD_TELNET_PORT', '2323'))
TELNET_USER = os.environ.get('MINICMD_TELNET_USER', 'admin')
TELNET_PASSWORD = os.environ.get('MINICMD_TELNET_PASSWORD', 'minicmd123')
TELNET_NO_PASSWORD = os.environ.get('MINICMD_TELNET_NO_PASSWORD', '0').lower() in ['1', 'true', 'yes', 'on']
TELNET_NO_PASSWORD_SCOPE = os.environ.get('MINICMD_TELNET_NO_PASSWORD_SCOPE', 'local').lower()
MAX_LINE = int(os.environ.get('MINICMD_TELNET_MAX_LINE', '4096'))

IAC = 255
DONT = 254
DO = 253
WONT = 252
WILL = 251
ECHO = 1
SUPPRESS_GO_AHEAD = 3


def is_local(peer):
    if not peer:
        return True
    ip = peer[0]
    return ip in ('127.0.0.1', '::1', 'localhost')


def allow_no_password(peer):
    if not TELNET_NO_PASSWORD:
        return False
    if TELNET_NO_PASSWORD_SCOPE == 'unsafe':
        return True
    return is_local(peer)


def telnet_cmd(*items):
    return bytes([IAC, *items])


async def setup_telnet(writer):
    # El servidor hace eco para que clientes sin eco local muestren texto.
    # Si el cliente acepta WILL ECHO, evita letras invisibles.
    writer.write(telnet_cmd(WILL, ECHO))
    writer.write(telnet_cmd(WILL, SUPPRESS_GO_AHEAD))
    await writer.drain()


def clean_telnet_bytes(data):
    out = bytearray()
    i = 0
    while i < len(data):
        b = data[i]
        if b == IAC:
            if i + 2 < len(data):
                i += 3
            else:
                i += 1
            continue
        out.append(b)
        i += 1
    return out.decode('utf-8', errors='replace')


async def write(writer, text='', newline=True):
    value = str(text)
    if newline:
        value += '\r\n'
    value = value.replace('\n', '\r\n')
    writer.write(value.encode('utf-8', errors='replace'))
    await writer.drain()


async def prompt_write(writer, text):
    writer.write(str(text).encode('utf-8', errors='replace'))
    await writer.drain()


async def read_line(reader, writer, hidden=False):
    buf = ''
    while True:
        data = await reader.read(128)
        if not data:
            return None
        text = clean_telnet_bytes(data)
        for ch in text:
            if ch in ('\r', '\n'):
                await write(writer, '')
                return buf.strip()
            if ch == '\x7f' or ch == '\b':
                if buf:
                    buf = buf[:-1]
                    if not hidden:
                        writer.write(b'\b \b')
                        await writer.drain()
            elif ch == '\x03':
                buf = ''
                await write(writer, '^C')
                return ''
            else:
                if len(buf) < MAX_LINE:
                    buf += ch
                    if not hidden:
                        writer.write(ch.encode('utf-8', errors='replace'))
                        await writer.drain()


async def login(reader, writer, peer):
    if allow_no_password(peer):
        await write(writer, 'Modo sin password activado')
        return TELNET_USER
    await write(writer, 'MiniCMD Telnet login')
    await prompt_write(writer, 'Usuario: ')
    user = await read_line(reader, writer)
    if user is None:
        return None
    await prompt_write(writer, 'Password: ')
    secret = await read_line(reader, writer, hidden=True)
    if secret is None:
        return None
    if user == TELNET_USER and secret == TELNET_PASSWORD:
        return user
    await write(writer, 'Login incorrecto')
    return None


async def handle_client(reader, writer):
    peer = writer.get_extra_info('peername')
    log_event(f'telnet connection from {peer}')
    try:
        await setup_telnet(writer)
        username = await login(reader, writer, peer)
        if not username:
            writer.close()
            await writer.wait_closed()
            return
        state = MiniCMDState(username)
        await write(writer, 'MiniCMD Telnet modular')
        await write(writer, 'Escribe help para ver comandos.')
        while state.running:
            await prompt_write(writer, f'{username}@mini:{prompt_path(state)}$ ')
            line = await read_line(reader, writer)
            if line is None:
                break
            try:
                out = run(line, state)
            except Exception as e:
                log_error('telnet command crash', e)
                out = 'Error interno.'
            if out:
                await write(writer, out)
        await write(writer, 'Sesion cerrada')
    except Exception as e:
        log_error('telnet session crash', e)
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass
        log_event(f'telnet closed from {peer}')


async def _run():
    server = await asyncio.start_server(handle_client, TELNET_HOST, TELNET_PORT)
    async with server:
        await server.serve_forever()


def start():
    print('MiniCMD Telnet iniciado')
    print(f'Host: {TELNET_HOST}')
    print(f'Puerto: {TELNET_PORT}')
    print(f'No-password: {TELNET_NO_PASSWORD} scope={TELNET_NO_PASSWORD_SCOPE}')
    print(f'Conectar: telnet 127.0.0.1 {TELNET_PORT}')
    asyncio.run(_run())
