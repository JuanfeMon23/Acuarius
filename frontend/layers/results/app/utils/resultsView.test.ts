import { describe, expect, it } from 'vitest'
import { LeoApiError } from '#leo-client/lib/errors'
import { displayValue, flagInfo, listErrorMessage, listQuery, patientOptions, pdfFilename, reportableRows, statusLabel, testsSummary } from './resultsView'

describe('resultsView', () => {
  it('estado legible', () => {
    expect(statusLabel('finalizada').label).toBe('Resultados listos')
    expect(statusLabel('otro').variant).toBe('neutral')
  })
  it('resumen de pruebas', () => {
    expect(testsSummary([])).toBe('Sin pruebas registradas')
    expect(testsSummary(['A', 'B'])).toBe('A, B')
    expect(testsSummary(['A', 'B', 'C', 'D', 'E'])).toBe('A, B, C y 2 más')
  })
  it('marcas: normal no muestra etiqueta', () => {
    expect(flagInfo('normal')).toBeNull()
    expect(flagInfo(null)).toBeNull()
    expect(flagInfo('critical_high')).toEqual({ label: 'Muy alto', tone: 'danger' })
  })
  it('valor mostrado', () => {
    const base = { code: 'x', name: 'x' }
    expect(displayValue({ ...base, value: 5.2, unit: 'mg/dL' })).toBe('5.2 mg/dL')
    expect(displayValue({ ...base, value: true })).toBe('Positivo')
    expect(displayValue({ ...base, value: null })).toBe('Sin valor')
    expect(displayValue({ ...base, value: 'o1', options: [{ id: 'o1', label: 'Reactivo' }] })).toBe('Reactivo')
  })
  it('filtra no publicables', () => {
    expect(reportableRows([{ code: 'a', name: 'a', value: 1, is_reportable: false }, { code: 'b', name: 'b', value: 1 }]).map((r) => r.code)).toEqual(['b'])
  })
  it('nombre de PDF seguro', () => {
    expect(pdfFilename('A-001/../x')).toBe('resultados-A-001..x.pdf')
  })
  it('selector y query', () => {
    expect(patientOptions([{ patient_id: 'p1', display_name: 'Ana' }])).toEqual([{ value: '', label: 'Yo' }, { value: 'p1', label: 'Ana' }])
    expect(listQuery(2, '')).toEqual({ page: 2, page_size: 10 })
    expect(listQuery(1, 'p1')).toEqual({ page: 1, page_size: 10, patient_id: 'p1' })
  })
})

describe('listErrorMessage', () => {
  it('422 de page_size nombra el tope del servidor (detalle como objeto o lista)', () => {
    const msg = 'No se pueden mostrar tantos resultados por página: el máximo permitido es 25.'
    expect(listErrorMessage(new LeoApiError(422, 'validation_error', 'x', { field: 'page_size', max: 25 }))).toBe(msg)
    expect(listErrorMessage(new LeoApiError(422, 'validation_error', 'x', [{ field: 'page_size', message: 'm', max: 25 }]))).toBe(msg)
  })
  it('sin el tope no inventa uno', () => {
    expect(listErrorMessage(new LeoApiError(422, 'validation_error', 'x', [{ field: 'page_size', message: 'm' }])))
      .not.toMatch(/\d/)
  })
  it('otros errores van por el mensaje legible general', () => {
    expect(listErrorMessage(new LeoApiError(404, 'not_found', 'Resultado no encontrado.'))).toBe('Resultado no encontrado.')
    expect(listErrorMessage(new Error('[GET] "http://x": <no response> Failed to fetch'))).toContain('No se pudo conectar')
  })
})
