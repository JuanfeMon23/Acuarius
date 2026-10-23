/** Texto de las páginas de error (sin mostrar nunca el mensaje técnico). */
export function errorView(status: number | undefined): { title: string, detail: string } {
  if (status === 404) {
    return { title: 'No encontramos esta página', detail: 'Puede que el enlace esté mal escrito o que la página ya no exista.' }
  }
  if (status === 403) {
    return { title: 'No tienes permiso para ver esta página', detail: 'Si crees que deberías tener acceso, comunícate con el laboratorio.' }
  }
  if (status === 503) {
    return { title: 'No pudimos conectar', detail: 'Verifica tu conexión e inténtalo de nuevo en unos minutos.' }
  }
  return { title: 'Algo salió mal', detail: 'Ocurrió un error inesperado. Inténtalo de nuevo en unos minutos.' }
}
