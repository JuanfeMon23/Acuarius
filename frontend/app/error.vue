<template>
  <NuxtLayout name="public">
    <section class="flex flex-col items-center gap-4 py-12 text-center" aria-labelledby="error-title">
      <p class="text-5xl font-bold text-default-300" aria-hidden="true">{{ code }}</p>
      <h1 id="error-title" class="text-xl font-semibold">{{ title }}</h1>
      <p class="max-w-md text-sm text-text-muted">{{ detail }}</p>
      <UiButton variant="primary" @click="goHome">Ir al inicio</UiButton>
    </section>
  </NuxtLayout>
</template>

<script setup lang="ts">
import type { NuxtError } from '#app'
import { errorView } from './utils/errorView'

const props = defineProps<{ error: NuxtError }>()
const view = computed(() => errorView(props.error.statusCode))
const code = computed(() => props.error.statusCode ?? '')
const title = computed(() => view.value.title)
const detail = computed(() => view.value.detail)
const goHome = () => clearError({ redirect: '/' })
</script>
