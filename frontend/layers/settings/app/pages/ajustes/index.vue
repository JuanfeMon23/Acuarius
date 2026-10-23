<script setup lang="ts">
definePageMeta({ leo: { tag: 'acuarius.settings.view' } })
useHead({ title: 'Ajustes del sistema · Acuarius' })

const admin = useSettingsScreen()
</script>

<template>
  <UiSettingsPanel :admin="admin" />
</template>
