import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative, sep } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import permissions from '../generated/permissions.json'
import { SCREENS } from './moduleAccess'
import { ALL_TAGS, PERMISSION_NAMES, TAGS, TAGS_WITHOUT_SCREEN } from './tags'

const ROOT = fileURLToPath(new URL('../..', import.meta.url))
const TAG_RE = /acuarius\.[a-z0-9-]+\.[a-z0-9-]+/g
/** Literales con forma de tag que no lo son (claves de almacenamiento, etc.). */
const NOT_TAGS = new Set(['acuarius.sidebar.collapsed'])

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const full = join(dir, name)
    if (statSync(full).isDirectory()) return name === 'generated' || name === 'node_modules' ? [] : sourceFiles(full)
    return /\.(ts|vue|js)$/.test(name) && !name.endsWith('.test.ts') ? [full] : []
  })
}

const contractTags = new Set(permissions.modules.flatMap((m) => m.actions.map((a) => a.tag)))

describe('alineación de tags frontend ↔ backend (generated/permissions.json)', () => {
  it('todo tag literal del código fuente existe en el contrato', () => {
    const unknown: string[] = []
    for (const file of [join(ROOT, 'app'), join(ROOT, 'layers')].flatMap(sourceFiles)) {
      for (const tag of readFileSync(file, 'utf-8').match(TAG_RE) ?? []) {
        if (!contractTags.has(tag) && !NOT_TAGS.has(tag)) unknown.push(`${tag} (${relative(ROOT, file).split(sep).join('/')})`)
      }
    }
    expect(unknown, 'tags que el backend no declara: corrige el literal o regenera el contrato').toEqual([])
  })

  it('todo tag asignable del contrato se usa en TAGS/SCREENS o está justificado en TAGS_WITHOUT_SCREEN', () => {
    const used = new Set<string>([
      ...Object.values(TAGS).flatMap((m) => Object.values(m)),
      ...SCREENS.flatMap((s) => (s.tag ? [s.tag] : [])),
      ...TAGS_WITHOUT_SCREEN
    ])
    expect(ALL_TAGS.filter((tag) => !used.has(tag)), 'tags nuevos del backend sin alinear en el frontend').toEqual([])
  })

  it('TAGS_WITHOUT_SCREEN solo contiene tags asignables del contrato que TAGS no usa', () => {
    const inTags = new Set(Object.values(TAGS).flatMap((m) => Object.values(m)))
    for (const tag of TAGS_WITHOUT_SCREEN) {
      expect(ALL_TAGS).toContain(tag)
      expect(inTags.has(tag)).toBe(false)
    }
  })

  it('los eventos de auditoría no son asignables ni tienen nombre de permiso', () => {
    const events = permissions.modules.flatMap((m) => m.actions).filter((a) => !a.assignable)
    expect(events.length).toBeGreaterThan(0)
    for (const e of events) {
      expect(ALL_TAGS).not.toContain(e.tag)
      expect(PERMISSION_NAMES[e.tag]).toBeUndefined()
    }
  })

  it('los nombres legibles y los conteos salen del contrato', () => {
    expect(ALL_TAGS).toHaveLength(9)
    expect(Object.keys(PERMISSION_NAMES)).toEqual(ALL_TAGS)
    expect(PERMISSION_NAMES[TAGS.results.view]).toBe('Consultar resultados')
  })
})
