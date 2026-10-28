"""Exporta el catalogo de tags a `frontend/app/generated/permissions.json`.

    cd backend
    uv run python -m app.core.permissions_export          # escribe el JSON
    uv run python -m app.core.permissions_export --check  # sale con 1 si difiere

Lee el catalogo en codigo (no toca la BD ni arranca servicios). El JSON es el
contrato de tags que el frontend deriva; se regenera y se commitea al cambiar tags.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from app.core.leo import APP_SLUG, catalog
from app.core import permissions  # noqa: F401  (registra el catalogo completo)

OUTPUT = (
    Path(__file__).resolve().parents[3] / "frontend" / "app" / "generated" / "permissions.json"
)
EVENT_PREFIX = "Evento:"


def build_contract() -> dict[str, Any]:
    modules = []
    for module in catalog.to_payload()["modules"]:
        actions = [
            {
                "tag": f"{APP_SLUG}.{module['slug']}.{a['verb']}",
                "verb": a["verb"],
                "name": a["name"],
                "description": a.get("description", ""),
                "assignable": not a["name"].startswith(EVENT_PREFIX),
            }
            for a in module["actions"]
        ]
        modules.append(
            {
                "slug": module["slug"],
                "name": module["name"],
                "description": module.get("description", ""),
                "actions": actions,
            }
        )
    return {"app": APP_SLUG, "modules": modules}


def render() -> str:
    return json.dumps(build_contract(), ensure_ascii=False, indent=2) + "\n"


def is_aligned() -> bool:
    return OUTPUT.is_file() and OUTPUT.read_bytes() == render().encode("utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if args.check:
        if is_aligned():
            return 0
        print("tags desalineados: ejecuta uv run python -m app.core.permissions_export")
        return 1
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(render().encode("utf-8"))
    print(f"escrito {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
