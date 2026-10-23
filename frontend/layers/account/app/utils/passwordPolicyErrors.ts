import { LeoApiError } from '#leo-client/lib/errors'
import type { PasswordPolicy } from '#andromeda/utils/passwordPolicy'

/** Requisito incumplido (`details[].code` de un 422) en palabras, con las cifras de la política vigente. */
function requirement(code: string, policy: PasswordPolicy): string | null {
  switch (code) {
    case 'too_short': return `tener al menos ${policy.min_length} caracteres`
    case 'too_long': return `tener como máximo ${policy.max_length} caracteres`
    case 'no_lowercase': return 'incluir una letra minúscula'
    case 'no_uppercase': return 'incluir una letra mayúscula'
    case 'no_digit': return 'incluir un número'
    case 'no_symbol': return 'incluir un símbolo'
    default: return null
  }
}

/**
 * Mensaje legible de un 422 `validation_error` cuyos `details` traen `code` de la
 * política de contraseña para `field` (p. ej. `password`, `new_password`);
 * `null` si el error no es de esa clase. Nunca incluye la contraseña.
 */
export function passwordPolicyMessage(err: unknown, field: string, policy: PasswordPolicy): string | null {
  if (!(err instanceof LeoApiError) || err.status !== 422 || !Array.isArray(err.details)) return null
  const items = (err.details as { field?: unknown, code?: unknown }[])
    .filter(d => d && d.field === field && typeof d.code === 'string')
    .map(d => requirement(d.code as string, policy))
    .filter((text): text is string => text !== null)
  return items.length ? `La contraseña debe ${items.join(', ')}.` : null
}
