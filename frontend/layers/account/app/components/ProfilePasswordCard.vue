<script setup lang="ts">
import type { AccountFailure } from '../utils/profileErrors'
import { passwordFailure } from '../utils/profileErrors'
import { passwordChangeSchema } from '../utils/profileSchema'

/**
 * Cambiar la contraseña propia: actual, nueva y confirmación, con los
 * requisitos en vivo. Las contraseñas solo viven en los campos: se limpian al
 * terminar con éxito, al fallar la actual y al salir. Un 429 bloquea el botón
 * con cuenta regresiva.
 */
const props = defineProps<{
  change: (body: { current_password: string, new_password: string }) => Promise<unknown>
}>()

const toast = useToast()
const { secondsLeft, start } = useCountdown()
const formEl = ref<HTMLFormElement | null>(null)
const success = ref(false)

const EMPTY = { current_password: '', new_password: '', confirm_password: '' }
const form = useZodForm(passwordChangeSchema, { initialValues: () => ({ ...EMPTY }) })
const values = form.values as Partial<typeof EMPTY>
const blocked = computed(() => secondsLeft.value > 0)

async function focusFirstInvalid() {
  await nextTick()
  formEl.value?.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus()
}

function showFailure(f: AccountFailure) {
  form.formError.value = f.form
  for (const [field, message] of Object.entries(f.fields)) {
    form.setFieldError(field as 'current_password' | 'new_password', message)
  }
  if (f.clearCurrentPassword) form.setFieldValue('current_password', '', false)
  if (f.rateLimited) start(f.retryAfterSeconds)
}

const onSubmit = form.submit(async (v) => {
  success.value = false
  try {
    await props.change({ current_password: v.current_password, new_password: v.new_password })
    form.reset()
    success.value = true
    toast.success('Contraseña actualizada')
  } catch (err) {
    showFailure(passwordFailure(err))
    await focusFirstInvalid()
  }
})

onBeforeUnmount(() => form.reset())
</script>

<template>
  <UiCard as="section" title="Cambiar contraseña" description="Elige una contraseña que no uses en otro sitio. Al cambiarla cerramos tus otras sesiones abiertas; esta se mantiene.">
    <form ref="formEl" class="flex flex-col gap-4" novalidate data-testid="password-form" @submit.prevent="onSubmit">
      <UiAlert v-if="success" variant="success" data-testid="password-success">
        Contraseña actualizada. Cerramos tus otras sesiones abiertas; esta sesión se mantiene.
      </UiAlert>
      <UiAlert v-if="form.formError.value" variant="warning" :message="form.formError.value" data-testid="password-error" />
      <p v-if="blocked" class="text-sm text-text-muted" role="status" aria-live="polite" data-testid="password-wait">
        Podrás intentarlo de nuevo en {{ secondsLeft }} segundos.
      </p>

      <UiFormField name="current_password" label="Contraseña actual" required>
        <UiPasswordInput autocomplete="current-password" />
      </UiFormField>
      <UiFormField name="new_password" label="Contraseña nueva" required>
        <UiPasswordInput autocomplete="new-password" />
      </UiFormField>
      <PasswordRequirements :password="values.new_password ?? ''" />
      <UiFormField name="confirm_password" label="Confirmar contraseña nueva" required>
        <UiPasswordInput autocomplete="new-password" />
      </UiFormField>

      <div>
        <UiButton type="submit" class="w-full sm:w-auto" :loading="form.isSubmitting.value" :disabled="blocked" data-testid="password-save">
          Cambiar contraseña
        </UiButton>
      </div>
    </form>
  </UiCard>
</template>
