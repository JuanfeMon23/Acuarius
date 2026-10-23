import { mockNuxtImport } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { LeoApiError } from '#leo-client/lib/errors'
import { DEFAULT_PASSWORD_POLICY, clearPasswordPolicyCache, usePasswordPolicy } from './usePasswordPolicy'

const { get } = vi.hoisted(() => ({ get: vi.fn() }))
mockNuxtImport('useLeoAppApi', () => () => ({ get }))

const SERVER = {
  min_length: 14, max_length: 64, require_lowercase: true, require_uppercase: true, require_digit: false, require_symbol: false
}

beforeEach(() => {
  get.mockReset()
  clearPasswordPolicyCache()
  vi.useRealTimers()
})

describe('usePasswordPolicy', () => {
  it('arranca estricta (12/128, 4 clases) y adopta la del servidor al llegar', async () => {
    get.mockResolvedValue(SERVER)
    const { policy } = usePasswordPolicy()
    expect(policy.value).toEqual(DEFAULT_PASSWORD_POLICY)
    expect(DEFAULT_PASSWORD_POLICY).toEqual({
      min_length: 12, max_length: 128, require_lowercase: true, require_uppercase: true, require_digit: true, require_symbol: true
    })
    await flushPromises()
    expect(policy.value).toEqual(SERVER)
    expect(get).toHaveBeenCalledWith('/account/password-policy')
  })

  it('si la carga falla o es un 429 se queda con la estricta y no lanza', async () => {
    get.mockRejectedValueOnce(new Error('red'))
    const a = usePasswordPolicy()
    await flushPromises()
    expect(a.policy.value).toEqual(DEFAULT_PASSWORD_POLICY)

    get.mockRejectedValueOnce(new LeoApiError(429, 'rate_limited', 'x', null, 30))
    const b = usePasswordPolicy()
    await flushPromises()
    expect(b.policy.value).toEqual(DEFAULT_PASSWORD_POLICY)
  })

  it('una respuesta con otra forma se ignora', async () => {
    get.mockResolvedValue({ items: [] })
    const { policy } = usePasswordPolicy()
    await flushPromises()
    expect(policy.value).toEqual(DEFAULT_PASSWORD_POLICY)
  })

  it('cachea ~30 s y vuelve a pedirla después; los fallos no se cachean', async () => {
    vi.useFakeTimers()
    get.mockResolvedValue(SERVER)
    usePasswordPolicy()
    await vi.advanceTimersByTimeAsync(0)
    const second = usePasswordPolicy()
    expect(second.policy.value).toEqual(SERVER) // sin esperar: sale de la caché
    expect(get).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(31_000)
    usePasswordPolicy()
    await vi.advanceTimersByTimeAsync(0)
    expect(get).toHaveBeenCalledTimes(2)

    clearPasswordPolicyCache()
    get.mockRejectedValueOnce(new Error('red'))
    usePasswordPolicy()
    await vi.advanceTimersByTimeAsync(0)
    usePasswordPolicy()
    await vi.advanceTimersByTimeAsync(0)
    expect(get).toHaveBeenCalledTimes(4)
  })

  it('peticiones simultáneas comparten una sola llamada', async () => {
    get.mockResolvedValue(SERVER)
    usePasswordPolicy()
    usePasswordPolicy()
    await flushPromises()
    expect(get).toHaveBeenCalledTimes(1)
  })
})
