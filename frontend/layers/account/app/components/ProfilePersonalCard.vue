<script setup lang="ts">
import type { AccountFailure } from '../utils/profileErrors'
import { profileUpdateFailure } from '../utils/profileErrors'
import type { AccountProfile, EditableProfile, ProfileUpdatePayload } from '../utils/profileSchema'
import { profileChanges, profileFormSchema } from '../utils/profileSchema'

/**
 * Datos personales: nombres y correo editables; usuario en solo lectura.
 * «Contraseña actual» solo aparece (y es obligatoria) si el correo cambió.
 * Un 429 bloquea el botón con cuenta regresiva. El documento no se muestra.
 */
const props = defineProps<{
  profile: AccountProfile
  save: (body: ProfileUpdatePayload) => Promise<unknown>
}>()

const toast = useToast()
const { secondsLeft, start } = useCountdown()
const formEl = ref<HTMLFormElement | null>(null)
const sessionsNotice = ref(false)

const toValues = (p: AccountProfile): EditableProfile => ({ first_name: p.first_name, last_name: p.last_name, email: p.email })

const form = useZodForm(profileFormSchema(() => props.profile.email), {
  initialValues: () => ({ ...toValues(props.profile), current_password: '' })
})
const values = form.values as Partial<EditableProfile> & { current_password?: string }

const changes = computed(() => profileChanges(toValues(props.profile), values))
const dirty = computed(() => Object.keys(changes.value).length > 0)
const emailChanged = computed(() => changes.value.email !== undefined)
const blocked = computed(() => secondsLeft.value > 0)

// Si el perfil se recarga desde fuera, el formulario parte de lo guardado.
watch(() => props.profile, () => form.reset())

async function focusFirstInvalid() {
  await nextTick()
  const target = formEl.value?.querySelector<HTMLElement>('[aria-invalid="true"]')
  target?.focus()
}

function showFailure(f: AccountFailure) {
  form.formError.value = f.form
  for (const [field, message] of Object.entries(f.fields)) {
    form.setFieldError(field as 'email' | 'current_password', message)
  }
  if (f.clearCurrentPassword) form.setFieldValue('current_password', '', false)
  if (f.rateLimited) start(f.retryAfterSeconds)
}

const onSubmit = form.submit(async () => {
  sessionsNotice.value = false
  const body: ProfileUpdatePayload = { ...changes.value }
  const changedEmail = emailChanged.value
  if (changedEmail) body.current_password = values.current_password ?? ''
  try {
    await props.save(body)
    form.reset({ ...toValues(props.profile), current_password: '' })
    sessionsNotice.value = changedEmail
    toast.success('Datos actualizados')
  } catch (err) {
    showFailure(profileUpdateFailure(err))
    await focusFirstInvalid()
  }
})

onBeforeUnmount(() => form.reset())
</script>

<template>
  <UiCard as="section" title="Datos personales" description="Tu nombre y tu correo. Tu usuario y tu documento no se pueden cambiar aquí.">
    <form ref="formEl" class="flex flex-col gap-4" novalidate data-testid="profile-form" @submit.prevent="onSubmit">
      <UiAlert v-if="sessionsNotice" variant="success" data-testid="profile-sessions-notice">
        Correo actualizado. Por seguridad cerramos tus otras sesiones abiertas (otros dispositivos y navegadores); esta sesión se mantiene.
      </UiAlert>
      <UiAlert v-if="form.formError.value" variant="warning" :message="form.formError.value" data-testid="profile-error" />
      <p v-if="blocked" class="text-sm text-text-muted" role="status" aria-live="polite" data-testid="profile-wait">
        Podrás intentarlo de nuevo en {{ secondsLeft }} segundos.
      </p>

      <div class="text-sm">
        <div class="font-medium text-text-muted">Usuario</div>
        <div class="mt-1" data-testid="profile-username"><code>{{ profile.username }}</code></div>
      </div>

      <div class="grid gap-4 sm:grid-cols-2">
        <UiFormField name="first_name" label="Nombres" required>
          <UiTextInput autocomplete="given-name" />
        </UiFormField>
        <UiFormField name="last_name" label="Apellidos" required>
          <UiTextInput autocomplete="family-name" />
        </UiFormField>
      </div>
      <UiFormField name="email" label="Correo electrónico" required>
        <UiTextInput type="email" autocomplete="email" inputmode="email" />
      </UiFormField>
      <UiFormField v-if="emailChanged" name="current_password" label="Contraseña actual" hint="Necesaria para confirmar el cambio de correo." required>
        <UiPasswordInput autocomplete="current-password" />
      </UiFormField>

      <div>
        <UiButton type="submit" class="w-full sm:w-auto" :loading="form.isSubmitting.value" :disabled="!dirty || blocked" data-testid="profile-save">
          Guardar cambios
        </UiButton>
      </div>
    </form>
  </UiCard>
</template>
