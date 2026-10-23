import { mockNuxtImport } from '@nuxt/test-utils/runtime'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { LeoApiError } from '#leo-client/lib/errors'
import { useResults } from './useResults'

const calls = vi.hoisted(() => [] as { method: string, path: string, options?: Record<string, unknown> }[])
const state = vi.hoisted(() => ({ handler: (_m: string, _p: string): unknown => ({}) }))
const download = vi.hoisted(() => vi.fn())

mockNuxtImport('useLeoAppApi', () => () => {
  const call = (method: string) => (path: string, a?: unknown, b?: unknown) => {
    const options = (method === 'GET' || method === 'DELETE' ? a : b) as Record<string, unknown> | undefined
    calls.push({ method, path, options })
    const out = state.handler(method, path)
    return out instanceof Error ? Promise.reject(out) : Promise.resolve(out)
  }
  return { get: call('GET'), post: call('POST'), put: call('PUT'), delete: call('DELETE') }
})
mockNuxtImport('useLeoSession', () => () => ({ can: () => true }))
mockNuxtImport('downloadBlob', () => download)

const page = { items: [{ order_number: 'A-1', date: '2026-10-01T10:00:00Z', finalized_at: null, status: 'finalizada', tests: ['Hemograma'], has_pdf: true }], page: 1, page_size: 10, total: 1 }

beforeEach(() => {
  calls.length = 0
  download.mockReset()
  state.handler = (_m, p) => (p === '/family/me' ? { shares_received: [{ patient_id: 'p2', display_name: 'Ana' }] } : page)
})

describe('useResults', () => {
  it('carga mi lista sin patient_id y el selector con familiares', async () => {
    const r = useResults()
    await r.init()
    const list = calls.find((c) => c.path === '/results')!
    expect(list.options?.query).toEqual({ page: 1, page_size: 10 })
    expect(r.options.value.map((o) => o.label)).toEqual(['Yo', 'Ana'])
    expect(r.data.value?.items).toHaveLength(1)
  })

  it('al elegir un familiar pide con patient_id y vuelve a la página 1', async () => {
    const r = useResults()
    await r.init()
    await r.goToPage(2)
    await r.selectPatient('p2')
    const last = calls.filter((c) => c.path === '/results').at(-1)!
    expect(last.options?.query).toEqual({ page: 1, page_size: 10, patient_id: 'p2' })
  })

  it('un error de carga queda como mensaje legible, no crudo', async () => {
    state.handler = (_m, p) => (p === '/family/me' ? { shares_received: [] } : new Error('[GET] "http://x": <no response> Failed to fetch'))
    const r = useResults()
    await r.init()
    expect(r.error.value).toContain('No se pudo conectar')
    expect(r.error.value).not.toContain('<no response>')
  })

  it('un 422 por page_size sale legible con el tope del servidor', async () => {
    state.handler = (_m, p) => (p === '/family/me' ? { shares_received: [] } : new LeoApiError(422, 'validation_error', 'Revisa los datos enviados.', { field: 'page_size', max: 25 }))
    const r = useResults()
    await r.init()
    expect(r.error.value).toContain('máximo permitido es 25')
  })

  it('descarga el PDF como blob con nombre seguro y sin abrirlo', async () => {
    const blob = new Blob(['%PDF'], { type: 'application/pdf' })
    state.handler = () => blob
    const r = useResults()
    expect(await r.downloadPdf('A-1')).toBe(true)
    expect(calls[0]!.path).toBe('/results/A-1/report.pdf')
    expect(calls[0]!.options?.responseType).toBe('blob')
    expect(download).toHaveBeenCalledWith(blob, 'resultados-A-1.pdf')
    expect(r.downloading.value).toBeNull()
  })

  it('si la descarga falla muestra un mensaje legible y no descarga', async () => {
    state.handler = () => new LeoApiError(404, 'not_found', 'Resultado no encontrado.')
    const r = useResults()
    expect(await r.downloadPdf('A-1')).toBe(false)
    expect(r.downloadError.value).toBe('Resultado no encontrado.')
    expect(download).not.toHaveBeenCalled()
  })
})
