import { TAGS } from './tags'

export type CanFn = (tag: string) => boolean

export interface ScreenItem {
  label: string
  to: string
  tag: string
  /** Clave del icono (ver `app/layouts/default.vue`). */
  icon: 'results' | 'family'
}

export const SCREENS: ScreenItem[] = [
  { label: 'Mis resultados', to: '/resultados', tag: TAGS.results.view, icon: 'results' },
  { label: 'Mi familia', to: '/familia', tag: TAGS.family.view, icon: 'family' }
]

/** Pantallas del menú que el usuario puede abrir. */
export function visibleScreens(can: CanFn): ScreenItem[] {
  return SCREENS.filter((screen) => can(screen.tag))
}
