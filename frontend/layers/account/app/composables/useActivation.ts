import { ACTIVATION_STEPS, activationSchema } from '../utils/activationSchema'
import type { ActivationFailure } from '../utils/activationErrors'
import { classifyActivationError } from '../utils/activationErrors'

/**
 * Lógica del alta por pasos: formulario (zod + vee-validate), paso actual,
 * envío a `POST /api/v1/account/activate` y clasificación del error.
 * Nada del formulario se guarda en el navegador (ni URL, ni localStorage).
 */
export function useActivation() {
  const api = useLeoAppApi()
  const step = ref(0)
  const failure = ref<ActivationFailure | null>(null)
  const createdUsername = ref<string | null>(null)
  const waitUntil = ref(0)
  const now = ref(Date.now())
  let timer: ReturnType<typeof setInterval> | undefined

  const form = useZodForm(activationSchema, {
    initialValues: {
      code: '', document_type: '', document_number: '', birth_date: '',
      username: '', email: '', password: '', password_confirm: ''
    }
  })

  const secondsLeft = computed(() => Math.max(0, Math.ceil((waitUntil.value - now.value) / 1000)))

  function startWait(seconds: number | null) {
    waitUntil.value = Date.now() + (seconds ?? 60) * 1000
    now.value = Date.now()
    clearInterval(timer)
    timer = setInterval(() => {
      now.value = Date.now()
      if (now.value >= waitUntil.value) clearInterval(timer)
    }, 1000)
  }
  onBeforeUnmount(() => clearInterval(timer))

  /** Valida los campos del paso actual; avanza solo si todos son válidos. */
  async function next(): Promise<boolean> {
    const fields = ACTIVATION_STEPS[step.value]!.fields
    const results = await Promise.all(fields.map((f) => form.validateField(f)))
    if (!results.every((r) => r.valid)) return false
    failure.value = null
    step.value = Math.min(step.value + 1, ACTIVATION_STEPS.length - 1)
    return true
  }

  function back() {
    failure.value = null
    step.value = Math.max(0, step.value - 1)
  }

  const stepOfField = (field: string) => ACTIVATION_STEPS.findIndex((s) => (s.fields as readonly string[]).includes(field))

  const submit = form.submit(async (values) => {
    failure.value = null
    const { password_confirm: _confirm, ...payload } = values
    try {
      const out = await api.post<{ username: string }>('/account/activate', payload)
      createdUsername.value = out.username
    } catch (err) {
      const result = classifyActivationError(err, leoErrorMessage(err))
      failure.value = result
      if (result.kind === 'rate') startWait(result.retryAfterSeconds)
      if (result.kind === 'validation') {
        form.applyApiError(err)
        const firstBad = Object.keys(form.errors.value).map(stepOfField).filter((i) => i >= 0).sort()[0]
        if (firstBad !== undefined) step.value = firstBad
      }
      if (result.kind !== 'validation') {
        form.setFieldValue('password', '')
        form.setFieldValue('password_confirm', '')
      }
      if (result.kind === 'neutral') step.value = 0
    }
  })

  return { form, step, failure, createdUsername, secondsLeft, next, back, submit }
}
