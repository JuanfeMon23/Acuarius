import { describe, expect, it } from 'vitest'
import { LeoApiError } from '#leo-client/lib/errors'
import type { PasswordPolicy } from '#andromeda/utils/passwordPolicy'
import { passwordPolicyMessage } from './passwordPolicyErrors'

const POLICY: PasswordPolicy = {
  min_length: 20, max_length: 64, require_lowercase: true, require_uppercase: true, require_digit: true, require_symbol: true
}
const err = (details: unknown, status = 422) => new LeoApiError(status, 'validation_error', 'Revisa los datos enviados.', details)

describe('passwordPolicyMessage', () => {
  it('traduce cada code con las cifras de la política', () => {
    const codes = ['too_short', 'too_long', 'no_lowercase', 'no_uppercase', 'no_digit', 'no_symbol']
    const msg = passwordPolicyMessage(err(codes.map(code => ({ field: 'password', message: 'x', code }))), 'password', POLICY)
    expect(msg).toBe(
      'La contraseña debe tener al menos 20 caracteres, tener como máximo 64 caracteres, incluir una letra minúscula, '
      + 'incluir una letra mayúscula, incluir un número, incluir un símbolo.'
    )
  })
  it('solo considera el campo pedido', () => {
    const e = err([{ field: 'new_password', message: 'x', code: 'no_digit' }])
    expect(passwordPolicyMessage(e, 'password', POLICY)).toBeNull()
    expect(passwordPolicyMessage(e, 'new_password', POLICY)).toBe('La contraseña debe incluir un número.')
  })
  it('otros errores o codes desconocidos devuelven null', () => {
    expect(passwordPolicyMessage(err([{ field: 'password', message: 'x', code: 'raro' }]), 'password', POLICY)).toBeNull()
    expect(passwordPolicyMessage(err(null), 'password', POLICY)).toBeNull()
    expect(passwordPolicyMessage(err([{ field: 'password', code: 'no_digit' }], 400), 'password', POLICY)).toBeNull()
    expect(passwordPolicyMessage(new Error('x'), 'password', POLICY)).toBeNull()
  })
})
