import { describe, expect, it } from 'vitest'
import { passwordChangeSchema, profileChanges, profileFormSchema } from './profileSchema'

const base = { first_name: 'Ana', last_name: 'Pérez', email: 'ana@x.co' }
const issuesOf = (r: { success: boolean, error?: { issues: { path: (string | number)[], message: string }[] } }) =>
  r.success ? [] : r.error!.issues.map(i => `${i.path.join('.')}: ${i.message}`)

describe('profileFormSchema', () => {
  const schema = profileFormSchema(() => 'ana@x.co')

  it('sin cambiar el correo no pide contraseña actual', () => {
    expect(schema.safeParse({ ...base, current_password: '' }).success).toBe(true)
  })
  it('correo cambiado sin contraseña actual: error en current_password', () => {
    const r = schema.safeParse({ ...base, email: 'otra@x.co', current_password: '' })
    expect(issuesOf(r)).toEqual(['current_password: Ingresa tu contraseña actual para cambiar el correo.'])
  })
  it('correo cambiado con contraseña actual es válido', () => {
    expect(schema.safeParse({ ...base, email: 'otra@x.co', current_password: 'x' }).success).toBe(true)
  })
  it('compara contra el correo actual al validar (función)', () => {
    let current = 'ana@x.co'
    const s = profileFormSchema(() => current)
    current = 'otra@x.co'
    expect(s.safeParse({ ...base, email: 'otra@x.co', current_password: '' }).success).toBe(true)
  })
  it('nombres obligatorios y correo válido', () => {
    const issues = issuesOf(schema.safeParse({ first_name: ' ', last_name: '', email: 'mal', current_password: '' }))
    expect(issues).toHaveLength(3)
  })
})

describe('profileChanges', () => {
  it('solo devuelve lo que cambió, recortado', () => {
    expect(profileChanges(base, { ...base, first_name: ' Ana María ' })).toEqual({ first_name: 'Ana María' })
    expect(profileChanges(base, base)).toEqual({})
    expect(profileChanges(base, { ...base, email: 'n@x.co' })).toEqual({ email: 'n@x.co' })
  })
})

describe('passwordChangeSchema', () => {
  const ok = { current_password: 'Vieja#Clave1', new_password: 'Nueva#Clave12', confirm_password: 'Nueva#Clave12' }
  it('acepta una contraseña que cumple la política', () => {
    expect(passwordChangeSchema.safeParse(ok).success).toBe(true)
  })
  it('rechaza débil, igual a la actual y confirmación distinta', () => {
    expect(issuesOf(passwordChangeSchema.safeParse({ ...ok, new_password: 'corta', confirm_password: 'corta' }))[0]).toContain('new_password')
    expect(issuesOf(passwordChangeSchema.safeParse({ ...ok, new_password: ok.current_password, confirm_password: ok.current_password })))
      .toContain('new_password: La contraseña nueva debe ser distinta de la actual.')
    expect(issuesOf(passwordChangeSchema.safeParse({ ...ok, confirm_password: 'Otra#Clave123' })))
      .toEqual(['confirm_password: Las contraseñas no coinciden.'])
  })
  it('campos vacíos piden cada valor', () => {
    expect(issuesOf(passwordChangeSchema.safeParse({ current_password: '', new_password: '', confirm_password: '' }))).toHaveLength(3)
  })
})
