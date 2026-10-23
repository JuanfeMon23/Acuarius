import { LeoApiError, leoErrorMessage } from '#leo-client/lib/errors'
import { CURRENT_PASSWORD_REQUIRED } from './profileSchema'
import type { PasswordPolicy } from '#andromeda/utils/passwordPolicy'
import { waitText } from './activationErrors'
import { passwordPolicyMessage } from './passwordPolicyErrors'

/** Error traducido: mensaje por campo, general, espera por 429 y si hay que vaciar la contraseña actual. */
export interface AccountFailure {
  fields: Record<string, string>
  form: string | null
  retryAfterSeconds: number | null
  rateLimited: boolean
  clearCurrentPassword: boolean
}

const failure = (partial: Partial<AccountFailure>): AccountFailure => ({
  fields: {}, form: null, retryAfterSeconds: null, rateLimited: false, clearCurrentPassword: false, ...partial
})

export const rateLimitMessage = (seconds: number | null) =>
  `Hiciste demasiados intentos. Espera ${waitText(seconds)} e inténtalo de nuevo.`

export const UPSTREAM_MESSAGE = 'No pudimos comunicarnos con el laboratorio en este momento. Inténtalo de nuevo en unos minutos.'

type FieldDetail = { field: string, message: string }

function fieldDetails(details: unknown): FieldDetail[] {
  if (!Array.isArray(details)) return []
  return details.filter((d): d is FieldDetail =>
    Boolean(d) && typeof d.field === 'string' && typeof d.message === 'string' && d.message.length > 0)
}

function common(err: LeoApiError): AccountFailure | null {
  if (err.status === 429) {
    return failure({ form: rateLimitMessage(err.retryAfterSeconds), retryAfterSeconds: err.retryAfterSeconds, rateLimited: true })
  }
  if (err.status === 502 || err.code === 'upstream_unavailable') return failure({ form: UPSTREAM_MESSAGE })
  return null
}

/**
 * Errores de `PATCH /account/profile`: contraseña requerida/incorrecta → campo
 * «contraseña actual» (que se vacía); correo repetido → campo correo; 422 →
 * campos del backend; 429 → espera. Nunca la respuesta cruda.
 */
export function profileUpdateFailure(err: unknown): AccountFailure {
  if (!(err instanceof LeoApiError)) return failure({ form: leoErrorMessage(err) })
  const known = common(err)
  if (known) return known
  if (err.code === 'current_password_required') {
    return failure({ fields: { current_password: CURRENT_PASSWORD_REQUIRED } })
  }
  if (err.code === 'invalid_current_password') {
    return failure({ fields: { current_password: 'La contraseña actual no es correcta.' }, clearCurrentPassword: true })
  }
  if (err.status === 409) {
    const field = (err.details as { field?: unknown } | null)?.field
    if (field === 'email' || field === undefined) {
      return failure({ fields: { email: 'Ese correo ya está en uso. Prueba con otro.' } })
    }
  }
  if (err.status === 422) {
    const fields: Record<string, string> = {}
    for (const d of fieldDetails(err.details)) {
      if (['first_name', 'last_name', 'email', 'current_password'].includes(d.field)) fields[d.field] ??= d.message
    }
    if (Object.keys(fields).length) return failure({ fields })
    return failure({ form: 'Algunos datos no son válidos. Revisa los campos.' })
  }
  return failure({ form: leoErrorMessage(err) })
}

/**
 * Errores de `POST /account/password`: `invalid_credentials` → «contraseña
 * actual» (que se vacía); `weak_password`/`same_password` → «contraseña nueva»;
 * un 422 con `details[].code` de la política (`too_short`, `no_symbol`…) →
 * «contraseña nueva», redactado con las cifras de `policy`.
 */
export function passwordFailure(err: unknown, policy: PasswordPolicy): AccountFailure {
  if (!(err instanceof LeoApiError)) return failure({ form: leoErrorMessage(err) })
  const known = common(err)
  if (known) return known
  if (err.code === 'invalid_credentials') {
    return failure({ fields: { current_password: 'La contraseña actual no es correcta.' }, clearCurrentPassword: true })
  }
  const unmet = passwordPolicyMessage(err, 'new_password', policy)
  if (unmet) return failure({ fields: { new_password: unmet } })
  if (err.code === 'same_password') {
    return failure({ fields: { new_password: 'La contraseña nueva debe ser distinta de la actual.' } })
  }
  if (err.code === 'weak_password') {
    const messages = fieldDetails(err.details).map(d => d.message.replace(/\.$/, ''))
    return failure({
      fields: {
        new_password: messages.length
          ? `La contraseña no cumple la política: ${messages.join('; ')}.`
          : 'La contraseña no cumple la política de seguridad. Revisa los requisitos.'
      }
    })
  }
  return failure({ form: leoErrorMessage(err) })
}
