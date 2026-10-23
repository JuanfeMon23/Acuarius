import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount } from '@vue/test-utils'
import { LeoApiError } from '#leo-client/lib/errors'
import ProfilePasswordCard from './ProfilePasswordCard.vue'

enableAutoUnmount(afterEach)

// vee-validate valida de forma asíncrona: se espera a que termine.
const settle = () => new Promise<void>(r => setTimeout(r, 30))

async function mountCard(change = vi.fn().mockResolvedValue(undefined)) {
  const w = await mountSuspended(ProfilePasswordCard, { props: { change } })
  return { w, change }
}
type W = Awaited<ReturnType<typeof mountCard>>['w']
const inputs = (w: W) => ({
  current: w.get('input[autocomplete="current-password"]'),
  next: w.findAll('input[autocomplete="new-password"]')[0]!,
  confirm: w.findAll('input[autocomplete="new-password"]')[1]!
})
async function fill(w: W, current = 'Vieja#Clave1', next = 'Nueva#Clave12', confirm = next) {
  const i = inputs(w)
  await i.current.setValue(current)
  await i.next.setValue(next)
  await i.confirm.setValue(confirm)
  await w.get('form').trigger('submit')
  await settle()
}

describe('ProfilePasswordCard', () => {
  it('muestra los requisitos en vivo', async () => {
    const { w } = await mountCard()
    expect(w.get('[data-testid="password-checks"]').text()).toContain('(pendiente)')
    await inputs(w).next.setValue('Nueva#Clave12')
    await settle()
    expect(w.get('[data-testid="password-checks"]').text()).not.toContain('(pendiente)')
  })

  it('contraseña débil o sin confirmar no se envía', async () => {
    const { w, change } = await mountCard()
    await fill(w, 'Vieja#Clave1', 'corta', 'otra')
    expect(change).not.toHaveBeenCalled()
    expect(w.text()).toContain('aún no cumple todos los requisitos')
  })

  it('éxito: envía, limpia los campos y avisa del cierre de otras sesiones', async () => {
    const { w, change } = await mountCard()
    await fill(w)
    expect(change).toHaveBeenCalledWith({ current_password: 'Vieja#Clave1', new_password: 'Nueva#Clave12' })
    const i = inputs(w)
    for (const el of [i.current, i.next, i.confirm]) expect((el.element as HTMLInputElement).value).toBe('')
    expect(w.get('[data-testid="password-success"]').text()).toContain('otras sesiones')
  })

  it('403 invalid_credentials marca la contraseña actual y la vacía', async () => {
    const { w } = await mountCard(vi.fn().mockRejectedValue(new LeoApiError(403, 'invalid_credentials', 'x')))
    await fill(w)
    expect(w.text()).toContain('La contraseña actual no es correcta.')
    expect((inputs(w).current.element as HTMLInputElement).value).toBe('')
    expect(w.find('[data-testid="password-success"]').exists()).toBe(false)
  })

  it('429 bloquea el botón con cuenta regresiva', async () => {
    const { w } = await mountCard(vi.fn().mockRejectedValue(new LeoApiError(429, 'rate_limited', 'x', null, 30)))
    await fill(w)
    expect(w.get('[data-testid="password-save"]').attributes('disabled')).toBeDefined()
    expect(w.get('[data-testid="password-wait"]').text()).toContain('30')
  })
})
