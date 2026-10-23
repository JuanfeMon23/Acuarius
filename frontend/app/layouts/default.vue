<template>
  <LeoAppShell :items="menu" brand="Acuarius" brand-to="/resultados" storage-key="acuarius.sidebar.collapsed">
    <a
      href="#contenido"
      class="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-md focus:bg-surface focus:px-3 focus:py-2"
    >Saltar al contenido</a>
    <div id="contenido" tabindex="-1" class="outline-none">
      <slot />
    </div>
  </LeoAppShell>
</template>

<script setup lang="ts">
import type { UiSidebarItem } from '#andromeda/components/ui/UiSidebar.vue'
import { visibleScreens } from '../utils/moduleAccess'
import type { ScreenItem } from '../utils/moduleAccess'

// Iconos de trazo 24×24 (atributo `d` del path).
const ICONS: Record<ScreenItem['icon'], string> = {
  results: 'M9 3h6M10 3v6l-5.5 9.5A2 2 0 0 0 6.2 21h11.6a2 2 0 0 0 1.7-2.5L14 9V3',
  family: 'M17 20v-1a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v1M10 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM21 20v-1a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75'
}

const { can } = useLeoSession()
const menu = computed<UiSidebarItem[]>(() =>
  visibleScreens(can).map(({ label, to, icon }) => ({ label, to, icon: ICONS[icon] }))
)
</script>
