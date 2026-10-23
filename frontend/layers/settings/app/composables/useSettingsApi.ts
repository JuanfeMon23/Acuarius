import type { SettingHistoryPage, SettingItem, SettingsListResponse, SettingUpdateBody } from '#andromeda/types/settings'

/**
 * Llamadas a `/settings`: única puerta del módulo a la API. Lanzan
 * `LeoApiError` (con `code` y `details`, que `useSettingsAdmin` interpreta).
 */
export function useSettingsApi() {
  const api = useLeoAppApi()
  const key = (k: string) => `/settings/${encodeURIComponent(k)}`

  return {
    list: () => api.get<SettingsListResponse>('/settings'),
    history: (k: string, page: number) => api.get<SettingHistoryPage>(`${key(k)}/history`, { query: { page } }),
    update: (k: string, body: SettingUpdateBody) => api.put<SettingItem>(key(k), body)
  }
}
