from flask import Flask, request, jsonify, send_from_directory, session
import os
import sys
import json
import time
import shlex
import shutil
import hashlib
import urllib.request
import urllib.error
import threading
import webbrowser
import runpy
import io
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

app = Flask(__name__)
app.secret_key = "minicmd_secret_key"

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).resolve().parent

ROOT = BASE_DIR / "system"
COMMADS = BASE_DIR / "commads"
WEB = BASE_DIR / "web"
LOGS = BASE_DIR / "logs"
DB_FILE = COMMADS / ".installed.json"

ROOT.mkdir(exist_ok=True)
COMMADS.mkdir(exist_ok=True)
WEB.mkdir(exist_ok=True)
LOGS.mkdir(exist_ok=True)

SUDO_PASSWORD = "1234"
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/slendermantvb/minicmd-repo/main/commads"

BUILTINS = {"help", "cls", "sudo", "cd", "pwd", "history"}

BUILTIN_HELP = {
    "help": "Muestra esta ayuda por páginas. Uso: help [pagina]",
    "cls": "Limpia la pantalla.",
    "sudo": "Admin e instalador GitHub.",
    "cd": "Cambia de carpeta dentro de C:\\system.",
    "pwd": "Muestra la ruta actual.",
    "history": "Muestra historial de comandos."
}


def now_date():
    return time.strftime("%Y-%m-%d")


def load_db():
    if not DB_FILE.exists():
        return {"installed": {}}
    try:
        return json.loads(DB_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"installed": {}}


def save_db(db):
    DB_FILE.write_text(
        json.dumps(db, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def log_event(text):
    with open(LOGS / "minicmd.log", "a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {text}\n")


def valid_name(name):
    if not name:
        return False

    if len(name) > 64:
        return False

    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
    return all(c in allowed for c in name)


def download_text(url):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "MiniCMD-Installer"}
    )

    with urllib.request.urlopen(req, timeout=20) as response:
        data = response.read(500_001)

        if len(data) > 500_000:
            raise RuntimeError("Archivo demasiado grande")

        return data.decode("utf-8")


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def repo_url(path):
    return f"{GITHUB_RAW_BASE}/{path}"


def extract_description_from_code(code):
    for line in code.splitlines():
        line = line.strip()

        if line.startswith("DESCRIPTION"):
            try:
                _, right = line.split("=", 1)
                return right.strip().strip('"').strip("'")
            except Exception:
                return ""

    return ""


def init_session():
    session.setdefault("cwd", "")
    session.setdefault("sudo", False)
    session.setdefault("history", [])


def get_prompt():
    cwd = session.get("cwd", "")

    if cwd:
        return "/system/" + cwd.replace("\\", "/")

    return "/system"


def safe_path_from_cwd(extra=""):
    cwd = session.get("cwd", "")
    base = (ROOT / cwd).resolve()
    final = (base / extra).resolve()

    root_resolved = ROOT.resolve()

    try:
        final.relative_to(root_resolved)
    except ValueError:
        session["cwd"] = ""
        raise ValueError("Acceso denegado fuera de /system")

    return final


def get_repo_index():
    try:
        text = download_text(repo_url("index.json"))
        data = json.loads(text)

        commands = data.get("commands", [])
        clean = []

        for item in commands:
            if isinstance(item, str) and valid_name(item):
                clean.append({
                    "name": item,
                    "description": "",
                    "entry": "main.py",
                    "category": "legacy"
                })

            elif isinstance(item, dict):
                name = item.get("name", "")
                entry = item.get("entry", "main.py")

                if valid_name(name) and entry == "main.py":
                    clean.append({
                        "name": name,
                        "description": item.get("description", ""),
                        "entry": entry,
                        "category": item.get("category", "legacy")
                    })

        return clean

    except Exception:
        return []


def get_manifest(command_name):
    try:
        text = download_text(repo_url(f"{command_name}/manifest.json"))
        data = json.loads(text)

        if data.get("name") != command_name:
            return None

        return data

    except Exception:
        return None


def validate_command_code(code):
    if "DESCRIPTION" not in code:
        return False, "El comando debe tener DESCRIPTION."

    blocked = [
        "os.system",
        "subprocess.",
        "shutil.rmtree",
        "socket.",
        "requests.",
        "urllib.",
        "eval(",
        "exec(",
        "__import__"
    ]

    for bad in blocked:
        if bad in code:
            return False, f"Código bloqueado: {bad}"

    return True, "OK"


def install_command(command_name, update=False):
    command_name = command_name.lower()

    if not valid_name(command_name):
        return False, "Nombre de comando no permitido."

    if command_name in BUILTINS:
        return False, "No puedes instalar encima de un comando interno."

    try:
        manifest = get_manifest(command_name)

        entry = "main.py"
        legacy = False

        if manifest:
            entry = manifest.get("entry", "main.py")

            if entry != "main.py":
                return False, "Solo se permite entry: main.py"

            description = manifest.get("description", "")
            version = manifest.get("version", "1.0.0")
            author = manifest.get("author", "")
            category = manifest.get("category", "normal")
            expected = manifest.get("sha256", "")

        else:
            legacy = True
            description = ""
            version = now_date()
            author = "desconocido"
            category = "legacy"
            expected = ""

        code = download_text(repo_url(f"{command_name}/{entry}"))

        ok, msg = validate_command_code(code)

        if not ok:
            return False, f"Instalación cancelada: {msg}"

        if legacy:
            description = extract_description_from_code(code)

            if not description:
                return False, "Comando legacy cancelado: no tiene DESCRIPTION interno."

        checksum = sha256_text(code)

        if expected and expected != checksum:
            return False, "Checksum incorrecto. Archivo no confiable."

        command_folder = COMMADS / command_name
        command_folder.mkdir(exist_ok=True)

        final_manifest = {
            "name": command_name,
            "version": version,
            "author": author,
            "description": description,
            "entry": "main.py",
            "sha256": checksum,
            "category": category,
            "legacy": legacy,
            "updated_date": now_date()
        }

        (command_folder / "manifest.json").write_text(
            json.dumps(final_manifest, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

        (command_folder / "main.py").write_text(code, encoding="utf-8")

        db = load_db()
        now = int(time.time())
        old = db["installed"].get(command_name, {})

        db["installed"][command_name] = {
            "name": command_name,
            "source": repo_url(f"{command_name}/{entry}"),
            "sha256": checksum,
            "installed_at": old.get("installed_at", now),
            "updated_at": now,
            "updated_date": now_date(),
            "description": description,
            "version": version,
            "author": author,
            "entry": "main.py",
            "category": category,
            "legacy": legacy
        }

        save_db(db)
        log_event(f"{'updated' if update else 'installed'} {command_name}")

        if legacy:
            return True, f"Comando {'actualizado' if update else 'instalado'} legacy: {command_name}"

        return True, f"Comando {'actualizado' if update else 'instalado'}: {command_name}"

    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False, f"No existe en GitHub: {command_name}/main.py"

        return False, f"HTTP Error {e.code}"

    except Exception as e:
        return False, f"No se pudo instalar {command_name}: {e}"


def remove_command(command_name):
    command_name = command_name.lower()

    if not valid_name(command_name):
        return False, "Nombre no permitido."

    if command_name in BUILTINS:
        return False, "No puedes eliminar comandos internos."

    path = COMMADS / command_name

    if not path.exists():
        return False, "Ese comando no está instalado."

    shutil.rmtree(path)

    db = load_db()
    db["installed"].pop(command_name, None)
    save_db(db)

    log_event(f"removed {command_name}")

    return True, f"Comando eliminado: {command_name}"


def get_external_help():
    commands = {}
    db = load_db().get("installed", {})

    for folder in COMMADS.iterdir():
        if not folder.is_dir():
            continue

        manifest_path = folder / "manifest.json"

        if not manifest_path.exists():
            continue

        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))

            name = data.get("name", folder.name)
            description = data.get("description", "")
            version = data.get("version", "")
            category = data.get("category", "normal")
            legacy = data.get("legacy", False)

            if legacy:
                version = db.get(name, {}).get("updated_date", data.get("updated_date", now_date()))

            if description:
                commands[name] = {
                    "description": description,
                    "version": version,
                    "category": category,
                    "legacy": legacy
                }

        except Exception:
            pass

    return commands


def run_external_command(cmd, args):
    command_folder = COMMADS / cmd
    script_path = command_folder / "main.py"

    if not script_path.exists():
        return None

    old_argv = sys.argv[:]
    old_cwd = os.getcwd()

    env_backup = {
        "MINICMD_ROOT": os.environ.get("MINICMD_ROOT"),
        "MINICMD_CWD": os.environ.get("MINICMD_CWD"),
        "MINICMD_SUDO": os.environ.get("MINICMD_SUDO")
    }

    stdout = io.StringIO()
    stderr = io.StringIO()

    try:
        current_dir = safe_path_from_cwd()

        os.environ["MINICMD_ROOT"] = str(ROOT.resolve())
        os.environ["MINICMD_CWD"] = str(current_dir)
        os.environ["MINICMD_SUDO"] = "1" if session.get("sudo") else "0"

        sys.argv = [str(script_path)] + args
        os.chdir(str(current_dir))

        with redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                runpy.run_path(str(script_path), run_name="__main__")
            except SystemExit:
                pass

        output = stdout.getvalue().strip()
        error = stderr.getvalue().strip()

        if error:
            output += ("\n" if output else "") + error

        return output

    except Exception as e:
        return f"Error ejecutando comando: {e}"

    finally:
        sys.argv = old_argv
        os.chdir(old_cwd)

        for key, value in env_backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@app.route("/")
def index():
    index_path = WEB / "index.html"

    if not index_path.exists():
        return f"No se encontró index.html en: {index_path}", 404

    return send_from_directory(str(WEB), "index.html")


@app.route("/run", methods=["POST"])
def run():
    init_session()

    data = request.json or {}
    raw = data.get("command", "").strip()

    if not raw:
        return jsonify({"output": "", "prompt": get_prompt()})

    history = session.get("history", [])
    history.append(raw)
    session["history"] = history[-100:]

    try:
        parts = shlex.split(raw)
    except Exception:
        return jsonify({"output": "Error: comillas inválidas.", "prompt": get_prompt()})

    if not parts:
        return jsonify({"output": "", "prompt": get_prompt()})

    cmd = parts[0].lower()
    args = parts[1:]

    try:
        if cmd == "help":
            page = 1
            per_page = 12

            if args:
                try:
                    page = max(1, int(args[0]))
                except Exception:
                    return jsonify({
                        "output": "Uso: help [pagina]\nEjemplo: help 2",
                        "prompt": get_prompt()
                    })

            lines = []

            lines.append("Comandos internos:")
            for name, desc in BUILTIN_HELP.items():
                lines.append(f"  {name:<12} {desc}")

            external = get_external_help()

            if external:
                lines.append("")
                lines.append("Comandos externos instalados:")

                for name, data in sorted(external.items()):
                    desc = data["description"]
                    version = data["version"]
                    category = data["category"]
                    legacy = data["legacy"]

                    if legacy:
                        lines.append(f"  {name:<12} [legacy] v{version} - {desc}")
                    else:
                        lines.append(f"  {name:<12} [{category}] v{version} - {desc}")

            lines.append("")
            lines.append("Sudo:")
            lines.append("  sudo 1234")
            lines.append("  sudo logout")
            lines.append("  sudo status")
            lines.append("  sudo install <comando>")
            lines.append("  sudo install all")
            lines.append("  sudo update <comando>")
            lines.append("  sudo update all")
            lines.append("  sudo remove <comando>")
            lines.append("  sudo list")
            lines.append("  sudo search <texto>")
            lines.append("  sudo info <comando>")

            total = len(lines)
            pages = max(1, (total + per_page - 1) // per_page)

            if page > pages:
                page = pages

            start = (page - 1) * per_page
            end = start + per_page

            page_lines = lines[start:end]
            footer = f"\nPágina {page}/{pages} | Usa: help <pagina>"

            return jsonify({
                "output": "\n".join(page_lines) + footer,
                "prompt": get_prompt()
            })

        if cmd == "cls":
            return jsonify({"output": "__CLS__", "prompt": get_prompt()})

        if cmd == "pwd":
            return jsonify({"output": get_prompt().replace("/", "\\"), "prompt": get_prompt()})

        if cmd == "history":
            lines = [
                f"{i + 1}: {x}"
                for i, x in enumerate(session.get("history", []))
            ]

            return jsonify({"output": "\n".join(lines), "prompt": get_prompt()})

        if cmd == "cd":
            if len(args) != 1:
                return jsonify({"output": "Uso: cd <carpeta>", "prompt": get_prompt()})

            target = args[0]

            if target in ["\\", "/", "C:\\system", "c:\\system"]:
                session["cwd"] = ""
                return jsonify({"output": "", "prompt": get_prompt()})

            if target == "..":
                parent = os.path.dirname(session["cwd"]).replace("\\", "/")
                session["cwd"] = "" if parent == "." else parent
                return jsonify({"output": "", "prompt": get_prompt()})

            if not valid_name(target):
                return jsonify({"output": "Nombre de carpeta no permitido.", "prompt": get_prompt()})

            new_path = safe_path_from_cwd(target)

            if not new_path.is_dir():
                return jsonify({"output": "La carpeta no existe.", "prompt": get_prompt()})

            relative = os.path.relpath(new_path, ROOT)
            session["cwd"] = "" if relative == "." else relative.replace("\\", "/")

            return jsonify({"output": "", "prompt": get_prompt()})

        if cmd == "sudo":
            if len(args) == 1 and args[0] == SUDO_PASSWORD:
                session["sudo"] = True
                return jsonify({"output": "Sudo activado.", "prompt": get_prompt()})

            if not args:
                return jsonify({"output": "Uso: sudo 1234 | sudo install <comando>", "prompt": get_prompt()})

            if args[0] == "logout":
                session["sudo"] = False
                return jsonify({"output": "Sudo desactivado.", "prompt": get_prompt()})

            if args[0] == "status":
                return jsonify({
                    "output": "Sudo activo." if session.get("sudo") else "Sudo inactivo.",
                    "prompt": get_prompt()
                })

            if not session.get("sudo"):
                return jsonify({"output": "Primero activa sudo: sudo 1234", "prompt": get_prompt()})

            action = args[0]

            if action == "install":
                if len(args) != 2:
                    return jsonify({"output": "Uso: sudo install <comando|all>", "prompt": get_prompt()})

                target = args[1].lower()

                if target == "all":
                    repo_commands = get_repo_index()

                    if not repo_commands:
                        return jsonify({"output": "No se encontró index.json o está vacío.", "prompt": get_prompt()})

                    results = []

                    for item in repo_commands:
                        _, msg = install_command(item["name"])
                        results.append(msg)

                    return jsonify({"output": "\n".join(results), "prompt": get_prompt()})

                _, msg = install_command(target)
                return jsonify({"output": msg, "prompt": get_prompt()})

            if action == "update":
                if len(args) != 2:
                    return jsonify({"output": "Uso: sudo update <comando|all>", "prompt": get_prompt()})

                target = args[1].lower()

                if target == "all":
                    db = load_db()
                    installed = list(db.get("installed", {}).keys())

                    if not installed:
                        return jsonify({"output": "No hay comandos instalados.", "prompt": get_prompt()})

                    results = []

                    for name in installed:
                        _, msg = install_command(name, update=True)
                        results.append(msg)

                    return jsonify({"output": "\n".join(results), "prompt": get_prompt()})

                _, msg = install_command(target, update=True)
                return jsonify({"output": msg, "prompt": get_prompt()})

            if action == "remove":
                if len(args) != 2:
                    return jsonify({"output": "Uso: sudo remove <comando>", "prompt": get_prompt()})

                _, msg = remove_command(args[1])
                return jsonify({"output": msg, "prompt": get_prompt()})

            if action == "list":
                repo_commands = get_repo_index()

                if not repo_commands:
                    return jsonify({"output": "No hay comandos en index.json.", "prompt": get_prompt()})

                installed = load_db().get("installed", {})

                lines = ["Comandos disponibles en GitHub:"]

                for item in repo_commands:
                    name = item["name"]
                    desc = item.get("description", "")
                    category = item.get("category", "legacy")
                    mark = "[instalado]" if name in installed else "[repo]"
                    lines.append(f"  {mark:<12} {name:<12} [{category}] {desc}")

                return jsonify({"output": "\n".join(lines), "prompt": get_prompt()})

            if action == "search":
                if len(args) < 2:
                    return jsonify({"output": "Uso: sudo search <texto>", "prompt": get_prompt()})

                query = " ".join(args[1:]).lower()
                repo_commands = get_repo_index()

                found = []

                for item in repo_commands:
                    name = item.get("name", "")
                    desc = item.get("description", "")
                    category = item.get("category", "")

                    if query in name.lower() or query in desc.lower() or query in category.lower():
                        found.append(f"  {name:<12} [{category}] {desc}")

                return jsonify({
                    "output": "Resultados:\n" + "\n".join(found) if found else "Sin resultados.",
                    "prompt": get_prompt()
                })

            if action == "info":
                if len(args) != 2:
                    return jsonify({"output": "Uso: sudo info <comando>", "prompt": get_prompt()})

                name = args[1].lower()

                if not valid_name(name):
                    return jsonify({"output": "Nombre no permitido.", "prompt": get_prompt()})

                manifest = get_manifest(name)
                installed = load_db().get("installed", {})

                lines = [f"Comando: {name}"]

                if manifest:
                    lines.append(f"Descripción: {manifest.get('description', '')}")
                    lines.append(f"Versión: {manifest.get('version', 'N/A')}")
                    lines.append(f"Autor: {manifest.get('author', 'N/A')}")
                    lines.append(f"Entry: {manifest.get('entry', 'main.py')}")
                    lines.append(f"Categoría: {manifest.get('category', 'normal')}")
                else:
                    lines.append("Manifest remoto: no disponible")
                    lines.append("Si existe main.py, se instalará como legacy.")
                    lines.append("Versión: fecha de update")
                    lines.append("Categoría: legacy")

                if name in installed:
                    local = installed[name]
                    lines.append("Estado: instalado")
                    lines.append(f"Local versión: {local.get('version', '')}")
                    lines.append(f"Local categoría: {local.get('category', '')}")
                    lines.append(f"Fecha update: {local.get('updated_date', '')}")
                    lines.append(f"SHA256: {local.get('sha256', '')}")
                else:
                    lines.append("Estado: no instalado")

                return jsonify({"output": "\n".join(lines), "prompt": get_prompt()})

            return jsonify({"output": "Acción sudo no reconocida.", "prompt": get_prompt()})

        output = run_external_command(cmd, args)

        if output is not None:
            return jsonify({"output": output, "prompt": get_prompt()})

        return jsonify({"output": f"Comando no encontrado: {cmd}", "prompt": get_prompt()})

    except Exception as e:
        return jsonify({"output": f"Error: {e}", "prompt": get_prompt()})


def open_browser():
    webbrowser.open("http://127.0.0.1:5000/")


if __name__ == "__main__":
    threading.Timer(1.5, open_browser).start()

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
        use_reloader=False,
        threaded=False
    )