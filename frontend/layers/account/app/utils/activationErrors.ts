import { LeoApiError } from '#leo-client/lib/errors'

export const NEUTRAL_MESSAGE = 'No pudimos verificar tus datos. Revisa el código, tu documento y tu fecha de nacimiento.'

export type ActivationFailure =
  | { kind: 'neutral', message: string }
  | { kind: 'validation', message: string }
  | { kind: 'rate', message: string, retryAfterSeconds: number | null }
  | { kind: 'recovery', message: string, reference: string | null }
  | { kind: 'retry', message: string }
  | { kind: 'other', message: string }

/** "2 minutos" / "45 segundos": espera legible. */
export function waitText(seconds: number | null): string {
  if (!seconds || seconds <= 0) return 'unos minutos'
  if (seconds < 60) return `${Math.ceil(seconds)} segundos`
  const m = Math.ceil(seconds / 60)
  return m === 1 ? '1 minuto' : `${m} minutos`
}

/** Clasifica el error del alta (400 neutro, 422 campos, 429, 409 recuperación, 502). `fallback` = mensaje legible genérico. */
export function classifyActivationError(err: unknown, fallback: string): ActivationFailure {
  if (!(err instanceof LeoApiError)) return { kind: 'other', message: fallback }
  switch (err.status) {
    case 400:
      return { kind: 'neutral', message: NEUTRAL_MESSAGE }
    case 422:
      return { kind: 'validation', message: err.message || fallback }
    case 429:
      return {
        kind: 'rate',
        retryAfterSeconds: err.retryAfterSeconds,
        message: `Hiciste demasiados intentos. Espera ${waitText(err.retryAfterSeconds)} e inténtalo de nuevo.`
      }
    case 409: {
      const ref = (err.details as { reference?: unknown } | null)?.reference
      return {
        kind: 'recovery',
        reference: typeof ref === 'string' ? ref : null,
        message: err.message || fallback
      }
    }
    case 502:
      return { kind: 'retry', message: 'No pudimos comunicarnos con el laboratorio en este momento. Inténtalo de nuevo en unos minutos.' }
    default:
      return { kind: 'other', message: fallback }
  }
}
