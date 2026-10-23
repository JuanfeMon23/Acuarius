import { z } from 'zod'
import { zRequiredText } from '#andromeda/utils/zodFields'
import { EMAIL_RE, passwordChecks } from './activationSchema'

/** Perfil propio (`GET /account/profile`). El documento no forma parte: no se edita. */
export interface AccountProfile {
  first_name: string
  last_name: string
  email: string
  username: string
}

/** Cuerpo de `PATCH /account/profile`: solo lo que cambió. */
export interface ProfileUpdatePayload {
  first_name?: string
  last_name?: string
  email?: string
  /** Solo si cambia el correo. Viaja únicamente en la petición. */
  current_password?: string
}

export type EditableProfile = Pick<AccountProfile, 'first_name' | 'last_name' | 'email'>

export const CURRENT_PASSWORD_REQUIRED = 'Ingresa tu contraseña actual para cambiar el correo.'

/**
 * Datos personales + «Contraseña actual», obligatoria solo si el correo cambió
 * respecto al actual (`currentEmail` se lee en cada validación). El backend
 * sigue siendo la autoridad.
 */
export function profileFormSchema(currentEmail: () => string) {
  return z.object({
    first_name: zRequiredText('Los nombres son obligatorios.', 100),
    last_name: zRequiredText('Los apellidos son obligatorios.', 100),
    email: z.string({ required_error: 'Escribe tu correo.' }).trim().min(1, 'Escribe tu correo.')
      .max(255, 'Máximo 255 caracteres.')
      .regex(EMAIL_RE, 'Escribe un correo válido, por ejemplo nombre@correo.com.'),
    current_password: z.string().optional()
  }).superRefine((v, ctx) => {
    if (EMAIL_RE.test(v.email) && v.email !== currentEmail().trim() && !v.current_password) {
      ctx.addIssue({ code: 'custom', path: ['current_password'], message: CURRENT_PASSWORD_REQUIRED })
    }
  })
}

/** Solo los campos que cambiaron (comparados ya recortados). */
export function profileChanges(current: EditableProfile, values: Partial<EditableProfile>): ProfileUpdatePayload {
  const out: ProfileUpdatePayload = {}
  for (const key of ['first_name', 'last_name', 'email'] as const) {
    const next = (values[key] ?? '').trim()
    if (next !== current[key]) out[key] = next
  }
  return out
}

const required = (message: string) => z.string({ required_error: message }).min(1, message)

/** Cambio de contraseña: política del backend, distinta de la actual y confirmada. */
export const passwordChangeSchema = z.object({
  current_password: required('Ingresa tu contraseña actual.'),
  new_password: required('Ingresa la contraseña nueva.'),
  confirm_password: required('Confirma la contraseña nueva.')
}).superRefine((v, ctx) => {
  if (v.new_password && !passwordChecks(v.new_password).every(c => c.ok)) {
    ctx.addIssue({ code: 'custom', path: ['new_password'], message: 'La contraseña nueva aún no cumple todos los requisitos.' })
  } else if (v.new_password && v.new_password === v.current_password) {
    ctx.addIssue({ code: 'custom', path: ['new_password'], message: 'La contraseña nueva debe ser distinta de la actual.' })
  }
  if (v.confirm_password && v.new_password !== v.confirm_password) {
    ctx.addIssue({ code: 'custom', path: ['confirm_password'], message: 'Las contraseñas no coinciden.' })
  }
})

export type PasswordChangeInput = z.input<typeof passwordChangeSchema>
