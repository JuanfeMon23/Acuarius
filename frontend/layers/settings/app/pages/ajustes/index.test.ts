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
    }, {
      key: 'results.show_footer', type: 'bool', value: true, default: true, min: null, max: null, unit: null,
      description: 'Mostrar pie en resultados', version: 1, requires_security_permission: false,
      updated_at: null, updated_by: null, updated_by_username: null
    }, {
      key: 'auth.max_attempts', type: 'int', value: 5, default: 5, min: 1, max: 10, unit: null,
      description: 'Intentos de inicio de sesión', version: 1, requires_security_permission: true,
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

  it('sin acuarius.settings.edit no hay controles en el DOM y el valor se ve como texto', async () => {
    signInWith([TAGS.settings.view])
    const wrapper = await mountSuspended(SettingsIndexPage)
    await flushPromises()
    const rows = wrapper.findAll('[data-testid="setting-row"]')
    expect(rows).toHaveLength(3)
    for (const row of rows) {
      expect(row.find('input').exists()).toBe(false)
      expect(row.find('[role=switch]').exists()).toBe(false)
      expect(row.find('[data-testid="setting-save"]').exists()).toBe(false)
      expect(row.find('[data-testid="setting-reset"]').exists()).toBe(false)
      expect(row.text()).not.toMatch(/Guardar|Restablecer/)
    }
    expect(wrapper.find('[data-testid="setting-row"][data-key="results.max_page_size"] [data-testid="setting-readonly"]').text()).toContain('50')
    expect(wrapper.find('[data-testid="setting-row"][data-key="results.show_footer"] [data-testid="setting-readonly"]').text()).toContain('Activado')
  })

  it('con acuarius.settings.edit el valor es editable', async () => {
    signInWith([TAGS.settings.view, TAGS.settings.edit])
    const wrapper = await mountSuspended(SettingsIndexPage)
    await flushPromises()
    const row = (key: string) => wrapper.find(`[data-testid="setting-row"][data-key="${key}"]`)
    expect(row('results.max_page_size').find('input').exists()).toBe(true)
    expect(row('results.max_page_size').find('input').attributes('disabled')).toBeUndefined()
    expect(row('results.show_footer').find('[role=switch]').exists()).toBe(true)
    expect(row('results.max_page_size').find('[data-testid="setting-save"]').exists()).toBe(true)
  })

  it('con view+edit pero sin edit-security los ajustes de seguridad son solo texto', async () => {
    signInWith([TAGS.settings.view, TAGS.settings.edit])
    const wrapper = await mountSuspended(SettingsIndexPage)
    await flushPromises()
    const secure = wrapper.find('[data-testid="setting-row"][data-key="auth.max_attempts"]')
    expect(secure.find('input').exists()).toBe(false)
    expect(secure.find('[role=switch]').exists()).toBe(false)
    expect(secure.find('[data-testid="setting-save"]').exists()).toBe(false)
    expect(secure.find('[data-testid="setting-reset"]').exists()).toBe(false)
    expect(secure.find('[data-testid="setting-readonly"]').text()).toContain('5')
  })

  it('con edit-security los ajustes de seguridad son editables', async () => {
    signInWith([TAGS.settings.view, TAGS.settings.edit, TAGS.settings.editSecurity])
    const wrapper = await mountSuspended(SettingsIndexPage)
    await flushPromises()
    expect(wrapper.find('[data-key="auth.max_attempts"] input').exists()).toBe(true)
  })
})
