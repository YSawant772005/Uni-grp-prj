<script setup lang="ts">
import { reactive, watch } from 'vue'
import { admin } from '../../services/api/admin'
import { useAsync } from '../../composables/useAsync'
import { formatDateTime, humanize } from '../../utils/format'
import AsyncState from '../../components/AsyncState.vue'
import { isSubstantivePublicationReason } from '../../utils/publicationReason'

const status = reactive({ value: 'candidate' })
const queue = useAsync(() => admin.programPublicationReviews({ status: status.value, page_size: 100 }), { immediate: true })
const reasons = reactive<Record<string, string>>({})
const busy = reactive<Record<string, boolean>>({})
const errors = reactive<Record<string, string>>({})

watch(() => status.value, () => void queue.run())

async function decide(programId: string, action: 'publish' | 'unpublish') {
  const reason = (reasons[programId] ?? '').trim()
  if (!isSubstantivePublicationReason(reason)) {
    errors[programId] = 'Explain the source or evidence reviewed and why it supports this decision.'
    return
  }
  busy[programId] = true
  errors[programId] = ''
  try {
    if (action === 'publish') await admin.publishProgram(programId, reason)
    else await admin.unpublishProgram(programId, reason)
    await queue.run()
  } catch (error) {
    errors[programId] = error instanceof Error ? error.message : 'Unable to save the publication decision.'
  } finally {
    busy[programId] = false
  }
}
</script>

<template>
  <div class="stack">
    <div>
      <h1>Program publication review</h1>
      <p class="muted small" style="margin: 0">
        Review the program identity and source chain before publishing. Publication makes the program discoverable;
        it does not verify its admission, tuition, deadline, or other facts. Unknown facts remain unknown.
      </p>
    </div>
    <section class="card field" style="max-width: 320px">
      <label for="publication-status">Programs</label>
      <select id="publication-status" v-model="status.value">
        <option value="candidate">Candidates</option>
        <option value="published">Published</option>
        <option value="hidden">Unpublished / hidden</option>
      </select>
    </section>
    <AsyncState :loading="queue.loading.value" :error="queue.error.value" :empty="!queue.data.value?.items.length"
      empty-title="No programs in this state" empty-hint="Candidate programs appear after their source identity is resolved and persisted."
      @retry="queue.run">
      <section v-for="item in queue.data.value?.items" :key="item.id" class="card stack">
        <div class="row-between">
          <div>
            <h2 style="margin: 0">{{ item.name }}</h2>
            <p class="small muted" style="margin: 4px 0 0">{{ humanize(item.degree_level) }} · {{ item.country_code }} · {{ item.university?.name ?? 'Institution missing' }}</p>
          </div>
          <span class="badge">{{ item.publication_status }}</span>
        </div>
        <p v-if="item.university?.is_demo" class="error">This program is linked to a synthetic demo institution and cannot be published.</p>
        <p v-if="item.university?.official_website_url" class="small">
          <a :href="item.university.official_website_url" target="_blank" rel="noopener noreferrer">Official university website</a>
          <span class="muted"> · website evidence {{ item.university.website_evidence_status }}</span>
        </p>
        <p v-else class="small error">Official university website not established.</p>
        <p v-if="item.program_page_evidence.status === 'verified' && item.program_page_evidence.url" class="small">
          <a :href="item.program_page_evidence.url" target="_blank" rel="noopener noreferrer">Verified official program page</a>
        </p>
        <div v-else class="small error">
          <span v-if="item.official_program_url_classification === 'general_catalogue'">Recorded URL is a general university catalogue, not an individual course page.</span>
          <span v-else-if="item.official_program_url_classification === 'dataset_record'">Recorded URL identifies a dataset record, not a university course page.</span>
          <span v-else>Official university program page not verified.</span>
          <a v-if="item.official_program_url" :href="item.official_program_url" target="_blank" rel="noopener noreferrer">(open recorded source reference)</a>
          <span v-if="item.program_page_evidence.reason"> · {{ item.program_page_evidence.reason }}</span>
        </div>
        <p v-if="item.registry_page_evidence?.url" class="small">
          <a :href="item.registry_page_evidence.url" target="_blank" rel="noopener noreferrer">Verified government programme record</a> · {{ item.registry_page_evidence.reason }}
        </p>
        <details v-if="item.university?.identifier_claims.length || item.university?.website_evidence.length">
          <summary class="small">Institution identity and website evidence</summary>
          <ul class="small">
            <li v-for="claim in item.university?.identifier_claims" :key="`${claim.namespace}-${claim.value}-${claim.scope}`">
              {{ claim.namespace }}: {{ claim.value }} · {{ claim.scope }} · {{ claim.claim_status }} · {{ claim.source_key }}
            </li>
            <li v-for="(proof, index) in item.university?.website_evidence" :key="`website-${index}`">
              <a :href="proof.url" target="_blank" rel="noopener noreferrer">{{ proof.title ?? 'Website evidence source' }}</a>
              · {{ formatDateTime(proof.retrieved_at) }} · {{ proof.status }}
              <span v-if="proof.locator"> · {{ proof.locator }}</span>
              <span v-if="proof.excerpt"> · “{{ proof.excerpt }}”</span>
            </li>
          </ul>
        </details>
        <p v-if="item.academic_field" class="small muted">Academic field: {{ item.academic_field.display_name }}</p>
        <p v-else class="small error">Academic field not mapped.</p>
        <div>
          <strong class="small">Source identity and evidence</strong>
          <ul class="small">
            <li v-for="identity in item.source_identities" :key="`${identity.source_key}:${identity.external_key}`">
              {{ identity.source?.name ?? identity.source_key }} · {{ identity.external_key }} · {{ identity.claim_status }}
              <template v-if="identity.document"> · <a :href="identity.document.url" target="_blank" rel="noopener noreferrer">{{ identity.document.title ?? 'Source document' }}</a> · retrieved {{ formatDateTime(identity.document.retrieved_at) }} · HTTP {{ identity.document.http_status ?? 'unknown' }}</template>
              <template v-if="identity.source"> · use: {{ identity.source.allowed_use_policy }}</template>
            </li>
          </ul>
          <p v-if="!item.source_identities.length" class="small error">No source identity evidence is attached.</p>
        </div>
        <p class="small muted">{{ item.fact_count }} program fact record(s). Program publication does not change their review state.</p>
        <details v-if="item.program_facts.length">
          <summary class="small">Program facts and evidence</summary>
          <ul class="timeline">
            <li v-for="(fact, index) in item.program_facts" :key="`${fact.fact_key}-${fact.applicability_key}-${index}`">
              <div class="row"><strong>{{ humanize(fact.fact_key) }}</strong><span class="badge">{{ fact.status }}</span></div>
              <p class="small" style="margin: 2px 0">{{ fact.display_value.summary }}</p>
              <p v-if="fact.applicability_key || fact.applicable_intake_year || fact.effective_from" class="small muted" style="margin: 2px 0">
                Applies: {{ fact.applicability_key || 'general' }}
                <template v-if="fact.applicable_intake_term || fact.applicable_intake_year"> · intake {{ fact.applicable_intake_term ?? '' }} {{ fact.applicable_intake_year ?? '' }}</template>
                <template v-if="fact.effective_from"> · effective {{ fact.effective_from }} to {{ fact.effective_to ?? 'open-ended' }}</template>
              </p>
              <p v-if="!fact.evidence.length" class="small error">No source evidence attached.</p>
              <ul v-else class="small">
                <li v-for="(proof, proofIndex) in fact.evidence" :key="`${proof.source_document_id}-${proofIndex}`">
                  <a :href="proof.source_url" target="_blank" rel="noopener noreferrer">{{ proof.source_name }}</a>
                  · retrieved {{ formatDateTime(proof.retrieved_at) }}
                  <span v-if="proof.locator"> · {{ proof.locator }}</span>
                  <span v-if="proof.excerpt"> · “{{ proof.excerpt }}”</span>
                </li>
              </ul>
            </li>
          </ul>
        </details>
        <ul v-if="item.missing_information.length" class="small muted">
          <li v-for="warning in item.missing_information" :key="warning">{{ warning }}</li>
        </ul>
        <details v-if="item.publication_events.length">
          <summary>Publication audit history ({{ item.publication_events.length }})</summary>
          <ul class="small">
            <li v-for="(event, index) in item.publication_events" :key="`${event.action}-${event.created_at}-${index}`">
              {{ humanize(event.action) }} · {{ formatDateTime(event.created_at) }} · {{ event.reason ?? 'No reason' }} · reviewer {{ event.actor_user_id ?? 'unavailable' }}
            </li>
          </ul>
        </details>
        <p v-if="item.publication_status !== 'published' && !item.can_publish" class="small error">{{ item.publication_blocker }}</p>
        <div class="field">
          <label :for="`program-reason-${item.id}`">Reviewer reason</label>
          <textarea :id="`program-reason-${item.id}`" v-model="reasons[item.id]" rows="2" maxlength="2000"
            :aria-describedby="`program-reason-help-${item.id}`" />
          <p :id="`program-reason-help-${item.id}`" class="small muted">
            Summarize the source or evidence reviewed and why it supports this decision.
          </p>
        </div>
        <p v-if="errors[item.id]" class="error" role="alert">{{ errors[item.id] }}</p>
        <div class="row">
          <button v-if="item.publication_status !== 'published'" class="btn btn-primary" :disabled="busy[item.id] || !item.can_publish || !isSubstantivePublicationReason(reasons[item.id])" @click="decide(item.id, 'publish')">Publish program</button>
          <button v-else class="btn" :disabled="busy[item.id] || !isSubstantivePublicationReason(reasons[item.id])" @click="decide(item.id, 'unpublish')">Unpublish</button>
        </div>
      </section>
    </AsyncState>
  </div>
</template>
