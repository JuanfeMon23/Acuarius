import { describe, expect, it } from 'vitest'

describe('configuración de leo-client en Acuarius', () => {
  it('usa transporte bff, /auth y el callback propio', () => {
    const leo = useRuntimeConfig().public.leo
    expect(leo.transport).toBe('bff')
    expect(leo.authPath).toBe('/auth')
    expect(leo.callbackPath).toBe('/leo/callback')
    expect(leo.appSlug).toBe('acuarius')
  })

  it('la API cuelga de la base de Leo (una sola URL de backend)', () => {
    const { apiBase, leo } = useRuntimeConfig().public
    expect(apiBase.startsWith(leo.apiBase)).toBe(true)
  })

  it('registra /leo/callback, /activar pública y las demás con tag', () => {
    const meta = (p: string) => (useRouter().resolve(p).meta as { leo?: { public?: boolean, tag?: string } }).leo
    expect(useRouter().resolve('/leo/callback').matched.length).toBeGreaterThan(0)
    expect(meta('/activar')?.public).toBe(true)
    expect(meta('/resultados')?.tag).toBe('acuarius.results.view')
    expect(meta('/familia')?.tag).toBe('acuarius.family.view')
  })
})
