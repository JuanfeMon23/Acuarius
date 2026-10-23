<template>
  <div class="mx-auto max-w-5xl space-y-5 px-4 py-6">
    <UiPageHeader
      title="Mis resultados"
      description="Aquí encuentras los resultados de tus exámenes cuando el laboratorio los termina."
    />

    <UiCard v-if="r.options.value.length > 1">
      <div class="max-w-sm">
        <UiFormField label="Ver resultados de" hint="Aparecen las personas de tu familia que decidieron compartir sus resultados contigo.">
          <UiSelect :model-value="r.patientId.value" :options="r.options.value" @update:model-value="r.selectPatient" />
        </UiFormField>
      </div>
    </UiCard>

    <UiAlert v-if="r.downloadError.value && !selected" variant="danger" title="No se pudo descargar el PDF" :message="r.downloadError.value" />

    <!-- Error de carga -->
    <div v-if="r.error.value" class="space-y-3">
      <UiAlert variant="danger" title="No pudimos cargar los resultados" :message="r.error.value" />
      <UiButton variant="secondary" @click="r.loadList()">Intentar de nuevo</UiButton>
    </div>

    <!-- Cargando (primera vez) -->
    <div v-else-if="r.loading.value && !r.data.value" class="flex items-center justify-center gap-2 py-16 text-text-muted" role="status">
      <UiSpinner size="md" color="primary" />
      <span>Cargando tus resultados…</span>
    </div>

    <!-- Vacío -->
    <UiCard v-else-if="r.data.value && r.data.value.items.length === 0">
      <div class="space-y-2 py-6 text-center">
        <p class="text-lg font-semibold">Aún no hay resultados para mostrar</p>
        <p class="text-sm text-text-muted">
          <template v-if="r.patientId.value">{{ r.ownerName.value }} todavía no tiene resultados disponibles.</template>
          <template v-else>Cuando el laboratorio termine tus exámenes, aparecerán aquí. Si ya pasó el tiempo que te indicaron, consulta con el laboratorio.</template>
        </p>
      </div>
    </UiCard>

    <template v-else-if="r.data.value">
      <p class="text-sm text-text-muted" aria-live="polite">
        Resultados de <strong class="text-text">{{ r.ownerName.value }}</strong>
      </p>

      <!-- Móvil: tarjetas -->
      <ul class="space-y-3 sm:hidden" :aria-busy="r.loading.value || undefined" aria-label="Órdenes con resultados">
        <li v-for="o in r.data.value.items" :key="o.order_number">
          <UiCard as="article" :padding="'sm'">
            <div class="space-y-3">
              <div class="flex items-start justify-between gap-2">
                <p class="font-semibold">{{ formatDateTime(o.date) }}</p>
                <UiStatusBadge dot :variant="statusLabel(o.status).variant" :label="statusLabel(o.status).label" />
              </div>
              <p class="text-sm text-text-muted">{{ testsSummary(o.tests) }}</p>
              <div class="flex flex-wrap gap-2">
                <UiButton size="md" class="flex-1" @click="open(o.order_number)">Ver resultados</UiButton>
                <LeoCan v-if="o.has_pdf" tag="acuarius.results.download">
                  <OrderPdfButton :order-number="o.order_number" :loading="r.downloading.value === o.order_number" :disabled="!!r.downloading.value" @download="r.downloadPdf" />
                </LeoCan>
              </div>
            </div>
          </UiCard>
        </li>
      </ul>
      <UiPagination
        class="sm:hidden"
        :page="r.data.value.page"
        :page-size="r.data.value.page_size"
        :total="r.data.value.total"
        @update:page="r.goToPage"
      />

      <!-- Pantallas amplias: tabla -->
      <UiDataTable
        class="hidden sm:block"
        :columns="columns"
        :rows="rows"
        :loading="r.loading.value"
        :row-key="(row) => row.order_number"
        :page="r.data.value.page"
        :page-size="r.data.value.page_size"
        :total="r.data.value.total"
        @update:page="r.goToPage"
      >
        <template #cell-date="{ row }">{{ formatDateTime(row.date) }}</template>
        <template #cell-tests="{ row }">{{ testsSummary(row.tests, 4) }}</template>
        <template #cell-status="{ row }">
          <UiStatusBadge dot :variant="statusLabel(row.status).variant" :label="statusLabel(row.status).label" />
        </template>
        <template #cell-actions="{ row }">
          <div class="flex justify-end gap-2">
            <UiButton size="sm" @click="open(row.order_number)">Ver resultados</UiButton>
            <LeoCan v-if="row.has_pdf" tag="acuarius.results.download">
              <OrderPdfButton size="sm" :order-number="row.order_number" :loading="r.downloading.value === row.order_number" :disabled="!!r.downloading.value" @download="r.downloadPdf" />
            </LeoCan>
          </div>
        </template>
      </UiDataTable>
    </template>

    <ResultDetailModal
      v-if="selected"
      :open="!!selected"
      :order-number="selected"
      :detail="r.detail.value"
      :loading="r.detailLoading.value"
      :error="r.detailError.value"
      :downloading="r.downloading.value === selected"
      :download-error="r.downloadError.value"
      :has-pdf="selectedHasPdf"
      @close="close"
      @retry="open(selected)"
      @download="r.downloadPdf"
    />
  </div>
</template>

<script setup lang="ts">
import type { UiDataTableColumn } from '#andromeda/components/ui/UiDataTable.vue'
import { statusLabel, testsSummary } from '../utils/resultsView'
import type { OrderSummary } from '../utils/resultsView'

definePageMeta({ leo: { tag: 'acuarius.results.view' } })
useHead({ title: 'Mis resultados' })

type Row = OrderSummary & { actions: string }
const columns: UiDataTableColumn<Row>[] = [
  { key: 'date', label: 'Fecha' },
  { key: 'tests', label: 'Pruebas' },
  { key: 'status', label: 'Estado' },
  { key: 'actions', label: 'Acciones', class: 'text-right' }
]

const r = useResults()
const selected = ref<string | null>(null)
const rows = computed<Row[]>(() => (r.data.value?.items ?? []).map((o) => ({ ...o, actions: '' })))
const selectedHasPdf = computed(() => !!r.data.value?.items.find((o) => o.order_number === selected.value)?.has_pdf)

async function open(orderNumber: string) {
  selected.value = orderNumber
  await r.openOrder(orderNumber)
}
function close() {
  selected.value = null
  r.closeOrder()
}

r.init()
</script>
