import { describe, expect, it } from 'vitest'
import { canRemove, expiryText, inviteSchema, isSharingWith, otherMembers } from './familyView'
import type { FamilyOverview, Group, Member } from './familyView'

const m = (id: string, is_me = false, is_creator = false): Member => ({ patient_id: id, display_name: id, is_me, is_creator, joined_at: '2026-10-01T00:00:00Z' })
const group = (created_by_me: boolean): Group => ({ id: 'g', created_by_me, members: [m('me', true, created_by_me), m('a'), m('b')] })

describe('familyView', () => {
  it('otros miembros excluyen a la persona', () => {
    expect(otherMembers(group(true)).map((x) => x.patient_id)).toEqual(['a', 'b'])
    expect(otherMembers(null)).toEqual([])
  })
  it('solo el creador quita, y nunca a sí mismo', () => {
    expect(canRemove(group(true), m('a'))).toBe(true)
    expect(canRemove(group(true), m('me', true))).toBe(false)
    expect(canRemove(group(false), m('a'))).toBe(false)
  })
  it('compartiendo con', () => {
    const o = { shares_given: [{ patient_id: 'a', display_name: 'A', granted_at: '' }] } as FamilyOverview
    expect(isSharingWith(o, 'a')).toBe(true)
    expect(isSharingWith(o, 'b')).toBe(false)
  })
  it('vencimiento', () => {
    const now = new Date('2026-10-22T12:00:00Z')
    expect(expiryText('2026-10-20T00:00:00Z', now)).toBe('Venció')
    expect(expiryText('2026-11-03T12:00:00Z', now)).toMatch(/^Vence el 3 /)
    expect(expiryText('basura', now)).toBe('')
  })
  it('valida la invitación', () => {
    expect(inviteSchema.safeParse({ document_type: 'CC', document_number: '123456' }).success).toBe(true)
    expect(inviteSchema.safeParse({ document_type: '', document_number: '123456' }).success).toBe(false)
    expect(inviteSchema.safeParse({ document_type: 'CC', document_number: '12 34' }).success).toBe(false)
  })
})
