import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { enableAutoUnmount, flushPromises } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { signInWith } from '#leo-client/testing/session'
import { TAGS } from '../../../../app/utils/tags'
import FamiliaPage from './familia.vue'

enableAutoUnmount(afterEach)

const { family } = vi.hoisted(() => ({
  family: {
    overview: { value: null as unknown },
    loading: { value: false }, error: { value: null }, busy: { value: null },
    load: () => {}, accept: () => {}, reject: () => {}, cancel: () => {}, setShare: () => {}, invite: () => {}, leave: () => {}, removeMember: () => {}
  }
}))
mockNuxtImport('useFamily', () => () => family)

family.overview.value = {
  group: {
    members: [
      { patient_id: 'me', display_name: 'Ana', is_me: true, is_creator: true },
      { patient_id: 'p2', display_name: 'Luis', is_me: false, is_creator: false }
    ]
  },
  invitations_received: [{ id: 'r1', inviter_display_name: 'Marta', expires_at: '2099-01-01T00:00:00Z' }],
  invitations_sent: [{ id: 's1', invitee_display_name: 'Pedro', expires_at: '2099-01-01T00:00:00Z' }],
  shares_received: [], shares_given: []
}

const ACTION_TEXTS = ['Aceptar', 'Rechazar', 'Cancelar invitación', 'Salir del grupo', 'Enviar invitación']

describe('/familia: controles condicionados por permiso', () => {
  it('solo con family.view no se renderiza ningún control de acción (no oculto, ausente)', async () => {
    signInWith([TAGS.family.view])
    const wrapper = await mountSuspended(FamiliaPage)
    await flushPromises()
    expect(wrapper.text()).toContain('Luis')
    for (const text of ACTION_TEXTS) expect(wrapper.text()).not.toContain(text)
    expect(wrapper.find('input').exists()).toBe(false)
    expect(wrapper.find('form').exists()).toBe(false)
    expect(wrapper.find('button[aria-label^="Quitar"]').exists()).toBe(false)
  })

  it('con los permisos de acción aparecen los controles', async () => {
    signInWith([TAGS.family.view, TAGS.family.invite, TAGS.family.respond, TAGS.family.manage])
    const wrapper = await mountSuspended(FamiliaPage)
    await flushPromises()
    for (const text of ACTION_TEXTS) expect(wrapper.text()).toContain(text)
    expect(wrapper.find('input[type=checkbox]').exists()).toBe(true)
  })
})
