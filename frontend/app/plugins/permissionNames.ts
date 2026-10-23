import { PERMISSION_NAMES } from '../utils/tags'

// Nombres legibles de los permisos para los mensajes de "sin permiso".
export default defineNuxtPlugin(() => {
  registerPermissionNames(PERMISSION_NAMES)
})
