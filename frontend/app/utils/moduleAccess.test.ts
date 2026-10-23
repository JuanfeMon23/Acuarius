import { describe, expect, it } from 'vitest'
import { visibleScreens } from './moduleAccess'
import { TAGS } from './tags'

const canOnly = (...tags: string[]) => (tag: string) => tags.includes(tag)

describe('menú filtrado por permiso', () => {
  it('sin permisos no hay pantallas', () => {
    expect(visibleScreens(canOnly())).toEqual([])
  })
  it('solo resultados', () => {
    expect(visibleScreens(canOnly(TAGS.results.view)).map((s) => s.label)).toEqual(['Mis resultados'])
  })
  it('con ambos aparecen en orden', () => {
    expect(visibleScreens(canOnly(TAGS.results.view, TAGS.family.view)).map((s) => s.to)).toEqual(['/resultados', '/familia'])
  })
})
