<template>
  <div class="min-h-screen bg-background text-text">
    <header class="border-b border-border bg-surface">
      <div class="mx-auto flex h-14 max-w-2xl items-center px-4">
        <NuxtLink to="/" class="rounded-md text-lg font-semibold text-primary-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-500">
          Acuarius
        </NuxtLink>
      </div>
    </header>
    <main id="contenido" class="mx-auto max-w-2xl px-4 py-6 sm:py-10">
      <slot />
    </main>
  </div>
</template>
