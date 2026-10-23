<template>
  <div class="mx-auto max-w-4xl space-y-5 px-4 py-6">
    <UiPageHeader title="Mi familia" description="Comparte tus resultados con las personas que tú elijas, y consulta los que ellas compartan contigo." />

    <UiAlert variant="info" title="Qué se comparte">
      <ul class="list-disc space-y-1 pl-5">
        <li>Por defecto <strong>no se comparte nada</strong>, aunque estés en un grupo familiar.</li>
        <li>Tú decides, persona por persona, con quién compartes tus resultados. Puedes dejar de compartir cuando quieras.</li>
        <li>Quien recibe lo que compartes puede ver tus resultados y descargarlos. No ve nada más de tu cuenta.</li>
        <li>Solo ves los resultados de otra persona si ella decidió compartirlos contigo.</li>
      </ul>
    </UiAlert>

    <div v-if="f.error.value" class="space-y-3">
      <UiAlert variant="danger" title="No pudimos cargar tu grupo familiar" :message="f.error.value" />
      <UiButton variant="secondary" @click="f.load()">Intentar de nuevo</UiButton>
    </div>

    <div v-else-if="f.loading.value && !o" class="flex items-center justify-center gap-2 py-16 text-text-muted" role="status">
      <UiSpinner size="md" color="primary" />
      <span>Cargando tu grupo familiar…</span>
    </div>

    <template v-else-if="o">
      <!-- Invitaciones recibidas -->
      <UiCard v-if="o.invitations_received.length" title="Invitaciones que recibiste" description="Alguien te invitó a su grupo familiar. Unirte no comparte nada por sí solo.">
        <ul class="divide-y divide-border">
          <li v-for="inv in o.invitations_received" :key="inv.id" class="flex flex-col gap-3 py-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p class="font-medium">{{ inv.inviter_display_name }}</p>
              <p class="text-xs text-text-muted">{{ expiryText(inv.expires_at) }}</p>
            </div>
            <LeoCan tag="acuarius.family.respond">
              <div class="flex gap-2">
                <UiButton class="flex-1 sm:flex-none" :loading="f.busy.value === `inv:${inv.id}`" :disabled="!!f.busy.value" @click="f.accept(inv.id)">Aceptar</UiButton>
                <UiButton class="flex-1 sm:flex-none" variant="secondary" :disabled="!!f.busy.value" @click="f.reject(inv.id)">Rechazar</UiButton>
              </div>
            </LeoCan>
          </li>
        </ul>
      </UiCard>

      <!-- Mi grupo -->
      <UiCard as="section" title="Mi grupo familiar" aria-label="Mi grupo familiar">
        <div v-if="!o.group" class="space-y-1 py-2">
          <p class="font-medium">Todavía no tienes un grupo familiar.</p>
          <p class="text-sm text-text-muted">Invita a un familiar con su documento. Cuando acepte, ustedes quedan en el mismo grupo.</p>
        </div>

        <template v-else>
          <ul class="divide-y divide-border">
            <li v-for="member in o.group.members" :key="member.patient_id" class="flex flex-col gap-3 py-3 sm:flex-row sm:items-center sm:justify-between">
              <div class="flex flex-wrap items-center gap-2">
                <span class="font-medium">{{ member.is_me ? 'Tú' : member.display_name }}</span>
                <span v-if="member.is_me" class="text-sm text-text-muted">({{ member.display_name }})</span>
                <UiStatusBadge v-if="member.is_creator" variant="primary" label="Creó el grupo" />
              </div>

              <div v-if="!member.is_me" class="flex flex-wrap items-center gap-3">
                <LeoCan tag="acuarius.family.manage">
                  <UiCheckbox
                    :model-value="isSharingWith(o, member.patient_id)"
                    :label="`Compartir mis resultados con ${member.display_name}`"
                    :disabled="!!f.busy.value"
                    @update:model-value="(on: boolean) => f.setShare(member.patient_id, on, member.display_name)"
                  />
                  <UiButton
                    v-if="canRemove(o.group, member)"
                    variant="danger-ghost"
                    size="sm"
                    :aria-label="`Quitar a ${member.display_name} del grupo`"
                    :disabled="!!f.busy.value"
                    @click="toRemove = member"
                  >Quitar</UiButton>
                </LeoCan>
              </div>
            </li>
          </ul>

          <LeoCan tag="acuarius.family.manage">
            <div class="mt-4 border-t border-border pt-4">
              <UiButton variant="danger-ghost" :disabled="!!f.busy.value" @click="leaveOpen = true">Salir del grupo</UiButton>
            </div>
          </LeoCan>
        </template>
      </UiCard>

      <!-- Resultados que comparten conmigo -->
      <UiCard v-if="o.shares_received.length" title="Comparten sus resultados contigo">
        <ul class="space-y-1 text-sm">
          <li v-for="s in o.shares_received" :key="s.patient_id">{{ s.display_name }}</li>
        </ul>
        <template #footer>
          <UiButton variant="secondary" size="sm" to="/resultados">Ver sus resultados</UiButton>
        </template>
      </UiCard>

      <!-- Invitar -->
      <LeoCan tag="acuarius.family.invite">
        <UiCard as="section" title="Invitar a un familiar" description="Escribe el documento de la persona. Por su privacidad, no te diremos si está registrada o no.">
          <form class="space-y-4" novalidate @submit.prevent="onInvite">
            <UiAlert v-if="inviteNotice" variant="info" :message="inviteNotice" data-testid="invite-notice" />
            <UiAlert v-if="invite.formError.value" variant="danger" :message="invite.formError.value" />
            <div class="grid gap-4 sm:grid-cols-2">
              <UiFormField name="document_type" label="Tipo de documento" required>
                <UiSelect :options="INVITE_DOCUMENT_TYPES" placeholder="Elige una opción" />
              </UiFormField>
              <UiFormField name="document_number" label="Número de documento" required>
                <UiTextInput autocomplete="off" />
              </UiFormField>
            </div>
            <UiButton type="submit" :loading="invite.isSubmitting.value" class="w-full sm:w-auto">Enviar invitación</UiButton>
          </form>
        </UiCard>
      </LeoCan>

      <!-- Invitaciones enviadas -->
      <UiCard v-if="o.invitations_sent.length" title="Invitaciones que enviaste">
        <ul class="divide-y divide-border">
          <li v-for="inv in o.invitations_sent" :key="inv.id" class="flex flex-col gap-3 py-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p class="font-medium">{{ inv.invitee_display_name }}</p>
              <p class="text-xs text-text-muted">Esperando respuesta · {{ expiryText(inv.expires_at) }}</p>
            </div>
            <LeoCan tag="acuarius.family.invite">
              <UiButton variant="secondary" size="sm" :loading="f.busy.value === `inv:${inv.id}`" :disabled="!!f.busy.value" :aria-label="`Cancelar la invitación a ${inv.invitee_display_name}`" @click="f.cancel(inv.id)">
                Cancelar invitación
              </UiButton>
            </LeoCan>
          </li>
        </ul>
      </UiCard>
    </template>

    <UiConfirmModal
      v-model:open="leaveOpen"
      title="¿Salir del grupo familiar?"
      message="Dejarás de compartir tus resultados con el grupo y ya no verás los que compartieron contigo. Para volver, alguien tendrá que invitarte de nuevo."
      confirm-label="Sí, salir"
      :loading="f.busy.value === 'leave'"
      @confirm="onLeave"
    />
    <UiConfirmModal
      :open="!!toRemove"
      :title="`¿Quitar a ${toRemove?.display_name ?? ''} del grupo?`"
      message="Dejará de ver tus resultados y tú los suyos. Esta acción no se puede deshacer, pero podrás invitarla de nuevo."
      confirm-label="Sí, quitar"
      :loading="!!toRemove && f.busy.value === `member:${toRemove.patient_id}`"
      @update:open="(v: boolean) => { if (!v) toRemove = null }"
      @confirm="onRemove"
    />
  </div>
</template>

<script setup lang="ts">
import { INVITE_DOCUMENT_TYPES, canRemove, expiryText, inviteSchema, isSharingWith } from '../utils/familyView'
import type { Member } from '../utils/familyView'

definePageMeta({ leo: { tag: 'acuarius.family.view' } })
useHead({ title: 'Mi familia' })

const f = useFamily()
const o = computed(() => f.overview.value)
const leaveOpen = ref(false)
const toRemove = ref<Member | null>(null)
const inviteNotice = ref<string | null>(null)

const invite = useZodForm(inviteSchema, { initialValues: { document_type: '', document_number: '' } })
const onInvite = invite.submit(async (values) => {
  inviteNotice.value = null
  inviteNotice.value = await f.invite(values.document_type, values.document_number)
  invite.reset()
})

async function onLeave() {
  if (await f.leave()) leaveOpen.value = false
}
async function onRemove() {
  if (!toRemove.value) return
  if (await f.removeMember(toRemove.value.patient_id, toRemove.value.display_name)) toRemove.value = null
}

f.load()
</script>
