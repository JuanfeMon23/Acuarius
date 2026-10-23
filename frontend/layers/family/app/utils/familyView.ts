import { z } from 'zod'

export interface Member { patient_id: string, display_name: string, is_me: boolean, is_creator: boolean, joined_at: string }
export interface Group { id: string, created_by_me: boolean, members: Member[] }
export interface InvitationReceived { id: string, inviter_display_name: string, created_at: string, expires_at: string }
export interface InvitationSent { id: string, invitee_display_name: string, created_at: string, expires_at: string }
export interface Share { patient_id: string, display_name: string, granted_at: string }
export interface FamilyOverview {
  display_name: string
  group: Group | null
  invitations_received: InvitationReceived[]
  invitations_sent: InvitationSent[]
  shares_given: Share[]
  shares_received: Share[]
}

/** Mensaje neutro de invitación: igual exista o no la persona (no permite averiguar quién está registrado). */
export const NEUTRAL_INVITE_MESSAGE = 'Si la persona está registrada, recibirá la invitación.'

export const INVITE_DOCUMENT_TYPES = [
  { value: 'CC', label: 'CC · Cédula de ciudadanía' },
  { value: 'TI', label: 'TI · Tarjeta de identidad' },
  { value: 'CE', label: 'CE · Cédula de extranjería' },
  { value: 'PA', label: 'PA · Pasaporte' },
  { value: 'RC', label: 'RC · Registro civil' },
  { value: 'PEP', label: 'PEP · Permiso especial de permanencia' },
  { value: 'PPT', label: 'PPT · Permiso por protección temporal' }
]

export const inviteSchema = z.object({
  document_type: z.enum(INVITE_DOCUMENT_TYPES.map((d) => d.value) as [string, ...string[]], { errorMap: () => ({ message: 'Elige el tipo de documento.' }) }),
  document_number: z.string({ required_error: 'Escribe el número de documento.' }).trim().min(1, 'Escribe el número de documento.')
    .regex(/^[A-Za-z0-9]{3,20}$/, 'Usa solo letras y números, sin puntos ni espacios.')
})

/** ¿Estoy compartiendo mis resultados con este miembro? */
export function isSharingWith(overview: FamilyOverview, patientId: string): boolean {
  return overview.shares_given.some((s) => s.patient_id === patientId)
}

/** Texto de "vence": "Vence el 3 nov" o "Venció" si ya pasó. */
export function expiryText(expiresAt: string, now: Date = new Date()): string {
  const date = new Date(expiresAt)
  if (Number.isNaN(date.getTime())) return ''
  if (date.getTime() <= now.getTime()) return 'Venció'
  return `Vence el ${new Intl.DateTimeFormat('es-CO', { day: 'numeric', month: 'short' }).format(date)}`
}

/** Miembros con los que se puede compartir (todos menos yo). */
export const otherMembers = (group: Group | null): Member[] => group?.members.filter((m) => !m.is_me) ?? []

/** El creador puede quitar a los demás miembros. */
export const canRemove = (group: Group, member: Member): boolean => group.created_by_me && !member.is_me
