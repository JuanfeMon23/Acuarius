import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount } from '@vue/test-utils'
import { LeoApiError } from '#leo-client/lib/errors'
import ProfilePersonalCard from './ProfilePersonalCard.vue'

enableAutoUnmount(afterEach)

// vee-validate valida de forma asíncrona: se espera a que termine.
const settle = () => new Promise<void>(r => setTimeout(r, 30))

const profile = { first_name: 'Ana', last_name: 'Pérez', email: 'ana@x.co', username: 'ana' }

async function mountCard(save = vi.fn().mockResolvedValue(undefined)) {
  const w = await mountSuspended(ProfilePersonalCard, { props: { profile, save } })
  return { w, save }
}
const submit = async (w: Awaited<ReturnType<typeof mountCard>>['w']) => {
  await w.get('form').trigger('submit')
  await settle()
}

describe('ProfilePersonalCard', () => {
  it('sin cambios el botón está deshabilitado y no hay contraseña actual', async () => {
    const { w } = await mountCard()
    expect(w.get('[data-testid="profile-save"]').attributes('disabled')).toBeDefined()
    expect(w.find('input[autocomplete="current-password"]').exists()).toBe(false)
    expect(w.get('[data-testid="profile-username"]').text()).toBe('ana')
  })

  it('cambiar el correo muestra y exige la contraseña actual', async () => {
    const { w, save } = await mountCard()
    await w.get('input[autocomplete="email"]').setValue('nuevo@x.co')
    await settle()
    expect(w.find('input[autocomplete="current-password"]').exists()).toBe(true)
    await submit(w)
    expect(save).not.toHaveBeenCalled()
    expect(w.text()).toContain('Ingresa tu contraseña actual para cambiar el correo.')
  })

  it('cambiar solo el nombre envía solo ese campo, sin contraseña', async () => {
    const { w, save } = await mountCard()
    await w.get('input[autocomplete="given-name"]').setValue('Ana María')
    await submit(w)
    expect(save).toHaveBeenCalledWith({ first_name: 'Ana María' })
    expect(w.find('[data-testid="profile-sessions-notice"]').exists()).toBe(false)
  })

  it('con el correo cambiado envía la contraseña y avisa del cierre de otras sesiones', async () => {
    const { w, save } = await mountCard()
    await w.get('input[autocomplete="email"]').setValue('nuevo@x.co')
    await settle()
    await w.get('input[autocomplete="current-password"]').setValue('Clave#Actual1')
    await submit(w)
    expect(save).toHaveBeenCalledWith({ email: 'nuevo@x.co', current_password: 'Clave#Actual1' })
    expect(w.get('[data-testid="profile-sessions-notice"]').text()).toContain('otras sesiones')
  })

  it('un 429 deshabilita el botón con cuenta regresiva', async () => {
    const save = vi.fn().mockRejectedValue(new LeoApiError(429, 'rate_limited', 'x', null, 45))
    const { w } = await mountCard(save)
    await w.get('input[autocomplete="given-name"]').setValue('Otro')
    await submit(w)
    expect(w.get('[data-testid="profile-save"]').attributes('disabled')).toBeDefined()
    expect(w.get('[data-testid="profile-wait"]').text()).toContain('45')
    expect(w.get('[data-testid="profile-error"]').text()).toContain('demasiados intentos')
  })

  it('contraseña actual incorrecta: error en su campo y el campo queda vacío', async () => {
    const save = vi.fn().mockRejectedValue(new LeoApiError(403, 'invalid_current_password', 'x'))
    const { w } = await mountCard(save)
    await w.get('input[autocomplete="email"]').setValue('nuevo@x.co')
    await settle()
    const pwd = w.get('input[autocomplete="current-password"]')
    await pwd.setValue('mal')
    await submit(w)
    expect(w.text()).toContain('La contraseña actual no es correcta.')
    expect((w.get('input[autocomplete="current-password"]').element as HTMLInputElement).value).toBe('')
  })
})
