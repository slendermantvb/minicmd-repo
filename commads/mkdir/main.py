import os
import sys
import json

DESCRIPTION = "Crea una carpeta. Uso: mkdir <nombre>"

if "--help-json" in sys.argv:
    print(json.dumps({
        "description": DESCRIPTION
    }))
    sys.exit()

if os.environ.get("MINICMD_SUDO") != "1":
    print("Necesitas sudo para crear carpetas.")
    sys.exit()

if len(sys.argv) != 2:
    print("Uso: mkdir <nombre>")
    sys.exit()

name = sys.argv[1]

if "/" in name or "\\" in name or ".." in name:
    print("Nombre no permitido.")
    sys.exit()

try:
    os.mkdir(name)
    print(f"Carpeta creada: {name}")
except Exception as e:
    print("Error:", e)