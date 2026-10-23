"""Nombre corto para mostrar: nombre de pila + iniciales de apellidos.

Se deriva SIEMPRE en el servidor desde lo que devuelve Incubus; nunca del body.
"""

from typing import Any

MAX_LEN = 80
FALLBACK = "Familiar"


def derive_display_name(data: dict[str, Any]) -> str:
    """'Ana Maria' + 'Perez Gomez' -> 'Ana P. G.' (nunca el apellido completo)."""

    def words(*keys: str) -> list[str]:
        out: list[str] = []
        for k in keys:
            v = data.get(k)
            if isinstance(v, str):
                out.extend(v.split())
        return out

    given = words("first_name")
    if not given:
        return FALLBACK
    initials = [
        f"{w[0].upper()}." for w in words("first_last_name", "second_last_name")
    ]
    return " ".join([given[0], *initials])[:MAX_LEN].strip() or FALLBACK
