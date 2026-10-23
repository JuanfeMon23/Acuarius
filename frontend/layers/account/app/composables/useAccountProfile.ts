import type { AccountProfile, ProfileUpdatePayload } from '../utils/profileSchema'

/**
 * Perfil propio del paciente: carga `GET /account/profile` y `/account/me`
 * (nombre a mostrar), guarda con `PATCH /account/profile` y cambia la
 * contraseña con `POST /account/password`. Lanza `LeoApiError`; los errores de
 * carga quedan como mensaje legible. Las contraseñas solo viajan en la petición.
 */
export function useAccountProfile() {
  const api = useLeoAppApi()
  const session = useLeoSession()

  const profile = ref<AccountProfile | null>(null)
  const displayName = ref<string | null>(null)
  const loading = ref(true)
  const error = ref<string | null>(null)

  async function refreshIdentity() {
    const me = await api.get<{ display_name?: string }>('/account/me')
    displayName.value = me?.display_name ?? null
    // La barra superior lee la sesión de Leo: se actualiza con el nombre nuevo.
    await session.ensure(true)
  }

  async function load() {
    loading.value = true
    error.value = null
    try {
      const [p] = await Promise.all([api.get<AccountProfile>('/account/profile'), refreshIdentity().catch(() => undefined)])
      profile.value = p
    } catch (err) {
      error.value = leoErrorMessage(err)
    } finally {
      loading.value = false
    }
  }

  /** Guarda lo cambiado y recarga el perfil y el nombre a mostrar. Lanza si el backend rechaza. */
  async function save(body: ProfileUpdatePayload) {
    await api.patch('/account/profile', body)
    profile.value = await api.get<AccountProfile>('/account/profile')
    await refreshIdentity().catch(() => undefined)
  }

  async function changePassword(body: { current_password: string, new_password: string }) {
    await api.post<void>('/account/password', body)
  }

  return { profile, displayName, loading, error, load, save, changePassword }
}
