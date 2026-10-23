import { DEFAULT_WAIT_SECONDS, remainingSeconds } from '../utils/countdown'

/**
 * Cuenta regresiva en segundos para un 429 (`Retry-After`). `start(null)` usa
 * la espera por defecto. El temporizador se limpia al desmontar.
 */
export function useCountdown() {
  const until = ref(0)
  const now = ref(Date.now())
  let timer: ReturnType<typeof setInterval> | undefined

  const secondsLeft = computed(() => remainingSeconds(until.value, now.value))

  function stop() {
    clearInterval(timer)
    until.value = 0
  }

  function start(seconds: number | null) {
    until.value = Date.now() + (seconds ?? DEFAULT_WAIT_SECONDS) * 1000
    now.value = Date.now()
    clearInterval(timer)
    timer = setInterval(() => {
      now.value = Date.now()
      if (now.value >= until.value) clearInterval(timer)
    }, 1000)
  }

  onBeforeUnmount(() => clearInterval(timer))

  return { secondsLeft, start, stop }
}
