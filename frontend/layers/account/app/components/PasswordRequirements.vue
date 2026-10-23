<script setup lang="ts">
import { passwordChecks } from '../utils/activationSchema'

/** Requisitos de la contraseña en vivo (política del backend). Candidato a promover a Andromeda. */
const props = defineProps<{ password: string }>()
const checks = computed(() => passwordChecks(props.password))
</script>

<template>
  <ul class="space-y-1 text-sm" aria-label="Requisitos de la contraseña" data-testid="password-checks">
    <li v-for="c in checks" :key="c.id" class="flex items-center gap-2" :class="c.ok ? 'text-success-700' : 'text-text-muted'">
      <span aria-hidden="true">{{ c.ok ? '✓' : '○' }}</span>
      <span>{{ c.label }}<span class="sr-only">{{ c.ok ? ' (cumplido)' : ' (pendiente)' }}</span></span>
    </li>
  </ul>
</template>
