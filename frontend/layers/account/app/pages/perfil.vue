<template>
  <div class="mx-auto max-w-3xl space-y-5 px-4 py-6">
    <UiPageHeader
      title="Mi perfil"
      :description="p.displayName.value ? `Sesión de ${p.displayName.value}. Gestiona tus datos y tu contraseña.` : 'Gestiona tus datos y tu contraseña.'"
    />

    <div v-if="p.error.value" class="space-y-3">
      <UiAlert variant="danger" title="No pudimos cargar tu perfil" :message="p.error.value" />
      <UiButton variant="secondary" @click="p.load()">Intentar de nuevo</UiButton>
    </div>

    <div v-else-if="p.loading.value && !p.profile.value" class="flex items-center justify-center gap-2 py-16 text-text-muted" role="status">
      <UiSpinner size="md" color="primary" />
      <span>Cargando tu perfil…</span>
    </div>

    <template v-else-if="p.profile.value">
      <ProfilePersonalCard :profile="p.profile.value" :save="p.save" />
      <ProfilePasswordCard :change="p.changePassword" />
    </template>
  </div>
</template>

<script setup lang="ts">
// Cualquier paciente con sesión: sin tag (el backend no lo exige).
definePageMeta({ leo: {} })
useHead({ title: 'Mi perfil' })

const p = useAccountProfile()
onMounted(() => p.load())
</script>
