import { TAGS } from './tags'

export type CanFn = (tag: string) => boolean

export interface ScreenItem {
  label: string
  to: string
  /** `null`: visible para cualquier persona con sesión (sin permiso de Leo). */
  tag: string | null
  /** Clave del icono (ver `app/layouts/default.vue`). */
  icon: 'results' | 'family' | 'profile' | 'settings'
}

export const SCREENS: ScreenItem[] = [
  { label: 'Mis resultados', to: '/resultados', tag: TAGS.results.view, icon: 'results' },
  { label: 'Mi familia', to: '/familia', tag: TAGS.family.view, icon: 'family' },
  { label: 'Mi perfil', to: '/perfil', tag: null, icon: 'profile' },
  { label: 'Ajustes', to: '/ajustes', tag: TAGS.settings.view, icon: 'settings' }
]

/** Pantallas del menú que el usuario puede abrir. */
export function visibleScreens(can: CanFn): ScreenItem[] {
  return SCREENS.filter((screen) => screen.tag === null || can(screen.tag))
}
