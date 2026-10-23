<template>
  <UiModal
    :open="open"
    size="lg"
    :title="`Orden ${orderNumber}`"
    description="Estos son los resultados que el laboratorio ya validó."
    @update:open="onOpen"
  >
    <div class="space-y-4" aria-live="polite">
      <div v-if="loading" class="flex items-center justify-center gap-2 py-10 text-text-muted">
        <UiSpinner size="md" color="primary" />
        <span>Cargando resultados…</span>
      </div>

      <div v-else-if="error" class="space-y-3">
        <UiAlert variant="danger" :message="error" />
        <UiButton variant="secondary" @click="emit('retry')">Reintentar</UiButton>
      </div>

      <template v-else-if="detail">
        <UiAlert v-if="downloadError" variant="danger" :message="downloadError" />
        <p v-if="!detail.tests.length" class="py-6 text-center text-text-muted">Esta orden no tiene pruebas con resultados.</p>

        <section v-for="test in detail.tests" :key="test.code" class="space-y-2" :aria-labelledby="`test-${test.code}`">
          <h3 :id="`test-${test.code}`" class="text-base font-semibold">{{ test.name }}</h3>
          <p v-if="test.validated_by" class="text-xs text-text-muted">
            Validado por {{ test.validated_by }}<template v-if="test.validated_at"> · {{ formatDateTime(test.validated_at) }}</template>
          </p>
          <ul class="divide-y divide-border rounded-lg border border-border">
            <li v-for="row in reportableRows(test.results)" :key="row.code" class="grid gap-1 px-3 py-2.5 sm:grid-cols-[1fr_auto]">
              <div class="min-w-0">
                <p class="text-sm font-medium">{{ row.name }}</p>
                <p v-if="row.reference" class="text-xs text-text-muted">Valor de referencia: {{ row.reference }}</p>
              </div>
              <p class="flex flex-wrap items-center gap-2 text-sm sm:justify-end">
                <span class="font-semibold" data-testid="result-value">{{ displayValue(row) }}</span>
                <UiStatusBadge v-if="flagInfo(row.flag)" :variant="flagInfo(row.flag)!.tone" :label="flagInfo(row.flag)!.label" />
              </p>
            </li>
          </ul>
        </section>

        <p class="text-xs text-text-muted">
          Estos valores no reemplazan la valoración de tu médico. Si tienes dudas, consúltalo.
        </p>
      </template>
    </div>

    <template #footer="{ close }">
      <UiButton variant="secondary" @click="close()">Cerrar</UiButton>
      <LeoCan v-if="hasPdf" tag="acuarius.results.download">
        <OrderPdfButton :order-number="orderNumber" :loading="downloading" @download="emit('download', $event)" />
      </LeoCan>
    </template>
  </UiModal>
</template>

<script setup lang="ts">
import { displayValue, flagInfo, reportableRows } from '../utils/resultsView'
import type { OrderDetail } from '../utils/resultsView'

defineProps<{
  open: boolean
  orderNumber: string
  detail: OrderDetail | null
  loading: boolean
  error: string | null
  downloading: boolean
  downloadError: string | null
  hasPdf: boolean
}>()

const emit = defineEmits<{ close: [], retry: [], download: [orderNumber: string] }>()

function onOpen(value: boolean) {
  if (!value) emit('close')
}
</script>
