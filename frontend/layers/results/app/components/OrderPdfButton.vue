<template>
  <UiButton
    variant="secondary"
    :size="size"
    :loading="loading"
    :disabled="disabled"
    :aria-label="`Descargar PDF de la orden ${orderNumber}`"
    @click="emit('download', orderNumber)"
  >
    <svg v-if="!loading" viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <path d="M12 3v12m0 0-4-4m4 4 4-4M5 21h14" />
    </svg>
    {{ loading ? 'Descargando…' : 'Descargar PDF' }}
  </UiButton>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  orderNumber: string
  loading?: boolean
  /** Otra descarga en curso. */
  disabled?: boolean
  size?: 'sm' | 'md' | 'lg'
}>(), { loading: false, disabled: false, size: 'md' })

const emit = defineEmits<{ download: [orderNumber: string] }>()
</script>
