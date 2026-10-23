<template>
  <div class="space-y-6">
    <!-- Bienvenida -->
    <UiCard v-if="createdUsername" as="section" aria-labelledby="bienvenida-title">
      <div class="space-y-4 text-center">
        <p class="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-success-50 text-success-600" aria-hidden="true">
          <svg viewBox="0 0 24 24" class="h-7 w-7" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m5 12 5 5L20 7" /></svg>
        </p>
        <h1 id="bienvenida-title" ref="headingRef" tabindex="-1" class="text-2xl font-semibold outline-none">¡Bienvenido a Acuarius!</h1>
        <p class="text-text-muted">
          Tu cuenta quedó creada con el usuario <strong class="text-text">{{ createdUsername }}</strong>.
          Ya puedes iniciar sesión para ver tus resultados.
        </p>
        <UiButton to="/resultados" size="lg" class="w-full sm:w-auto">Iniciar sesión</UiButton>
      </div>
    </UiCard>

    <template v-else>
      <header class="space-y-2">
        <h1 class="text-2xl font-semibold tracking-tight">Activa tu cuenta</h1>
        <p class="text-sm text-text-muted">
          Necesitas el código de activación que te entregó el laboratorio en tu comprobante.
          Solo toma unos minutos.
        </p>
      </header>

      <ol class="flex gap-2" aria-label="Pasos">
        <li
          v-for="(s, i) in ACTIVATION_STEPS"
          :key="s.title"
          class="flex-1"
          :aria-current="i === step ? 'step' : undefined"
        >
          <div class="h-1.5 rounded-full" :class="i <= step ? 'bg-primary-500' : 'bg-default-200'" />
          <span class="mt-1 block text-xs" :class="i === step ? 'font-semibold text-text' : 'text-text-muted'">
            <span class="sr-only">Paso {{ i + 1 }}: </span>{{ s.title }}
          </span>
        </li>
      </ol>

      <UiCard as="section" aria-labelledby="paso-title">
        <form class="space-y-5" novalidate @submit.prevent="onSubmit">
          <h2 id="paso-title" ref="headingRef" tabindex="-1" class="text-lg font-semibold outline-none">
            Paso {{ step + 1 }} de {{ ACTIVATION_STEPS.length }}: {{ ACTIVATION_STEPS[step]!.title }}
          </h2>

          <UiAlert v-if="failure" :variant="alertVariant" :title="alertTitle" data-testid="activation-alert">
            <p>{{ failure.message }}</p>
            <template v-if="failure.kind === 'recovery'">
              <p v-if="failure.reference" class="mt-2">
                Tu referencia es <strong class="select-all font-mono" data-testid="recovery-reference">{{ failure.reference }}</strong>.
              </p>
              <p class="mt-1">Guárdala y comunícate con el laboratorio. No necesitas volver a intentarlo: tu código ya fue validado.</p>
            </template>
            <p v-if="failure.kind === 'rate' && secondsLeft > 0" class="mt-1" aria-live="polite">
              Podrás intentarlo en {{ secondsLeft }} segundos.
            </p>
          </UiAlert>

          <!-- Paso 1 -->
          <div v-show="step === 0" class="space-y-4">
            <UiFormField name="code" label="Código de activación" hint="Está en tu comprobante. Ejemplo: ABCDE-FGHJK" required>
              <UiTextInput
                placeholder="ABCDE-FGHJK"
                autocomplete="off"
                autocapitalize="characters"
                spellcheck="false"
                inputmode="text"
                class="font-mono tracking-widest"
                @update:model-value="onCodeInput"
              />
            </UiFormField>
          </div>

          <!-- Paso 2 -->
          <div v-show="step === 1" class="space-y-4">
            <UiFormField name="document_type" label="Tipo de documento" required>
              <UiSelect :options="documentOptions" placeholder="Elige una opción" />
            </UiFormField>
            <UiFormField name="document_number" label="Número de documento" hint="Solo números y letras, sin puntos." required>
              <UiTextInput autocomplete="off" inputmode="text" />
            </UiFormField>
            <UiFormField name="birth_date" label="Fecha de nacimiento" required>
              <UiTextInput type="date" min="1900-01-01" :max="today" autocomplete="bday" />
            </UiFormField>
          </div>

          <!-- Paso 3 -->
          <div v-show="step === 2" class="space-y-4">
            <UiFormField name="username" label="Usuario" hint="Con este usuario iniciarás sesión. Minúsculas, números, punto, guion o guion bajo." required>
              <UiTextInput autocomplete="username" autocapitalize="none" spellcheck="false" />
            </UiFormField>
            <UiFormField name="email" label="Correo electrónico" required>
              <UiTextInput type="email" autocomplete="email" inputmode="email" />
            </UiFormField>
            <UiFormField name="password" label="Contraseña" required>
              <UiPasswordInput autocomplete="new-password" />
            </UiFormField>
            <ul class="space-y-1 text-sm" aria-label="Requisitos de la contraseña" data-testid="password-checks">
              <li v-for="c in checks" :key="c.id" class="flex items-center gap-2" :class="c.ok ? 'text-success-700' : 'text-text-muted'">
                <span aria-hidden="true">{{ c.ok ? '✓' : '○' }}</span>
                <span>{{ c.label }}<span class="sr-only">{{ c.ok ? ' (cumplido)' : ' (pendiente)' }}</span></span>
              </li>
            </ul>
            <UiFormField name="password_confirm" label="Repite la contraseña" required>
              <UiPasswordInput autocomplete="new-password" />
            </UiFormField>
          </div>

          <div class="flex flex-col-reverse gap-2 sm:flex-row sm:justify-between">
            <UiButton v-if="step > 0" variant="secondary" size="lg" @click="goBack">Atrás</UiButton>
            <span v-else />
            <UiButton v-if="step < ACTIVATION_STEPS.length - 1" size="lg" @click="goNext">Siguiente</UiButton>
            <UiButton v-else type="submit" size="lg" :loading="form.isSubmitting.value" :disabled="secondsLeft > 0">
              Crear mi cuenta
            </UiButton>
          </div>
        </form>
      </UiCard>

      <p class="text-center text-sm text-text-muted">
        ¿Ya tienes cuenta? <NuxtLink to="/resultados" class="font-medium text-primary-700 underline">Inicia sesión</NuxtLink>
      </p>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ACTIVATION_STEPS, DOCUMENT_TYPES, maskActivationCode, passwordChecks } from '../utils/activationSchema'

// Página PÚBLICA: no exige sesión de Leo; usa el layout sin menú.
definePageMeta({ layout: 'public', leo: { public: true } })
useHead({ title: 'Activar mi cuenta' })

const { form, step, failure, createdUsername, secondsLeft, next, back, submit } = useActivation()
const headingRef = ref<HTMLElement | null>(null)
const documentOptions = DOCUMENT_TYPES.map((d) => ({ value: d.value, label: `${d.value} · ${d.label}` }))
const today = new Date().toISOString().slice(0, 10)

const checks = computed(() => passwordChecks(String(form.values.password ?? '')))

const alertVariant = computed(() => (failure.value?.kind === 'recovery' || failure.value?.kind === 'rate' ? 'warning' : 'danger'))
const alertTitle = computed(() => {
  switch (failure.value?.kind) {
    case 'recovery': return 'Tu cuenta no pudo terminar de crearse'
    case 'rate': return 'Espera un momento'
    case 'retry': return 'Inténtalo de nuevo'
    default: return 'No pudimos continuar'
  }
})

function onCodeInput(value: string) {
  const masked = maskActivationCode(String(value))
  if (masked !== value) form.setFieldValue('code', masked)
}

async function focusHeading() {
  await nextTick()
  headingRef.value?.focus()
}

async function goNext() {
  if (await next()) await focusHeading()
}
async function goBack() {
  back()
  await focusHeading()
}
async function onSubmit() {
  // Enter en un paso intermedio avanza en vez de enviar.
  if (step.value < ACTIVATION_STEPS.length - 1) return goNext()
  await submit()
  await focusHeading()
}
</script>
