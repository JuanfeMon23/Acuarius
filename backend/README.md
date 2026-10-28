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

Antes de usar la pantalla Ajustes, publicar los permisos nuevos en Leo (`acuarius.settings.view`, `acuarius.settings.edit`, `acuarius.settings.edit-security`) y concederlos a un rol:

```
uv run python -m app.core.leo_sync
```

Tags de acciones: el catálogo (`app/core/permissions.py`) se exporta al contrato del frontend (`frontend/app/generated/permissions.json`). Al cambiar tags, regenerar y commitear el JSON:

```
uv run python -m app.core.permissions_export          # regenera el JSON
uv run python -m app.core.permissions_export --check  # sale con 1 si está desalineado
```

Los límites de intentos, la vigencia de invitaciones y la paginación se editan en la pantalla Ajustes (tabla `settings`, creada por la migración 0004); la API los siembra al arrancar.

API en http://localhost:8200 (documentación en `/docs`).

## Producción

Requisitos: un superusuario de PostgreSQL para crear los roles (`acuarius_migrator`, dueño del esquema y solo para Alembic; `acuarius_app`, solo DML, para la API). Los roles se crean sin contraseña.

```
psql -d acuarius -v ON_ERROR_STOP=1 -f deploy/db_roles.sql   # crea los roles
psql -d acuarius -c "\password acuarius_migrator"            # fija las contraseñas
psql -d acuarius -c "\password acuarius_app"
# .env: MIGRATION_DATABASE_URL con acuarius_migrator, DATABASE_URL con acuarius_app
uv run alembic upgrade head                                  # corre como acuarius_migrator
psql -d acuarius -v ON_ERROR_STOP=1 -f deploy/db_roles.sql   # re-aplicar tras cada migración que agregue tablas
```

## Pruebas

```
uv run pytest
```
