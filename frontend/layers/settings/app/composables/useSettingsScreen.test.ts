import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { LeoApiError } from '#leo-client/lib/errors'
import { signInWith } from '#leo-client/testing/session'
import { TAGS } from '../../../../app/utils/tags'
import { useSettingsScreen } from './useSettingsScreen'

const { api } = vi.hoisted(() => ({ api: { get: vi.fn(), put: vi.fn() } }))
mockNuxtImport('useLeoAppApi', () => () => api)

const ALL = [TAGS.settings.view, TAGS.settings.edit, TAGS.settings.editSecurity]

function setting(over: Record<string, unknown> = {}) {
  return {
    key: 'results.max_page_size', type: 'int', value: 50, default: 50, min: 1, max: 200, unit: null,
    description: 'Máximo de resultados por página', version: 3, requires_security_permission: false,
    updated_at: null, updated_by: null, updated_by_username: null, ...over
  }
}
const LIST = { groups: [{ group: 'Resultados', settings: [setting()] }] }

async function screen(perms: string[]) {
  signInWith(perms)
  let admin!: ReturnType<typeof useSettingsScreen>
  await mountSuspended({ setup() { admin = useSettingsScreen(); return () => null } })
  await flushPromises()
  return admin
}

beforeEach(() => {
  api.get.mockReset().mockResolvedValue(LIST)
  api.put.mockReset()
})

describe('useSettingsScreen (permisos y API)', () => {
  const secure = setting({ key: 'account.lockout', requires_security_permission: true })

  it('view: nada es editable', async () => {
    const admin = await screen([TAGS.settings.view])
    expect(admin.canEditSetting(setting() as never)).toBe(false)
  })

  it('edit: edita lo común pero no lo de seguridad', async () => {
    const admin = await screen([TAGS.settings.view, TAGS.settings.edit])
    expect(admin.canEditSetting(setting() as never)).toBe(true)
    expect(admin.canEditSetting(secure as never)).toBe(false)
  })

  it('edit-security: también lo de seguridad', async () => {
    const admin = await screen(ALL)
    expect(admin.canEditSetting(secure as never)).toBe(true)
  })

  it('guardar hace PUT /settings/{key} con valor, motivo y versión esperada', async () => {
    const admin = await screen(ALL)
    await admin.load()
    expect(api.get).toHaveBeenCalledWith('/settings')
    const item = admin.groups[0]!.settings[0]!
    admin.setDraft(item, '40')
    expect(admin.askSave(item)).toBe(true)
    admin.reason = 'Reducir la carga'
    api.put.mockResolvedValue({ ...item, value: 40, version: 4 })
    await admin.confirmSave()
    expect(api.put).toHaveBeenCalledWith('/settings/results.max_page_size', { value: 40, reason: 'Reducir la carga', expected_version: 3 })
    expect(admin.groups[0]!.settings[0]!.value).toBe(40)
  })

  it('el historial pide GET /settings/{key}/history?page', async () => {
    const admin = await screen(ALL)
    await admin.load()
    api.get.mockResolvedValue({ items: [], page: 2, page_size: 20, total: 0 })
    await admin.openHistory(admin.groups[0]!.settings[0]!)
    await admin.setHistoryPage(2)
    expect(api.get).toHaveBeenLastCalledWith('/settings/results.max_page_size/history', { query: { page: 2 } })
  })

  it('un error al cargar sale como mensaje legible, no el crudo', async () => {
    const admin = await screen([TAGS.settings.view])
    api.get.mockRejectedValue(new LeoApiError(500, 'internal_error', 'Traceback (most recent call last)'))
    await admin.load()
    expect(admin.loadError).toBeTruthy()
    expect(admin.loadError).not.toContain('Traceback')
  })
})
