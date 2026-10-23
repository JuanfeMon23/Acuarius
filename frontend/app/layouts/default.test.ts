import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, it } from 'vitest'
import { enableAutoUnmount } from '@vue/test-utils'
import { signInWith } from '#leo-client/testing/session'
import { TAGS } from '../utils/tags'
import DefaultLayout from './default.vue'

enableAutoUnmount(afterEach)

async function menuLabels(tags: string[]) {
  signInWith(tags)
  const wrapper = await mountSuspended(DefaultLayout)
  return wrapper.findAll('nav a').map((a) => a.text()).filter((t) => ['Mis resultados', 'Mi familia'].includes(t))
}

describe('menú lateral por permiso', () => {
  it('con ambos permisos aparecen las dos pantallas', async () => {
    expect(await menuLabels([TAGS.results.view, TAGS.family.view])).toEqual(['Mis resultados', 'Mi familia'])
  })
  it('solo resultados', async () => {
    expect(await menuLabels([TAGS.results.view])).toEqual(['Mis resultados'])
  })
  it('solo familia', async () => {
    expect(await menuLabels([TAGS.family.view])).toEqual(['Mi familia'])
  })
})
