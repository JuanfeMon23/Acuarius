import { LeoApiError, leoErrorMessage } from '#leo-client/lib/errors'

/** Tipos y presentación de resultados (lógica pura, sin datos de salud en URLs ni almacenamiento). */

export interface OrderSummary {
  order_number: string
  date: string
  finalized_at: string | null
  status: string
  tests: string[]
  has_pdf: boolean
}

export interface OrdersPage {
  items: OrderSummary[]
  page: number
  page_size: number
  total: number
}

export interface ResultRow {
  code: string
  name: string
  section?: string | null
  value: string | number | boolean | null
  unit?: string | null
  options?: { id?: string, value?: string, label?: string, name?: string }[] | null
  reference?: string | null
  flag?: string | null
  is_reportable?: boolean
}

export interface OrderTestDetail {
  code: string
  name: string
  area?: string | null
  validated_by?: string | null
  validated_at?: string | null
  results: ResultRow[]
}

export interface OrderDetail {
  order_number: string
  tests: OrderTestDetail[]
}

export const PAGE_SIZE = 10

export function statusLabel(status: string): { label: string, variant: 'success' | 'warning' | 'neutral' } {
  if (status === 'finalizada') return { label: 'Resultados listos', variant: 'success' }
  if (status === 'en_proceso') return { label: 'En proceso', variant: 'warning' }
  return { label: 'En revisión', variant: 'neutral' }
}

/** "Hemograma, Glicemia y 2 más" */
export function testsSummary(tests: string[], max = 3): string {
  if (!tests.length) return 'Sin pruebas registradas'
  if (tests.length <= max) return tests.join(', ')
  const more = tests.length - max
  return `${tests.slice(0, max).join(', ')} y ${more} más`
}

const FLAGS: Record<string, { label: string, tone: 'warning' | 'danger' }> = {
  low: { label: 'Bajo', tone: 'warning' },
  high: { label: 'Alto', tone: 'warning' },
  critical_low: { label: 'Muy bajo', tone: 'danger' },
  critical_high: { label: 'Muy alto', tone: 'danger' },
  abnormal: { label: 'Fuera de lo esperado', tone: 'warning' }
}

/** Etiqueta de la marca del resultado; `null` si es normal o no hay marca. */
export function flagInfo(flag: string | null | undefined) {
  return (flag && FLAGS[flag]) || null
}

/** Valor listo para mostrar: Sí/No, etiqueta de la opción elegida o el valor con su unidad. */
export function displayValue(row: ResultRow): string {
  const v = row.value
  if (v === null || v === undefined || v === '') return 'Sin valor'
  if (typeof v === 'boolean') return v ? 'Positivo' : 'Negativo'
  if (typeof v === 'string' && row.options?.length) {
    const opt = row.options.find((o) => o.id === v || o.value === v)
    const label = opt?.label ?? opt?.name
    if (label) return label
  }
  return row.unit ? `${v} ${row.unit}` : String(v)
}

/** Solo los resultados que el laboratorio marcó como publicables. */
export const reportableRows = (rows: ResultRow[]) => rows.filter((r) => r.is_reportable !== false)

/** Nombre de archivo del PDF (solo caracteres seguros). */
export function pdfFilename(orderNumber: string): string {
  return `resultados-${orderNumber.replace(/[^A-Za-z0-9._-]/g, '')}.pdf`
}

export interface PatientOption { value: string, label: string }

/** Selector "Ver resultados de": yo + familiares que comparten conmigo. Valor `''` = yo. */
export function patientOptions(shares: { patient_id: string, display_name: string }[]): PatientOption[] {
  return [{ value: '', label: 'Yo' }, ...shares.map((s) => ({ value: s.patient_id, label: s.display_name }))]
}

/** Query de la API: `patient_id` solo para otra persona. */
export function listQuery(page: number, patientId: string) {
  return { page, page_size: PAGE_SIZE, ...(patientId ? { patient_id: patientId } : {}) }
}

/**
 * Mensaje legible del error de la lista. Si el backend rechaza el tamaño de
 * página (422, `details.field = page_size` con `max`, o la lista de `{field}`
 * de FastAPI) nombra el tope que informa el servidor; nunca se fija uno aquí.
 */
export function listErrorMessage(err: unknown): string {
  if (err instanceof LeoApiError && err.status === 422) {
    const list = Array.isArray(err.details) ? err.details : [err.details]
    const bad = list.find((d): d is { field: string, max?: unknown } => (d as { field?: unknown } | null)?.field === 'page_size')
    if (bad) {
      return typeof bad.max === 'number'
        ? `No se pueden mostrar tantos resultados por página: el máximo permitido es ${bad.max}.`
        : 'No se pueden mostrar tantos resultados por página. Inténtalo de nuevo más tarde.'
    }
  }
  return leoErrorMessage(err)
}
