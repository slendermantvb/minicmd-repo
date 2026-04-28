# MiniCMD/minicmd/unix_layer.py
# Capa Unix para MiniCMD. No usa subprocess.

import time
import shutil

UNIX_BUILTINS = {
    "clear", "echo", "date", "uname", "cp", "mv", "grep", "head", "tail", "tree"
}

UNIX_HELP = {
    "clear": "Alias de cls. Limpia pantalla.",
    "echo": "Muestra texto. Uso: echo <texto>",
    "date": "Muestra fecha y hora. Uso: date",
    "uname": "Muestra informacion del sistema. Uso: uname [-a]",
    "cp": "Copia archivo. Uso: cp <origen> <destino>",
    "mv": "Mueve o renombra. Uso: mv <origen> <destino>",
    "grep": "Busca texto. Uso: grep <texto> <archivo>",
    "head": "Muestra primeras lineas. Uso: head <archivo> [n]",
    "tail": "Muestra ultimas lineas. Uso: tail <archivo> [n]",
    "tree": "Muestra carpetas como arbol. Uso: tree [ruta]",
}


def unix_prompt(state, is_admin_func):
    path = "~" if not state.cwd else "~/" + state.cwd.replace("\\", "/")
    symbol = "#" if state.sudo or is_admin_func(state) else "$"
    return f"{state.username}@minicmd:{path}{symbol}"


def _lines(text):
    return str(text or "").splitlines()


def _read_file(state, path, require_perm):
    if not path.is_file():
        return None, "No es archivo."
    require_perm(state, path, "r")
    return path.read_text(encoding="utf-8", errors="replace"), None


def tree_command(state, args, safe_path_from_cwd, require_perm):
    path_arg = args[0] if args else "."
    target = safe_path_from_cwd(state, path_arg)
    if not target.exists():
        return "Ruta no existe."
    if target.is_file():
        require_perm(state, target, "r")
        return target.name
    require_perm(state, target, "r")
    require_perm(state, target, "x")
    lines = [target.name + "/"]

    def walk(folder, prefix=""):
        items = sorted(folder.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        for i, item in enumerate(items):
            connector = "└── " if i == len(items) - 1 else "├── "
            lines.append(prefix + connector + item.name + ("/" if item.is_dir() else ""))
            if item.is_dir():
                try:
                    require_perm(state, item, "r")
                    require_perm(state, item, "x")
                    extension = "    " if i == len(items) - 1 else "│   "
                    walk(item, prefix + extension)
                except Exception:
                    extension = "    " if i == len(items) - 1 else "│   "
                    lines.append(prefix + extension + "└── [permiso denegado]")

    walk(target)
    return "\n".join(lines)


def execute_unix_command(state, cmd, args, *, safe_path_from_cwd, require_perm, ensure_meta, set_meta, delete_meta, user_info):
    if cmd == "clear":
        return "\033[2J\033[H"
    if cmd == "echo":
        return " ".join(args)
    if cmd == "date":
        return time.strftime("%a %b %d %H:%M:%S %Y")
    if cmd == "uname":
        return "MiniCMD minicmd 1.0 UnixLayer python ssh" if args and args[0] == "-a" else "MiniCMD"

    if cmd == "cp":
        if len(args) != 2:
            return "Uso: cp <origen> <destino>"
        src = safe_path_from_cwd(state, args[0])
        dst = safe_path_from_cwd(state, args[1])
        if not src.is_file():
            return "Origen no es archivo."
        require_perm(state, src, "r")
        require_perm(state, dst.parent, "w")
        require_perm(state, dst.parent, "x")
        shutil.copy2(src, dst)
        group = (user_info(state.username) or {}).get("group", "users")
        ensure_meta(dst, state.username, group)
        return f"Copiado: {args[0]} -> {args[1]}"

    if cmd == "mv":
        if len(args) != 2:
            return "Uso: mv <origen> <destino>"
        src = safe_path_from_cwd(state, args[0])
        dst = safe_path_from_cwd(state, args[1])
        if not src.exists():
            return "Origen no existe."
        require_perm(state, src.parent, "w")
        require_perm(state, src.parent, "x")
        require_perm(state, dst.parent, "w")
        require_perm(state, dst.parent, "x")
        old_meta = ensure_meta(src)
        shutil.move(str(src), str(dst))
        set_meta(dst, old_meta)
        delete_meta(src)
        return f"Movido: {args[0]} -> {args[1]}"

    if cmd == "grep":
        if len(args) != 2:
            return "Uso: grep <texto> <archivo>"
        text, error = _read_file(state, safe_path_from_cwd(state, args[1]), require_perm)
        if error:
            return error
        needle = args[0].lower()
        return "\n".join([line for line in _lines(text) if needle in line.lower()])

    if cmd == "head":
        if not args:
            return "Uso: head <archivo> [n]"
        n = int(args[1]) if len(args) > 1 and args[1].isdigit() else 10
        text, error = _read_file(state, safe_path_from_cwd(state, args[0]), require_perm)
        if error:
            return error
        return "\n".join(_lines(text)[:n])

    if cmd == "tail":
        if not args:
            return "Uso: tail <archivo> [n]"
        n = int(args[1]) if len(args) > 1 and args[1].isdigit() else 10
        text, error = _read_file(state, safe_path_from_cwd(state, args[0]), require_perm)
        if error:
            return error
        return "\n".join(_lines(text)[-n:])

    if cmd == "tree":
        return tree_command(state, args, safe_path_from_cwd, require_perm)

    return None
