import { useSettingsAdmin } from '#andromeda/composables/useSettingsAdmin'
import { TAGS } from '../../../../app/utils/tags'

/**
 * Estado de la pantalla «Ajustes del sistema»: conecta `useSettingsAdmin` de
 * Andromeda con la API de Acuarius, los permisos de la sesión, los avisos y los
 * mensajes de error legibles. Editar exige `acuarius.settings.edit`; los
 * ajustes marcados como de seguridad, además `acuarius.settings.edit-security`.
 */
export function useSettingsScreen() {
  const api = useSettingsApi()
  const toast = useToast()
  const canEdit = useCan(TAGS.settings.edit)
  const canEditSecurity = useCan(TAGS.settings.editSecurity)

  return useSettingsAdmin({
    list: api.list,
    history: api.history,
    update: api.update,
    canEdit,
    canEditSecurity,
    mapError: leoErrorMessage,
    notify: (kind, message) => toast[kind](message)
  })
}
