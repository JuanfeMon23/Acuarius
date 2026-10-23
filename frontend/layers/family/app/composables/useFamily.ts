import { NEUTRAL_INVITE_MESSAGE } from '../utils/familyView'
import type { FamilyOverview } from '../utils/familyView'

/** Grupo familiar: carga de `/family/me` y acciones. Cada acción recarga y avisa con un aviso legible. */
export function useFamily() {
  const api = useLeoAppApi()
  const toast = useToast()

  const overview = ref<FamilyOverview | null>(null)
  const loading = ref(true)
  const error = ref<string | null>(null)
  /** Clave de la acción en curso (p. ej. `share:<id>`), para deshabilitar su control. */
  const busy = ref<string | null>(null)

  async function load() {
    loading.value = true
    error.value = null
    try {
      overview.value = await api.get<FamilyOverview>('/family/me')
    } catch (err) {
      error.value = leoErrorMessage(err)
    } finally {
      loading.value = false
    }
  }

  /** Ejecuta una acción; devuelve `true` si salió bien. El error se muestra como aviso. */
  async function run(key: string, action: () => Promise<unknown>, success: string): Promise<boolean> {
    if (busy.value) return false
    busy.value = key
    try {
      await action()
      toast.success(success)
      await load()
      return true
    } catch (err) {
      toast.error(leoErrorMessage(err))
      await load() // el estado pudo cambiar (invitación vencida, ya en otro grupo…)
      return false
    } finally {
      busy.value = null
    }
  }

  /** Invitar: la respuesta es SIEMPRE el mensaje neutro (no revela si la persona existe). */
  async function invite(documentType: string, documentNumber: string) {
    const out = await api.post<{ message?: string }>('/family/invitations', { document_type: documentType, document_number: documentNumber })
    await load()
    return out?.message || NEUTRAL_INVITE_MESSAGE
  }

  const accept = (id: string) => run(`inv:${id}`, () => api.post(`/family/invitations/${id}/accept`), 'Te uniste al grupo familiar.')
  const reject = (id: string) => run(`inv:${id}`, () => api.post(`/family/invitations/${id}/reject`), 'Rechazaste la invitación.')
  const cancel = (id: string) => run(`inv:${id}`, () => api.post(`/family/invitations/${id}/cancel`), 'Cancelaste la invitación.')
  const setShare = (patientId: string, on: boolean, name: string) =>
    run(`share:${patientId}`,
      () => (on ? api.put(`/family/shares/${patientId}`) : api.delete(`/family/shares/${patientId}`)),
      on ? `Ahora compartes tus resultados con ${name}.` : `Dejaste de compartir tus resultados con ${name}.`)
  const leave = () => run('leave', () => api.post('/family/leave'), 'Saliste del grupo familiar.')
  const removeMember = (patientId: string, name: string) =>
    run(`member:${patientId}`, () => api.delete(`/family/members/${patientId}`), `Quitaste a ${name} del grupo.`)

  return { overview, loading, error, busy, load, invite, accept, reject, cancel, setShare, leave, removeMember }
}
