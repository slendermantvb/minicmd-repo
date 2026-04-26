import os
import sys
import json

DESCRIPTION = "Renombra archivo o carpeta. Uso: rename <old> <new>"

if "--help-json" in sys.argv:
    print(json.dumps({
        "description": DESCRIPTION
    }))
    sys.exit()

if os.environ.get("MINICMD_SUDO") != "1":
    print("Necesitas sudo para renombrar.")
    sys.exit()

if len(sys.argv) != 3:
    print("Uso: rename <old> <new>")
    sys.exit()

old = sys.argv[1]
new = sys.argv[2]

if "/" in old or "\\" in old or ".." in old:
    print("Nombre original no permitido.")
    sys.exit()

if "/" in new or "\\" in new or ".." in new:
    print("Nombre nuevo no permitido.")
    sys.exit()

try:
    os.rename(old, new)
    print(f"Renombrado: {old} -> {new}")
except Exception as e:
    print("Error:", e)