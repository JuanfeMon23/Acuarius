import { describe, expect, it } from 'vitest'
import { visibleScreens } from './moduleAccess'
import { TAGS } from './tags'

const canOnly = (...tags: string[]) => (tag: string) => tags.includes(tag)

describe('menú filtrado por permiso', () => {
  it('sin permisos solo queda Mi perfil (sin tag)', () => {
    expect(visibleScreens(canOnly()).map((s) => s.label)).toEqual(['Mi perfil'])
  })
  it('solo resultados', () => {
    expect(visibleScreens(canOnly(TAGS.results.view)).map((s) => s.label)).toEqual(['Mis resultados', 'Mi perfil'])
  })
  it('Ajustes solo con acuarius.settings.view', () => {
    expect(visibleScreens(canOnly(TAGS.settings.view)).map((s) => s.to)).toEqual(['/perfil', '/ajustes'])
    expect(visibleScreens(canOnly(TAGS.settings.edit, TAGS.settings.editSecurity)).map((s) => s.to)).toEqual(['/perfil'])
  })
  it('con ambos aparecen en orden', () => {
    expect(visibleScreens(canOnly(TAGS.results.view, TAGS.family.view)).map((s) => s.to)).toEqual(['/resultados', '/familia', '/perfil'])
  })
})
