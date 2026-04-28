from .relay_client import push, pull, peek, flush, status, make_chat_message, format_chat_message, RELAY_URL

DEFAULT_CHANNEL = 'chat'


def run_chat(cmd, args, state):
    if cmd != 'chat':
        return None

    if not args:
        return help_text()

    action = args[0].lower()

    if action == 'send':
        if len(args) < 2:
            return 'Uso: chat send <mensaje> | chat send <canal> <mensaje>'
        if len(args) >= 3:
            channel = args[1]
            text = ' '.join(args[2:])
        else:
            channel = DEFAULT_CHANNEL
            text = ' '.join(args[1:])
        ok, msg = push(channel, make_chat_message(state.username, text))
        return msg

    if action == 'pull':
        channel = args[1] if len(args) >= 2 else DEFAULT_CHANNEL
        ok, data = pull(channel)
        if not ok:
            return data
        if not data:
            return f'Sin mensajes en {channel}.'
        return '\n'.join(format_chat_message(x) for x in data)

    if action == 'peek':
        channel = args[1] if len(args) >= 2 else DEFAULT_CHANNEL
        ok, data = peek(channel)
        if not ok:
            return data
        if not data:
            return f'Sin mensajes en {channel}.'
        return '\n'.join(format_chat_message(x) for x in data)

    if action == 'flush':
        channel = args[1] if len(args) >= 2 else DEFAULT_CHANNEL
        ok, msg = flush(channel)
        return msg

    if action == 'status':
        ok, data = status()
        if not ok:
            return data
        return '\n'.join([
            f'Relay: {RELAY_URL}',
            f"Status: {data.get('status', 'unknown')}",
            f"Channels: {data.get('channels', 0)}",
            f"Packets: {data.get('packets', 0)}",
        ])

    return help_text()


def help_text():
    return '\n'.join([
        'Chat Relay MiniCMD',
        'Uso:',
        '  chat send <mensaje>',
        '  chat send <canal> <mensaje>',
        '  chat pull [canal]     lee y borra mensajes',
        '  chat peek [canal]     lee sin borrar',
        '  chat flush [canal]    limpia canal',
        '  chat status',
    ])
