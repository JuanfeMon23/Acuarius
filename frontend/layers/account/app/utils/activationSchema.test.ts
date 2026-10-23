import { describe, expect, it } from 'vitest'
import { activationSchema, maskActivationCode, normalizeActivationCode, passwordChecks } from './activationSchema'

const valid = {
  code: 'ABCDE-FGHJK', document_type: 'CC', document_number: '123456789', birth_date: '1990-05-17',
  username: 'Ana.Perez', email: 'ana@correo.com', password: 'Clave-Segura-2026', password_confirm: 'Clave-Segura-2026'
}

describe('máscara del código', () => {
  it('formatea ABCDE-FGHJK, en mayúscula y sin caracteres inválidos', () => {
    expect(maskActivationCode('abcdefghjk')).toBe('ABCDE-FGHJK')
    expect(maskActivationCode('abc')).toBe('ABC')
    expect(maskActivationCode('ab cd-e fg')).toBe('ABCDE-FG')
    expect(maskActivationCode('0O1I ABCDE')).toBe('ABCDE')
    expect(maskActivationCode('ABCDEFGHJKLMN')).toBe('ABCDE-FGHJK')
  })
  it('normaliza quitando el guion', () => expect(normalizeActivationCode('abcde-fghjk')).toBe('ABCDEFGHJK'))
})

describe('requisitos de contraseña', () => {
  it('marca cada requisito', () => {
    const ok = (p: string) => Object.fromEntries(passwordChecks(p).map((c) => [c.id, c.ok]))
    expect(ok('abc')).toEqual({ length: false, lower: true, upper: false, digit: false, symbol: false })
    expect(Object.values(ok('Clave-Segura-2026')).every(Boolean)).toBe(true)
  })
})

describe('activationSchema', () => {
  it('acepta datos válidos y normaliza código y usuario', () => {
    const r = activationSchema.safeParse(valid)
    expect(r.success).toBe(true)
    if (r.success) {
      expect(r.data.code).toBe('ABCDEFGHJK')
      expect(r.data.username).toBe('ana.perez')
    }
  })
  const fails = (patch: object, path: string) => {
    const r = activationSchema.safeParse({ ...valid, ...patch })
    expect(r.success).toBe(false)
    if (!r.success) expect(r.error.issues.map((i) => i.path[0])).toContain(path)
  }
  it('rechaza código incompleto o con caracteres inexistentes', () => {
    fails({ code: 'ABCDE' }, 'code')
    fails({ code: 'ABCDE-FGH0K' }, 'code')
  })
  it('rechaza documento, fecha, usuario y correo inválidos', () => {
    fails({ document_type: '' }, 'document_type')
    fails({ document_number: '12.345' }, 'document_number')
    fails({ birth_date: '2999-01-01' }, 'birth_date')
    fails({ birth_date: '' }, 'birth_date')
    fails({ username: 'a' }, 'username')
    fails({ email: 'sin-arroba' }, 'email')
  })
  it('rechaza contraseña débil y confirmación distinta', () => {
    fails({ password: 'corta', password_confirm: 'corta' }, 'password')
    fails({ password_confirm: 'Otra-Clave-2026!' }, 'password_confirm')
  })
})
