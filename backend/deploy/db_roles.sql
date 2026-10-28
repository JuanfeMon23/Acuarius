-- Roles de BD de minimo privilegio para Acuarius (idempotente; ver README,
-- seccion "Produccion").
--
--   acuarius_migrator  duenio del esquema, tablas, funciones y triggers; hace el
--                      DDL. SOLO lo usa Alembic (MIGRATION_DATABASE_URL).
--   acuarius_app       lo que usa la API (DATABASE_URL): SELECT/INSERT/UPDATE
--                      sobre las tablas (ningun flujo borra filas fisicamente:
--                      las FK son RESTRICT y la trazabilidad se conserva, asi
--                      que NO tiene DELETE), USAGE/SELECT en las secuencias.
--                      Sin DDL, sin TRUNCATE, sin acceso a alembic_version;
--                      sobre settings_history (append-only por trigger) solo
--                      SELECT e INSERT. Sin superusuario.
--
-- Correr como superusuario (o un rol que pueda crear roles y cambiar duenios),
-- conectado a la BD de Acuarius:
--
--   psql -d acuarius -v ON_ERROR_STOP=1 -f deploy/db_roles.sql
--
-- NO define contrasenas (no hay secretos en el repo): los roles se crean
-- LOGIN sin contrasena y no pueden entrar hasta que el operador la fije, p. ej.
-- con `\password acuarius_app` en psql. Volver a correr despues de CADA
-- migracion que agregue tablas: no hay ALTER DEFAULT PRIVILEGES a proposito (una
-- tabla nueva falla cerrada hasta que se re-aplica el script).

-- 1) Roles (sin superusuario, sin crear BD/roles, sin saltarse RLS).
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'acuarius_migrator') THEN
        CREATE ROLE acuarius_migrator LOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'acuarius_app') THEN
        CREATE ROLE acuarius_app LOGIN;
    END IF;
END
$$;

ALTER ROLE acuarius_migrator NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
ALTER ROLE acuarius_app NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;

-- 2) Conexion a esta BD.
DO $$
BEGIN
    EXECUTE format(
        'GRANT CONNECT ON DATABASE %I TO acuarius_app, acuarius_migrator',
        current_database()
    );
END
$$;

-- 3) acuarius_migrator es duenio del esquema y de sus tablas y funciones
--    (los triggers pertenecen a su tabla).
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
ALTER SCHEMA public OWNER TO acuarius_migrator;

DO $$
DECLARE
    obj record;
BEGIN
    FOR obj IN
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'public' AND tableowner <> 'acuarius_migrator'
    LOOP
        -- Las secuencias de columnas serial/identity cambian de duenio con la tabla.
        EXECUTE format('ALTER TABLE public.%I OWNER TO acuarius_migrator', obj.tablename);
    END LOOP;
    FOR obj IN
        SELECT p.oid::regprocedure AS signature
        FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public' AND p.prokind = 'f'
          AND pg_get_userbyid(p.proowner) <> 'acuarius_migrator'
          AND NOT EXISTS (
              SELECT 1 FROM pg_depend d
              WHERE d.objid = p.oid AND d.deptype = 'e'
          )
    LOOP
        EXECUTE format('ALTER FUNCTION %s OWNER TO acuarius_migrator', obj.signature);
    END LOOP;
END
$$;

-- 4) acuarius_app: solo DML. Se parte de cero para quitar lo que sobrara.
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM acuarius_app;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM acuarius_app;
GRANT USAGE ON SCHEMA public TO acuarius_app;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO acuarius_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO acuarius_app;

-- Excepciones: historial de ajustes append-only (solo leer y agregar) y la
-- tabla de control de Alembic (la API no la necesita).
DO $$
BEGIN
    IF to_regclass('public.settings_history') IS NOT NULL THEN
        REVOKE ALL ON TABLE public.settings_history FROM acuarius_app;
        GRANT SELECT, INSERT ON TABLE public.settings_history TO acuarius_app;
    END IF;
    IF to_regclass('public.alembic_version') IS NOT NULL THEN
        REVOKE ALL ON TABLE public.alembic_version FROM acuarius_app;
    END IF;
END
$$;
