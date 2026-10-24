import { mountSuspended } from '@nuxt/test-utils/runtime'
import { enableAutoUnmount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'
// Página de error que Nuxt resuelve desde la capa Andromeda (la app no define app/error.vue).
import LayerError from '../../node_modules/andromeda/app/error.vue'

enableAutoUnmount(afterEach)

describe('error.vue de la capa Andromeda', () => {
  it('404: texto fijo y nunca el statusMessage crudo', async () => {
    const wrapper = await mountSuspended(LayerError, {
      props: { error: { statusCode: 404, statusMessage: 'Page not found: /x', message: 'raw internal' } }
    })
    expect(wrapper.text()).toContain('No encontramos esta página')
    expect(wrapper.text()).not.toContain('Page not found')
    expect(wrapper.text()).not.toContain('raw internal')
  })

  it('503: «Servicio no disponible» con reintentar y sin el statusMessage crudo', async () => {
    const wrapper = await mountSuspended(LayerError, {
      props: { error: { statusCode: 503, statusMessage: 'ECONNREFUSED 10.0.0.5' } }
    })
    expect(wrapper.text()).toContain('Servicio no disponible')
    expect(wrapper.text()).toContain('Reintentar')
    expect(wrapper.text()).not.toContain('ECONNREFUSED')
  })
})
