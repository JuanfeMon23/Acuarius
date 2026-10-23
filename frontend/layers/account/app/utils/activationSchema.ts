import { z } from 'zod'
import type { PasswordPolicy } from '#andromeda/utils/passwordPolicy'
import { zLazyPassword } from './lazyPassword'

/** Alfabeto de los códigos del laboratorio (sin 0, O, 1, I). */
const CODE_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
const CODE_LENGTH = 10

/** "abcdefghjk" -> "ABCDE-FGHJK": solo caracteres válidos, en mayúscula, con guion tras 5. */
export function maskActivationCode(raw: string): string {
  const clean = [...raw.toUpperCase()].filter((c) => CODE_ALPHABET.includes(c)).slice(0, CODE_LENGTH).join('')
  return clean.length > 5 ? `${clean.slice(0, 5)}-${clean.slice(5)}` : clean
}

/** Código sin guion ni espacios, como se envía. */
export const normalizeActivationCode = (value: string) => value.replace(/[^A-Za-z0-9]/g, '').toUpperCase()

export const DOCUMENT_TYPES = [
  { value: 'CC', label: 'Cédula de ciudadanía' },
  { value: 'TI', label: 'Tarjeta de identidad' },
  { value: 'CE', label: 'Cédula de extranjería' },
  { value: 'PA', label: 'Pasaporte' },
  { value: 'RC', label: 'Registro civil' },
  { value: 'PEP', label: 'Permiso especial de permanencia' },
  { value: 'PPT', label: 'Permiso por protección temporal' }
] as const

export const USERNAME_RE = /^[a-z0-9]([a-z0-9._-]{1,62})[a-z0-9]$/
export const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/

const required = (msg: string) => z.string({ required_error: msg }).trim().min(1, msg)

/**
 * Formulario de alta. La política de contraseña es la del servidor
 * (`usePasswordPolicy`) y se lee en cada validación; el backend sigue siendo la autoridad.
 */
export const activationSchema = (policy: () => PasswordPolicy) => z.object({
  code: z.string({ required_error: 'Escribe el código de tu comprobante.' }).transform(normalizeActivationCode).pipe(
    z.string().length(CODE_LENGTH, 'Escribe el código completo (10 caracteres, como en tu comprobante).')
      .refine((v) => [...v].every((c) => CODE_ALPHABET.includes(c)), 'El código tiene caracteres que no existen en los códigos del laboratorio.')
  ),
  document_type: z.enum(DOCUMENT_TYPES.map((d) => d.value) as [string, ...string[]], { errorMap: () => ({ message: 'Elige el tipo de documento.' }) }),
  document_number: required('Escribe tu número de documento.').regex(/^[A-Za-z0-9]{3,20}$/, 'Usa solo letras y números, sin puntos ni espacios.'),
  birth_date: required('Indica tu fecha de nacimiento.').refine((v) => {
    const d = new Date(`${v}T00:00:00`)
    return !Number.isNaN(d.getTime()) && d.getFullYear() >= 1900 && d.getTime() <= Date.now()
  }, 'La fecha de nacimiento no es válida.'),
  username: z.string({ required_error: 'Elige un usuario.' }).trim().toLowerCase().refine((v) => USERNAME_RE.test(v),
    'Usa de 3 a 64 caracteres: minúsculas, números, punto, guion o guion bajo.'),
  email: required('Escribe tu correo.').regex(EMAIL_RE, 'Escribe un correo válido, por ejemplo nombre@correo.com.'),
  password: zLazyPassword(policy),
  password_confirm: z.string({ required_error: 'Repite la contraseña.' }).min(1, 'Repite la contraseña.')
}).refine((v) => v.password === v.password_confirm, { path: ['password_confirm'], message: 'Las contraseñas no coinciden.' })

export type ActivationInput = z.input<ReturnType<typeof activationSchema>>

/** Campos de cada paso del formulario. */
export const ACTIVATION_STEPS = [
  { title: 'Tu código', fields: ['code'] },
  { title: 'Tus datos', fields: ['document_type', 'document_number', 'birth_date'] },
  { title: 'Tu cuenta', fields: ['username', 'email', 'password', 'password_confirm'] }
] as const
