import { describe, expect, it } from 'vitest'
import { LeoApiError } from '#leo-client/lib/errors'
import { passwordFailure, profileUpdateFailure, rateLimitMessage } from './profileErrors'

const err = (status: number, code: string, details: unknown = null, retry: number | null = null) =>
  new LeoApiError(status, code, 'texto del servidor', details, retry)

describe('profileUpdateFailure', () => {
  it('contraseña requerida e incorrecta van al campo; la incorrecta se vacía', () => {
    expect(profileUpdateFailure(err(422, 'current_password_required')).fields.current_password).toContain('contraseña actual')
    const bad = profileUpdateFailure(err(403, 'invalid_current_password'))
    expect(bad.fields.current_password).toBe('La contraseña actual no es correcta.')
    expect(bad.clearCurrentPassword).toBe(true)
  })
  it('409 duplicado va al campo correo', () => {
    expect(profileUpdateFailure(err(409, 'duplicate', { field: 'email' })).fields.email).toContain('ya está en uso')
  })
  it('422 de validación reparte por campo', () => {
    const r = profileUpdateFailure(err(422, 'validation_error', [{ field: 'email', message: 'Correo inválido.' }]))
    expect(r.fields).toEqual({ email: 'Correo inválido.' })
  })
  it('429 trae la espera y marca rateLimited', () => {
    const r = profileUpdateFailure(err(429, 'rate_limited', { retry_after_seconds: 90 }, 90))
    expect(r).toMatchObject({ rateLimited: true, retryAfterSeconds: 90 })
    expect(r.form).toBe(rateLimitMessage(90))
    expect(r.form).toContain('2 minutos')
  })
  it('502 y errores de red son legibles, nunca crudos', () => {
    expect(profileUpdateFailure(err(502, 'upstream_unavailable')).form).toContain('laboratorio')
    const net = profileUpdateFailure(new Error('[PATCH] "http://x": <no response> Failed to fetch'))
    expect(net.form).toContain('No se pudo conectar')
  })
})

const STRICT = {
  min_length: 12, max_length: 128, require_lowercase: true, require_uppercase: true, require_digit: true, require_symbol: true
}

describe('passwordFailure', () => {
  it('credenciales inválidas → contraseña actual (vaciada)', () => {
    const r = passwordFailure(err(403, 'invalid_credentials'), STRICT)
    expect(r.fields.current_password).toBeDefined()
    expect(r.clearCurrentPassword).toBe(true)
  })
  it('422 con details[].code de la política se redacta con las cifras vigentes', () => {
    const r = passwordFailure(err(422, 'validation_error', [
      { field: 'new_password', message: 'x', code: 'too_short' },
      { field: 'new_password', message: 'x', code: 'no_symbol' }
    ]), STRICT)
    expect(r.fields.new_password).toBe('La contraseña debe tener al menos 12 caracteres, incluir un símbolo.')
  })
  it('weak_password lista los requisitos y same_password va a la nueva', () => {
    const weak = passwordFailure(err(422, 'weak_password', [{ field: 'new_password', message: 'Falta una mayúscula.' }]), STRICT)
    expect(weak.fields.new_password).toBe('La contraseña no cumple la política: Falta una mayúscula.')
    expect(passwordFailure(err(422, 'same_password'), STRICT).fields.new_password).toContain('distinta')
  })
  it('429 bloquea con espera', () => {
    expect(passwordFailure(err(429, 'rate_limited', null, 30), STRICT)).toMatchObject({ rateLimited: true, retryAfterSeconds: 30 })
  })
})
