import { mountSuspended } from '@nuxt/test-utils/runtime'
import { describe, expect, it } from 'vitest'
import OrderPdfButton from './OrderPdfButton.vue'

describe('OrderPdfButton', () => {
  it('emite la orden al pulsar y tiene nombre accesible', async () => {
    const w = await mountSuspended(OrderPdfButton, { props: { orderNumber: 'A-1' } })
    const btn = w.get('button')
    expect(btn.attributes('aria-label')).toBe('Descargar PDF de la orden A-1')
    await btn.trigger('click')
    expect(w.emitted('download')![0]).toEqual(['A-1'])
  })

  it('en descarga muestra el estado y no emite de nuevo', async () => {
    const w = await mountSuspended(OrderPdfButton, { props: { orderNumber: 'A-1', loading: true } })
    expect(w.text()).toContain('Descargando')
    expect(w.get('button').attributes('aria-busy')).toBe('true')
    await w.get('button').trigger('click')
    expect(w.emitted('download')).toBeUndefined()
  })
})
