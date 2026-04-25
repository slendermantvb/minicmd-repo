import os
import sys
import json

DESCRIPTION = "Lista archivos y carpetas del directorio actual."

if "--help-json" in sys.argv:
    print(json.dumps({
        "description": DESCRIPTION
    }))
    sys.exit()

items = os.listdir()

if not items:
    print("(vacío)")
    sys.exit()

for item in items:
    if os.path.isdir(item):
        print(f"<DIR>  {item}")
    else:
        print(f"       {item}")