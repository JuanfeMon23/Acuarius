# Acuarius — backend

API del portal de pacientes (FastAPI).

## Requisitos

- Python 3.13 y [uv](https://docs.astral.sh/uv/)
- PostgreSQL 18 con una base de datos propia `acuarius`
- Un `.env` (copiar de `.env.example`) con la conexión a la BD, la URL de Leo y la credencial de servicio de Incubus

## Cómo correr

```
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --port 8200 --reload
```

API en http://localhost:8200 (documentación en `/docs`).

## Pruebas

```
uv run pytest
```
