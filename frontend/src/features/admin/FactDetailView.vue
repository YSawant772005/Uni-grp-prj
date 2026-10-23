<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { admin } from '../../services/api/admin'
import { isApiError } from '../../services/api/client'
import { useAsync } from '../../composables/useAsync'
import { useUiStore } from '../../stores/ui'
import { formatDateTime, formatValue, humanize } from '../../utils/format'
import AsyncState from '../../components/AsyncState.vue'
import StatusBadge from '../../components/StatusBadge.vue'

const route = useRoute()
const router = useRouter()
const ui = useUiStore()

const factId = computed(() => String(route.params.factId))
const factState = useAsync(() => admin.fact(factId.value), { immediate: true })

const fact = computed(() => factState.data.value)
const activeVersions = computed(() => fact.value?.versions ?? [])

// ---------------------------------------------------------------- action panel

const pending = ref(false)
const actionError = ref('')
const reason = ref('')
const descriptionSummary = ref('')
const confirmAction = ref<'approve' | 'reject' | 'request_evidence' | null>(null)

/** Which version the actions target: the current one, or a chosen older one. */
const targetVersionId = ref<string | null>(null)
const selectedVersionId = computed(
  () => targetVersionId.value ?? fact.value?.current_version_id ?? null,
)

function startAction(action: 'approve' | 'reject' | 'request_evidence') {
  actionError.value = ''
  confirmAction.value = action
}

function cancelAction() {
  confirmAction.value = null
  actionError.value = ''
}

async function runAction() {
  if (!confirmAction.value || pending.value) return
  const action = confirmAction.value
  if (action === 'approve' && fact.value?.fact_key === 'program_description'
      && (!descriptionSummary.value.trim() || !reason.value.trim())) {
    actionError.value = 'Write an independent description summary and explain its official source evidence.'
    return
  }
  if ((action === 'reject' || action === 'request_evidence') && !reason.value.trim()) {
    actionError.value = 'A reason is required for this action.'
    return
  }
  pending.value = true
  actionError.value = ''
  try {
    if (action === 'approve') {
      await admin.approveFact(factId.value, {
        ...(selectedVersionId.value ? { version_id: selectedVersionId.value } : {}),
        ...(reason.value.trim() ? { reason: reason.value.trim() } : {}),
        ...(fact.value?.fact_key === 'program_description' ? { description_summary: descriptionSummary.value.trim() } : {}),
      })
      ui.push('Fact version verified. Program publication is reviewed separately.', 'success')
    } else if (action === 'reject') {
      await admin.rejectFact(factId.value, {
        ...(selectedVersionId.value ? { version_id: selectedVersionId.value } : {}),
        reason: reason.value.trim(),
      })
      ui.push('Version rejected.', 'success')
    } else {
      await admin.requestEvidence(factId.value, reason.value.trim())
      ui.push('Evidence requested - the fact stays out of published results until better sources arrive.', 'success')
    }
    confirmAction.value = null
    reason.value = ''
    descriptionSummary.value = ''
    targetVersionId.value = null
    await factState.run()
  } catch (err) {
    if (isApiError(err) && err.status === 401) {
      void router.push({ path: '/login', query: { redirect: route.fullPath } })
      return
    }
    actionError.value = isApiError(err) ? err.message : 'The action failed - please try again.'
  } finally {
    pending.value = false
  }
}

const actionButtons = computed(() => {
  const status = fact.value?.current_status ?? ''
  return {
    // approve is only meaningful on a non-verified current version
    canApprove: status !== 'verified',
    canReject: status !== 'rejected',
  }
})
</script>

<template>
  <AsyncState
    :loading="factState.loading.value"
    :error="factState.error.value"
    :empty="!fact"
    empty-title="Fact not found"
    empty-hint="It may have been removed, or the link is wrong."
    @retry="factState.run"
  >
    <template #empty-action>
      <RouterLink to="/admin/review" class="btn">Back to queue</RouterLink>
    </template>

    <div v-if="fact" class="stack">
      <div class="row-between">
        <div>
          <p class="small muted" style="margin: 0">
            <RouterLink to="/admin/review">Review queue</RouterLink> / fact
          </p>
          <h1 style="margin-bottom: 2px">{{ fact.entity_label ?? fact.entity_type }} · {{ fact.fact_key }}</h1>
          <p class="muted small" style="margin: 0">
            {{ humanize(fact.entity_type) }} · applicability: {{ fact.applicability_key || 'general' }}
          </p>
        </div>
        <StatusBadge :status="fact.current_status" />
      </div>

      <div class="grid-2">
        <!-- versions + evidence -->
        <div class="stack">
          <section v-if="fact.entity_context" class="card">
            <h3 style="margin-top: 0">{{ humanize(fact.entity_context.type) }} identity</h3>
            <p class="small" style="margin: 0">
              <strong>{{ fact.entity_context.name }}</strong>
              <span v-if="fact.entity_context.country_code" class="muted"> · {{ fact.entity_context.country_code }}</span>
              <span v-if="fact.entity_context.publication_status" class="muted"> · {{ fact.entity_context.publication_status }}</span>
            </p>
            <p v-if="fact.entity_context.type === 'university'" class="small" style="margin: 6px 0 0">
              <a v-if="fact.entity_context.official_website_url" :href="fact.entity_context.official_website_url" target="_blank" rel="noopener noreferrer">
                Official university website
              </a>
              <span v-else class="error">Official university website not established</span>
            </p>
            <template v-if="fact.entity_context.type === 'program'">
              <p class="small" style="margin: 6px 0 0">
                Institution:
                <a v-if="fact.entity_context.university?.official_website_url" :href="fact.entity_context.university.official_website_url" target="_blank" rel="noopener noreferrer">
                  {{ fact.entity_context.university.name }} official website
                </a>
                <span v-else>{{ fact.entity_context.university?.name ?? 'Institution unresolved' }}</span>
              </p>
              <p v-if="fact.entity_context.source_identifiers?.length" class="small muted" style="margin: 4px 0 0">
                <span v-for="(identity, index) in fact.entity_context.source_identifiers" :key="`${identity.source_key}-${identity.external_key}`">
                  {{ index ? ' · ' : '' }}{{ identity.source_key }}: {{ identity.external_key }} ({{ identity.claim_status }})
                </span>
              </p>
            </template>
            <template v-if="fact.entity_context.type === 'university' && fact.entity_context.external_identifiers">
              <p class="small muted" style="margin: 4px 0 0">
                Identifiers: {{ Object.entries(fact.entity_context.external_identifiers).map(([key, value]) => `${key}: ${value}`).join(' · ') || 'none recorded' }}
              </p>
            </template>
          </section>

          <section v-for="version in activeVersions" :key="version.id" class="card">
            <div class="row-between">
              <h3 style="margin: 0">Version {{ version.version_number }}</h3>
              <div class="row">
                <StatusBadge :status="version.status" />
                <span v-if="version.id === fact.current_version_id" class="badge badge-info">current</span>
              </div>
            </div>
            <p class="small muted" style="margin: 4px 0">
              {{ humanize(version.extraction_method) }}
              <template v-if="version.extraction_confidence !== null">
                · confidence {{ version.extraction_confidence }}</template
              ><template v-if="version.applicable_intake_year">
                · intake {{ version.applicable_intake_term ?? '' }} {{ version.applicable_intake_year }}</template
              >
              · created {{ formatDateTime(version.created_at) }}
            </p>
            <p class="card" style="margin: 8px 0; padding: 10px">
              <strong class="small">Value for review</strong><br />
              {{ version.display_value?.summary ?? formatValue(version.value) }}
            </p>
            <details>
              <summary class="small muted">Raw source value</summary>
              <pre class="json-block">{{ formatValue(version.value) }}</pre>
            </details>
            <p v-if="version.reviewed_at" class="small muted" style="margin: 0">
              Reviewed {{ formatDateTime(version.reviewed_at) }}
              <template v-if="version.review_reason"> - “{{ version.review_reason }}”</template>
            </p>

            <div v-if="version.evidence.length" style="margin-top: 8px">
              <h4 style="margin: 0 0 6px">Evidence ({{ version.evidence.length }})</h4>
              <ul class="timeline">
                <li v-for="evidence in version.evidence" :key="evidence.evidence_id">
                  <div class="row">
                    <StatusBadge :status="evidence.supports_or_conflicts" />
                    <a v-if="evidence.canonical_url" :href="evidence.canonical_url" target="_blank" rel="noopener noreferrer">
                      {{ evidence.source?.name ?? evidence.canonical_url }}
                    </a>
                    <span v-else class="small muted">{{ evidence.source?.name ?? 'unknown source' }}</span>
                  </div>
                  <p v-if="evidence.excerpt" class="small" style="margin: 2px 0">“{{ evidence.excerpt }}”</p>
                  <p v-if="evidence.locator" class="small muted" style="margin: 2px 0">Source locator: {{ evidence.locator }}</p>
                  <p class="small muted" style="margin: 0">
                    <template v-if="evidence.source">
                      tier {{ evidence.source.authority_tier }} · policy
                      {{ humanize(evidence.source.allowed_use_policy) }} ·
                    </template>
                    <template v-if="evidence.retrieved_at">retrieved {{ formatDateTime(evidence.retrieved_at) }} · </template>
                    <template v-if="evidence.fetch_status">fetch {{ evidence.fetch_status }}</template>
                    <template v-if="evidence.reviewer_note"> · note: “{{ evidence.reviewer_note }}”</template>
                  </p>
                </li>
              </ul>
            </div>
            <p v-else class="small muted" style="margin: 8px 0 0">
              No evidence attached - approving without evidence publishes an unsourced value; prefer
              requesting evidence instead.
            </p>
          </section>

          <!-- review history -->
          <section class="card">
            <h3>Review history</h3>
            <p v-if="fact.review_events.length === 0" class="muted small" style="margin: 0">
              No review actions yet.
            </p>
            <ul v-else class="timeline">
              <li v-for="event in fact.review_events" :key="event.id">
                <div class="row">
                  <strong class="small">{{ humanize(event.action) }}</strong>
                  <span class="small muted">{{ formatDateTime(event.created_at) }}</span>
                </div>
                <p v-if="event.reason" class="small" style="margin: 2px 0">“{{ event.reason }}”</p>
                <p class="small muted" style="margin: 0">reviewer {{ event.reviewer_user_id.slice(0, 8) }}…</p>
              </li>
            </ul>
          </section>
        </div>

        <!-- sticky action panel -->
        <section class="card" style="position: sticky; top: 72px; align-self: start">
          <h2>Review actions</h2>
          <p class="small muted" style="margin-top: 0">
            Target version:
            <select v-model="targetVersionId" style="width: auto; min-height: 32px" aria-label="Target version">
              <option :value="null">
                current (v{{ activeVersions.find((v) => v.id === fact?.current_version_id)?.version_number ?? '?' }})
              </option>
              <option v-for="version in activeVersions" :key="version.id" :value="version.id">
                v{{ version.version_number }} ({{ version.status }})
              </option>
            </select>
          </p>

          <div v-if="actionError" class="error-summary" role="alert">{{ actionError }}</div>

          <div v-if="fact?.fact_key === 'program_description'" class="field">
            <label for="description-summary">Independent programme summary</label>
            <textarea id="description-summary" v-model="descriptionSummary" maxlength="600" rows="5" />
            <p class="small muted">Use the attached official source passage as evidence. Write 40–600 characters in your own words (at most 90 words), and explain your review in the reason. Existing authored descriptions are preserved.</p>
          </div>

          <template v-if="!confirmAction">
            <div class="stack-sm">
              <button
                v-if="actionButtons.canApprove"
                class="btn btn-primary"
                type="button"
                :disabled="pending"
                @click="startAction('approve')"
              >
                Verify fact version
              </button>
              <button
                v-if="actionButtons.canReject"
                class="btn btn-danger"
                type="button"
                :disabled="pending"
                @click="startAction('reject')"
              >
                Reject version
              </button>
              <button class="btn" type="button" :disabled="pending" @click="startAction('request_evidence')">
                Request better evidence
              </button>
            </div>
            <p class="small muted" style="margin: 10px 0 0">
              Verification updates supported structured catalogue fields. University approval and
              programme publication require their own review. Request evidence keeps this fact queued.
            </p>
          </template>

          <template v-else>
            <h3>
              {{ confirmAction === 'approve' ? 'Confirm approval' : confirmAction === 'reject' ? 'Confirm rejection' : 'Request evidence' }}
            </h3>
            <p class="small" style="margin-top: 0">
              <template v-if="confirmAction === 'approve' && fact?.fact_key === 'program_description'">
                Your summary is saved in a new verified version with the selected version's source
                evidence. This does not publish a programme. The decision is recorded in the audit log.
              </template>
              <template v-else-if="confirmAction === 'approve'">
                The selected version becomes the published value for this fact. This is recorded in
                the audit log under your account.
              </template>
              <template v-else-if="confirmAction === 'reject'">
                The selected version will not be published. This is recorded in the audit log.
              </template>
              <template v-else>
                The fact stays in the queue and ingestion is asked for stronger evidence.
              </template>
            </p>
            <div class="field">
              <label :for="`reason-${confirmAction}`">
                Reason <span v-if="confirmAction !== 'approve' || fact?.fact_key === 'program_description'" class="muted">(required)</span>
                <span v-else class="muted">(optional)</span>
              </label>
              <textarea
                :id="`reason-${confirmAction}`"
                v-model="reason"
                rows="3"
                placeholder="e.g. Official fee page confirms 24,000 EUR/year for 2025 intake"
              />
            </div>
            <div class="row">
              <button class="btn btn-primary" type="button" :disabled="pending" @click="runAction">
                {{ pending ? 'Applying…' : 'Confirm' }}
              </button>
              <button class="btn btn-quiet" type="button" :disabled="pending" @click="cancelAction">Cancel</button>
            </div>
          </template>
        </section>
      </div>
    </div>
  </AsyncState>
</template>
