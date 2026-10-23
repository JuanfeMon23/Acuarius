<template>
  <div class="flex justify-center py-16">
    <UiSpinner size="lg" color="primary" label="Cargando" />
  </div>
</template>

<script setup lang="ts">
// La raíz solo redirige. Exige sesión (middleware de leo-client): sin ella, va a iniciar sesión.
definePageMeta({ leo: {} })
await navigateTo('/resultados', { replace: true })
</script>
