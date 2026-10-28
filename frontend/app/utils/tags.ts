import permissions from '../generated/permissions.json'

/**
 * Tags de acción de Acuarius en Leo (`acuarius.<modulo>.<accion>`). El backend decide de verdad.
 * Accesos por ergonomía: `tags.test.ts` los contrasta con `generated/permissions.json` (contrato
 * generado por el backend con `uv run python -m app.core.permissions_export`).
 */
export const TAGS = {
  results: { view: 'acuarius.results.view', download: 'acuarius.results.download' },
  family: {
    view: 'acuarius.family.view',
    invite: 'acuarius.family.invite',
    respond: 'acuarius.family.respond',
    manage: 'acuarius.family.manage'
  },
  settings: {
    view: 'acuarius.settings.view',
    edit: 'acuarius.settings.edit',
    editSecurity: 'acuarius.settings.edit-security'
  }
} as const


/**
 * Tags asignables del contrato sin pantalla ni acción propia en este frontend. Cada uno con su
 * motivo; vacío mientras todos tengan uso. `tags.test.ts` obliga a decidir ante un tag nuevo.
 */
export const TAGS_WITHOUT_SCREEN: readonly string[] = []

const ACTIONS = permissions.modules.flatMap((m) => m.actions)

/** Tags que se asignan a roles (excluye los eventos de auditoría). */
export const ALL_TAGS: string[] = ACTIONS.filter((a) => a.assignable).map((a) => a.tag)

/** Nombres legibles para el mensaje "No tienes permiso para: …" (derivados del contrato). */
export const PERMISSION_NAMES: Record<string, string> = Object.fromEntries(
  ACTIONS.filter((a) => a.assignable).map((a) => [a.tag, a.name])
)
