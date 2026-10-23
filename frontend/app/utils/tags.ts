/** Tags de acción de Acuarius en Leo (`acuarius.<modulo>.<accion>`). El backend decide de verdad. */
export const TAGS = {
  results: { view: 'acuarius.results.view', download: 'acuarius.results.download' },
  family: {
    view: 'acuarius.family.view',
    invite: 'acuarius.family.invite',
    respond: 'acuarius.family.respond',
    manage: 'acuarius.family.manage'
  }
} as const

/** Nombres legibles para el mensaje "No tienes permiso para: …". */
export const PERMISSION_NAMES: Record<string, string> = {
  [TAGS.results.view]: 'Consultar resultados',
  [TAGS.results.download]: 'Descargar resultados',
  [TAGS.family.view]: 'Consultar el grupo familiar',
  [TAGS.family.invite]: 'Invitar al grupo familiar',
  [TAGS.family.respond]: 'Responder invitaciones familiares',
  [TAGS.family.manage]: 'Gestionar el grupo familiar'
}
