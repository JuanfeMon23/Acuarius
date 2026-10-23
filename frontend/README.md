# Acuarius — frontend

Portal de pacientes (Nuxt 4, SPA).

## Requisitos

- Node.js 24 LTS y [pnpm](https://pnpm.io/) (`corepack enable`)
- Backend de Acuarius corriendo en http://localhost:8200
- Leo (SSO) y su frontend, con la app `acuarius` registrada y `http://localhost:3300/leo/callback` como redirect_uri
- Un `.env` (copiar de `.env.example`)

## Cómo correr

```
pnpm install
pnpm run dev
```

App en http://localhost:3300 (el alta pública está en `/activar`).

## Pruebas

```
pnpm test               # lógica pura
pnpm test:components    # componentes y configuración (con Nuxt)
pnpm typecheck
```
