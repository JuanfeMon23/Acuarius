import { mockNuxtImport } from '@nuxt/test-utils/runtime'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { LeoApiError } from '#leo-client/lib/errors'
import { useAccountProfile } from './useAccountProfile'

const calls = vi.hoisted(() => [] as { method: string, path: string, body?: unknown }[])
const state = vi.hoisted(() => ({ fail: null as unknown, failGet: null as unknown, ensure: vi.fn() }))

mockNuxtImport('useLeoAppApi', () => () => {
  const call = (method: string) => (path: string, body?: unknown) => {
    calls.push({ method, path, body })
    if (state.failGet && method === 'GET') return Promise.reject(state.failGet)
    if (state.fail && method !== 'GET') return Promise.reject(state.fail)
    if (path === '/account/me') return Promise.resolve({ display_name: 'Ana P.' })
    return Promise.resolve({ first_name: 'Ana', last_name: 'Pérez', email: 'ana@x.co', username: 'ana' })
  }
  return { get: call('GET'), post: call('POST'), patch: call('PATCH'), put: call('PUT'), delete: call('DELETE') }
})
mockNuxtImport('useLeoSession', () => () => ({ ensure: state.ensure }))

beforeEach(() => {
  calls.length = 0
  state.fail = null
  state.failGet = null
  state.ensure.mockReset()
})

describe('useAccountProfile', () => {
  it('carga perfil y nombre a mostrar', async () => {
    const p = useAccountProfile()
    await p.load()
    expect(p.profile.value?.username).toBe('ana')
    expect(p.displayName.value).toBe('Ana P.')
    expect(p.loading.value).toBe(false)
  })

  it('guardar hace PATCH y refresca perfil, /account/me y la sesión', async () => {
    const p = useAccountProfile()
    await p.save({ first_name: 'Ana María' })
    expect(calls[0]).toEqual({ method: 'PATCH', path: '/account/profile', body: { first_name: 'Ana María' } })
    expect(calls.map(c => c.path)).toContain('/account/me')
    expect(state.ensure).toHaveBeenCalledWith(true)
  })

  it('si el PATCH falla lanza y no refresca', async () => {
    state.fail = new LeoApiError(403, 'invalid_current_password', 'x')
    const p = useAccountProfile()
    await expect(p.save({ email: 'n@x.co', current_password: 'mal' })).rejects.toBeInstanceOf(LeoApiError)
    expect(calls).toHaveLength(1)
  })

  it('cambiar contraseña hace POST con ambos campos', async () => {
    const p = useAccountProfile()
    await p.changePassword({ current_password: 'a', new_password: 'b' })
    expect(calls[0]).toEqual({ method: 'POST', path: '/account/password', body: { current_password: 'a', new_password: 'b' } })
  })

  it('un error de carga queda como mensaje legible', async () => {
    state.failGet = new Error('[GET] "http://x": <no response> Failed to fetch')
    const p = useAccountProfile()
    await p.load()
    expect(p.error.value).toContain('No se pudo conectar')
    expect(p.error.value).not.toContain('<no response>')
  })
})
