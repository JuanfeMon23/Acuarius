import { PAGE_SIZE, listQuery, patientOptions, pdfFilename } from '../utils/resultsView'
import type { OrderDetail, OrdersPage } from '../utils/resultsView'

interface FamilyShare { patient_id: string, display_name: string }

/**
 * Resultados del paciente (o de un familiar que comparte): lista paginada,
 * detalle y descarga del PDF. El paciente elegido vive solo en memoria
 * (nunca en la URL ni en localStorage).
 */
export function useResults() {
  const api = useLeoAppApi()
  const { can } = useLeoSession()

  const shares = ref<FamilyShare[]>([])
  const patientId = ref('')
  const page = ref(1)
  const data = ref<OrdersPage | null>(null)
  const loading = ref(true)
  const error = ref<string | null>(null)

  const detail = ref<OrderDetail | null>(null)
  const detailLoading = ref(false)
  const detailError = ref<string | null>(null)

  const downloading = ref<string | null>(null)
  const downloadError = ref<string | null>(null)

  const options = computed(() => patientOptions(shares.value))
  const ownerName = computed(() => options.value.find((o) => o.value === patientId.value)?.label ?? 'Yo')

  // Descartar respuestas viejas si el usuario cambió de persona/página mientras cargaba.
  let seq = 0

  async function loadList() {
    const mine = ++seq
    loading.value = true
    error.value = null
    try {
      const res = await api.get<OrdersPage>('/results', { query: listQuery(page.value, patientId.value) })
      if (mine === seq) data.value = res
    } catch (err) {
      if (mine === seq) {
        error.value = leoErrorMessage(err)
        data.value = null
      }
    } finally {
      if (mine === seq) loading.value = false
    }
  }

  async function loadShares() {
    // Sin permiso de familia no hay selector: solo "Yo".
    if (!can('acuarius.family.view')) return
    try {
      const me = await api.get<{ shares_received: FamilyShare[] }>('/family/me')
      shares.value = me.shares_received ?? []
    } catch {
      shares.value = [] // el selector es opcional: la lista propia sigue funcionando
    }
  }

  async function init() {
    await Promise.all([loadShares(), loadList()])
  }

  async function selectPatient(id: string) {
    patientId.value = id
    page.value = 1
    detail.value = null
    await loadList()
  }

  async function goToPage(next: number) {
    page.value = next
    await loadList()
  }

  async function openOrder(orderNumber: string) {
    detail.value = null
    detailError.value = null
    detailLoading.value = true
    try {
      const q = patientId.value ? { patient_id: patientId.value } : undefined
      detail.value = await api.get<OrderDetail>(`/results/${encodeURIComponent(orderNumber)}`, { query: q })
    } catch (err) {
      detailError.value = leoErrorMessage(err)
    } finally {
      detailLoading.value = false
    }
  }

  function closeOrder() {
    detail.value = null
    detailError.value = null
    detailLoading.value = false
  }

  /** Descarga el PDF por la API firmada (blob); nunca se abre en otra pestaña ni se guarda. */
  async function downloadPdf(orderNumber: string): Promise<boolean> {
    if (downloading.value) return false
    downloading.value = orderNumber
    downloadError.value = null
    try {
      const q = patientId.value ? { patient_id: patientId.value } : undefined
      const blob = await api.get<Blob>(`/results/${encodeURIComponent(orderNumber)}/report.pdf`, { query: q, responseType: 'blob' })
      downloadBlob(blob, pdfFilename(orderNumber))
      return true
    } catch (err) {
      downloadError.value = leoErrorMessage(err)
      return false
    } finally {
      downloading.value = null
    }
  }

  return {
    PAGE_SIZE, shares, patientId, page, data, loading, error, options, ownerName,
    detail, detailLoading, detailError, downloading, downloadError,
    init, loadList, selectPatient, goToPage, openOrder, closeOrder, downloadPdf
  }
}
