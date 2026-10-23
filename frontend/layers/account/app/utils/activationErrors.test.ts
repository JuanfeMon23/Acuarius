import { describe, expect, it } from 'vitest'
import { LeoApiError } from '#leo-client/lib/errors'
import { NEUTRAL_MESSAGE, classifyActivationError, waitText } from './activationErrors'

const FB = 'fallback'

describe('classifyActivationError', () => {
  it('400 -> mensaje neutro fijo (sin usar el del servidor)', () => {
    const r = classifyActivationError(new LeoApiError(400, 'activation_failed', 'otro texto'), FB)
    expect(r).toEqual({ kind: 'neutral', message: NEUTRAL_MESSAGE })
  })
  it('422 -> validación', () => {
    expect(classifyActivationError(new LeoApiError(422, 'validation_error', 'Revisa'), FB).kind).toBe('validation')
  })
  it('429 -> espera por Retry-After', () => {
    const r = classifyActivationError(new LeoApiError(429, 'rate_limited', 'x', null, 120), FB)
    expect(r).toMatchObject({ kind: 'rate', retryAfterSeconds: 120 })
    expect(r.message).toContain('2 minutos')
  })
  it('409 -> recuperación con referencia', () => {
    const r = classifyActivationError(new LeoApiError(409, 'activation_recovery', 'Código validado', { reference: 'abc123' }), FB)
    expect(r).toEqual({ kind: 'recovery', reference: 'abc123', message: 'Código validado' })
  })
  it('502 -> reintentar; red/desconocido -> fallback', () => {
    expect(classifyActivationError(new LeoApiError(502, 'upstream_unavailable', 'x'), FB).kind).toBe('retry')
    expect(classifyActivationError(new Error('Failed to fetch'), FB)).toEqual({ kind: 'other', message: FB })
  })
  it('waitText', () => {
    expect([waitText(null), waitText(30), waitText(60), waitText(61)]).toEqual(['unos minutos', '30 segundos', '1 minuto', '2 minutos'])
  })
})
