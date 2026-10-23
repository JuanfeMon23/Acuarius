/** Segundos que faltan hasta `until` (ms epoch) desde `now`; nunca negativo. */
export function remainingSeconds(until: number, now: number): number {
  return Math.max(0, Math.ceil((until - now) / 1000))
}

/** Espera por defecto cuando un 429 llega sin `Retry-After`. */
export const DEFAULT_WAIT_SECONDS = 60
