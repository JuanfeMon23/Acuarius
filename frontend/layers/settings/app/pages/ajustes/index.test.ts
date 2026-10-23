import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { enableAutoUnmount, flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { signInWith } from '#leo-client/testing/session'
import { forbiddenMessage } from '#leo-client/lib/permissionNames'
import { TAGS } from '../../../../../app/utils/tags'
import SettingsIndexPage from './index.vue'

enableAutoUnmount(afterEach)

const { api } = vi.hoisted(() => ({ api: { get: vi.fn(), put: vi.fn() } }))
mockNuxtImport('useLeoAppApi', () => () => api)

const LIST = {
  groups: [{
    group: 'Resultados',
    settings: [{
      key: 'results.max_page_size', type: 'int', value: 50, default: 50, min: 1, max: 200, unit: null,
      description: 'Máximo de resultados por página', version: 3, requires_security_permission: false,
      updated_at: null, updated_by: null, updated_by_username: null
    }]
  }]
}

beforeEach(() => {
  api.get.mockReset().mockResolvedValue(LIST)
})

describe('/ajustes', () => {
  it('exige acuarius.settings.view', () => {
    expect(useRouter().resolve('/ajustes').meta.leo?.tag).toBe(TAGS.settings.view)
  })

  it('registra nombres legibles de los 3 permisos', () => {
    for (const tag of Object.values(TAGS.settings)) {
      expect(forbiddenMessage({ action: tag }, 'x')).toMatch(/^No tienes permiso para: .*ajustes/i)
    }
  })

  it('carga con GET /settings y lista los ajustes por grupo', async () => {
    signInWith([TAGS.settings.view])
    const wrapper = await mountSuspended(SettingsIndexPage)
    await flushPromises()
    expect(api.get).toHaveBeenCalledWith('/settings')
    expect(wrapper.text()).toContain('Ajustes del sistema')
    expect(wrapper.text()).toContain('Máximo de resultados por página')
  })

  it('sin acuarius.settings.edit el valor no es editable', async () => {
    signInWith([TAGS.settings.view])
    const wrapper = await mountSuspended(SettingsIndexPage)
    await flushPromises()
    expect(wrapper.find('input').attributes('disabled')).toBeDefined()
  })

  it('con acuarius.settings.edit el valor es editable', async () => {
    signInWith([TAGS.settings.view, TAGS.settings.edit])
    const wrapper = await mountSuspended(SettingsIndexPage)
    await flushPromises()
    expect(wrapper.find('input').attributes('disabled')).toBeUndefined()
  })
})
