<script setup lang="ts">
import { reactive, watch } from 'vue'
import { useRoute } from 'vue-router'
import { admin } from '../../services/api/admin'
import { useAsync } from '../../composables/useAsync'
import { formatDateTime, humanize } from '../../utils/format'
import { isSubstantivePublicationReason } from '../../utils/publicationReason'
import { ApiError } from '../../services/api/client'
import AsyncState from '../../components/AsyncState.vue'
import StatusBadge from '../../components/StatusBadge.vue'
import PaginationBar from '../../components/PaginationBar.vue'

const route = useRoute()
const status = reactive({ value: 'pending' })
const stage = reactive({ value: 'ready_for_review' })
const page = reactive({ value: 1 })
const queue = useAsync(() => admin.institutionReviews({ status: status.value, stage: stage.value, page: page.value, page_size: 20 }), {
  immediate: !route.params.universityId,
})
const detail = useAsync(() => admin.institutionReview(String(route.params.universityId)), {
  immediate: Boolean(route.params.universityId),
})
const decision = reactive({ action: 'approve' as 'approve' | 'reject' | 'defer' | 'needs_evidence', reason: '' })
const busy = reactive({ value: false })
const error = reactive({ value: '' })
const reasonError = reactive({ value: '' })

watch([() => status.value, () => stage.value], () => { page.value = 1; void queue.run() })
watch(() => page.value, () => void queue.run())
watch(() => decision.reason, () => { reasonError.value = '' })
watch(() => route.params.universityId, (id) => {
  decision.reason = ''; error.value = ''; reasonError.value = ''
  if (id) void detail.run()
  else void queue.run()
})

async function submit() {
  const item = detail.data.value
  if (!item || busy.value) return
  busy.value = true
  error.value = ''
  try {
    await admin.decideInstitutionReview(item.university_id, decision.action, decision.reason.trim())
    await detail.run()
  } catch (cause) {
    if (cause instanceof ApiError && cause.fieldError('reason')) {
      reasonError.value = cause.fieldError('reason') ?? ''
    } else {
      error.value = cause instanceof Error ? cause.message : 'Unable to record this institution decision.'
    }
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="stack">
    <template v-if="!route.params.universityId">
      <div>
        <h1>University and Master’s review</h1>
        <p class="small muted" style="margin: 0">
          Review the university identity, official website and named Master’s offerings together.
          Universities awaiting programme discovery remain in evidence collection.
        </p>
      </div>
      <section class="card field" style="max-width: 420px">
        <label for="institution-review-stage">Evidence readiness</label>
        <select id="institution-review-stage" v-model="stage.value">
          <option value="ready_for_review">Ready for human review ({{ queue.data.value?.stage_counts?.ready_for_review ?? 0 }})</option>
          <option value="discovery">Discovery — programme data needed ({{ queue.data.value?.stage_counts?.discovery ?? 0 }})</option>
          <option value="evidence_collection">Evidence collection ({{ queue.data.value?.stage_counts?.evidence_collection ?? 0 }})</option>
          <option value="all">All institutions</option>
        </select>
        <label for="institution-review-status">Review state</label>
        <select id="institution-review-status" v-model="status.value">
          <option value="pending">Pending</option>
          <option value="needs_evidence">Needs evidence</option>
          <option value="deferred">Deferred</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
        </select>
      </section>
      <AsyncState :loading="queue.loading.value" :error="queue.error.value"
        :empty="!queue.data.value?.items.length" empty-title="No universities in this readiness category"
        empty-hint="Choose Discovery or Evidence collection to inspect universities still awaiting sufficient Master’s and website evidence."
        @retry="queue.run">
        <RouterLink v-for="item in queue.data.value?.items" :key="item.university_id"
          :to="`/admin/institution-reviews/${item.university_id}`" class="card row-between"
          style="color: inherit">
          <div>
            <strong>{{ item.name }}</strong>
            <div class="small muted">{{ item.country_code }} · {{ item.institution_type ? humanize(item.institution_type) : 'Institution type unavailable' }} ·
              {{ item.location ?? 'Location unavailable' }} · {{ item.identifier_count }} identifier claims ·
              {{ item.fact_count }} grouped facts · {{ item.program_count }} programmes ·
              {{ humanize(item.program_coverage.status) }} ·
              {{ item.source_keys.join(', ') || 'source unknown' }}</div>
            <div class="small">Website: <a v-if="item.official_website_url" :href="item.official_website_url"
              target="_blank" rel="noopener noreferrer" @click.stop>{{ item.official_website_url }}</a>
              <span v-else>unresolved</span> · evidence {{ humanize(item.website_evidence_status) }}</div>
          </div>
          <div class="stack-sm"><StatusBadge :status="item.workflow_stage" /><StatusBadge :status="item.status" /></div>
        </RouterLink>
      </AsyncState>
      <PaginationBar v-if="queue.data.value" :page="queue.data.value.page"
        :page-size="queue.data.value.page_size"
        :total-pages="queue.data.value.total_pages" :total-items="queue.data.value.total_items"
        @update:page="page.value = $event" />
    </template>

    <template v-else>
      <p><RouterLink to="/admin/institution-reviews">← All institutions</RouterLink></p>
      <AsyncState :loading="detail.loading.value" :error="detail.error.value"
        :empty="!detail.data.value" empty-title="Institution review unavailable" @retry="detail.run">
        <template v-if="detail.data.value">
          <section class="card stack">
            <div class="row-between">
              <div>
                <h1 style="margin: 0">{{ detail.data.value.name }}</h1>
                <p class="small muted">{{ detail.data.value.country_code }} ·
                  {{ detail.data.value.institution_type ? humanize(detail.data.value.institution_type) : 'Institution type unavailable' }} ·
                  {{ detail.data.value.location ?? 'Location unavailable' }} ·
                  {{ humanize(detail.data.value.recognition_status) }} · {{ detail.data.value.university_id }}</p>
              </div>
              <StatusBadge :status="detail.data.value.status" />
            </div>
            <details><summary>Evidence collection progress</summary>
              <ul class="small"><li v-for="step in detail.data.value.workflow" :key="step.step">{{ step.complete ? 'Complete' : 'Pending' }} · {{ humanize(step.step) }}</li></ul>
            </details>
            <p v-for="warning in detail.data.value.warnings" :key="warning" class="small error">{{ warning }}</p>
            <section class="card card-flat stack-sm" aria-labelledby="institution-program-coverage">
              <h2 id="institution-program-coverage">Master's programme coverage</h2>
              <StatusBadge :status="detail.data.value.program_coverage.status" />
              <p class="small">{{ detail.data.value.program_coverage.message }}</p>
              <p class="small">
                {{ detail.data.value.program_coverage.evidence_backed_program_count }} of
                {{ detail.data.value.program_coverage.program_count }} programme records have
                source-row evidence.
              </p>
            </section>
            <section class="card card-flat stack-sm" aria-labelledby="institution-approval-eligibility">
              <h2 id="institution-approval-eligibility">Approval eligibility</h2>
              <p v-if="detail.data.value.approval_eligibility.eligible" class="small">
                Required identity, website and programme evidence is available for reviewer assessment.
              </p>
              <ul v-else class="small error">
                <li v-for="blocker in detail.data.value.approval_eligibility.blockers" :key="blocker">{{ blocker }}</li>
              </ul>
            </section>
            <p class="small">Official university website:
              <a v-if="detail.data.value.official_website_url" :href="detail.data.value.official_website_url"
                target="_blank" rel="noopener noreferrer">{{ detail.data.value.official_website_url }}</a>
              <span v-else>unresolved</span> · {{ humanize(detail.data.value.website_evidence_status) }}
            </p>
            <ul v-if="detail.data.value.website_evidence.length" class="small">
              <li v-for="(proof, index) in detail.data.value.website_evidence" :key="`${proof.url}-${index}`">
                {{ proof.source_name }}<span v-if="proof.publisher"> ({{ proof.publisher }})</span>:
                <a :href="proof.url" target="_blank" rel="noopener noreferrer">{{ proof.title ?? proof.url }}</a>
                · {{ formatDateTime(proof.retrieved_at) }} · {{ humanize(proof.status) }}
                · use {{ humanize(proof.allowed_use_policy) }}
                <span v-if="proof.locator"> · {{ proof.locator }}</span>
                <span v-if="proof.excerpt"> · “{{ proof.excerpt }}”</span>
              </li>
            </ul>
            <details><summary>Raw source identity JSON</summary>
              <pre class="small" style="white-space: pre-wrap">{{ JSON.stringify(detail.data.value.identifiers, null, 2) }}</pre>
            </details>
          </section>

          <section class="card stack">
            <h2>Authoritative and auxiliary identifiers</h2>
            <p v-if="!detail.data.value.identifier_claims.length" class="muted">No source identifier claims.</p>
            <article v-for="(claim, index) in detail.data.value.identifier_claims" :key="`${claim.source_key}-${claim.namespace}-${claim.value}-${index}`">
              <strong>{{ claim.namespace }}:</strong> <span class="mono">{{ claim.value }}</span>
              · {{ claim.scope }} · {{ humanize(claim.claim_status) }} · {{ claim.source_name }}
              <span v-if="claim.publisher"> · {{ claim.publisher }}</span>
              <div v-if="claim.source_document" class="small">
                <a :href="claim.source_document.url" target="_blank" rel="noopener noreferrer">{{ claim.source_document.title ?? 'Source document' }}</a>
                · retrieved {{ formatDateTime(claim.source_document.retrieved_at) }}
                · HTTP {{ claim.source_document.http_status ?? 'unknown' }} · {{ claim.source_document.fetch_status }}
              </div>
            </article>
            <details><summary>Raw identifier claim records</summary>
              <pre class="small" style="white-space: pre-wrap">{{ JSON.stringify(detail.data.value.identifier_claims, null, 2) }}</pre>
            </details>
          </section>

          <section class="card stack">
            <h2>Official Master’s catalogue sources</h2>
            <p v-if="!detail.data.value.catalogue_sources.length" class="small muted">A permitted Master’s source has not been imported. Programme availability remains unknown.</p>
            <details v-if="detail.data.value.source_discovery.length"><summary>Potential official sources for discovery</summary>
              <article v-for="source in detail.data.value.source_discovery" :key="source.source_key" class="small">
                {{ source.name }} · {{ humanize(source.status) }} · {{ source.message }}
                <span v-if="source.requires_identity"> Required identity: {{ source.requires_identity }} {{ source.matching_identifier ?? 'unresolved' }}.</span>
                <a v-if="source.terms_url" :href="source.terms_url" target="_blank" rel="noopener noreferrer">Source reuse basis</a>
              </article>
            </details>
            <article v-for="source in detail.data.value.catalogue_sources" :key="source.id" class="small">
              <a :href="source.url" target="_blank" rel="noopener noreferrer">{{ source.title ?? source.source_name }}</a>
              · {{ source.source_name }} · use {{ humanize(source.allowed_use_policy) }}
              · institution link {{ source.institution_linked ? 'established' : 'needs evidence' }}
              · academic period {{ source.academic_period ?? 'not supplied' }}
              · checked {{ formatDateTime(source.last_checked_at ?? source.retrieved_at) }}
            </article>
          </section>

          <section class="card stack">
            <h2>Associated programme records ({{ detail.data.value.programs.length }})</h2>
            <article v-for="program in detail.data.value.programs" :key="program.id" class="card card-flat stack-sm">
              <div class="row-between"><strong>{{ program.title }}</strong><StatusBadge :status="program.publication_status" /></div>
              <p class="small">{{ humanize(program.identity_layers.record_scope) }} · Qualification: {{ program.identity_layers.qualification.mention ?? humanize(program.identity_layers.qualification.level) }}<span v-if="program.identity_layers.qualification.source_identifier"> ({{ program.identity_layers.qualification.source_identifier }})</span> · Pathway: {{ program.identity_layers.pathway.name ?? 'not specified' }} · Study stage (M1/M2): {{ program.identity_layers.study_stage ?? 'unknown' }}</p>
              <p class="small muted">{{ program.identity_layers.relationship_note }}</p>
              <p class="small">Academic period: {{ program.review_readiness.academic_periods.join(', ') || 'not supplied' }} · {{ humanize(program.review_readiness.applicability) }}</p>
              <p v-for="blocker in program.review_readiness.blockers" :key="blocker" class="small error">{{ blocker }}</p>
              <p v-for="warning in program.review_readiness.warnings" :key="warning" class="small muted">{{ warning }}</p>
              <p class="small muted">{{ program.missing_information.join(' ') }}</p>
              <div class="small">{{ humanize(program.degree_level) }} · {{ program.id }} ·
                {{ program.study_mode ? humanize(program.study_mode) : 'Study mode not specified' }} ·
                {{ program.delivery_language || 'Teaching language not specified' }} ·
                {{ program.duration_min_months ?? program.duration_max_months ?? 'Duration unavailable' }}<span v-if="program.duration_min_months || program.duration_max_months"> months</span></div>
              <div v-if="program.program_page_evidence.status === 'verified' && program.program_page_evidence.url" class="small">
                <a :href="program.program_page_evidence.url" target="_blank" rel="noopener noreferrer">Verified official program page</a>
              </div>
              <div v-else class="small error">
                {{ program.program_page_evidence.reason ?? 'Official university program page not verified.' }}
                <a v-if="program.program_page_evidence.url" :href="program.program_page_evidence.url"
                  target="_blank" rel="noopener noreferrer">Open unverified candidate URL</a>
              </div>
              <p v-if="program.registry_page_evidence?.url" class="small">
                <a :href="program.registry_page_evidence.url" target="_blank" rel="noopener noreferrer">Verified government programme record</a> · {{ program.registry_page_evidence.reason }}
              </p>
              <p v-if="program.possible_same_title_program_ids.length" class="small error">
                Possible same-title records: {{ program.possible_same_title_program_ids.join(', ') }}. Compare source identifiers; no records were merged.
              </p>
              <ul class="small">
                <li v-for="identity in program.source_identities" :key="`${identity.source_key}-${identity.external_key}`">
                  {{ identity.source_name }} · <span class="mono">{{ identity.external_key }}</span> · {{ humanize(identity.claim_status) }}
                  <template v-if="identity.source_document"> · <a :href="identity.source_document.url" target="_blank" rel="noopener noreferrer">{{ identity.source_document.title ?? 'Source record' }}</a>
                    · retrieved {{ formatDateTime(identity.source_document.retrieved_at) }} · {{ identity.source_document.fetch_status }}</template>
                </li>
              </ul>
              <details v-if="program.program_facts.length">
                <summary>Programme facts and row evidence ({{ program.program_facts.length }})</summary>
                <article v-for="(fact, factIndex) in program.program_facts" :key="`${fact.fact_key}-${fact.applicability_key}-${factIndex}`" class="stack-sm">
                  <RouterLink :to="`/admin/review/${fact.fact_id}`">{{ humanize(fact.fact_key) }}</RouterLink>
                  <span class="small">{{ fact.display_value.summary }} · {{ humanize(fact.status) }}
                    <span v-if="fact.applicability_key"> · applies {{ fact.applicability_key }}</span>
                    <span v-if="fact.applicable_intake_year"> · intake year {{ fact.applicable_intake_year }}</span>
                    <span v-if="fact.applicable_intake_term"> · {{ fact.applicable_intake_term }}</span>
                  </span>
                  <ul class="small">
                    <li v-for="(proof, proofIndex) in fact.evidence" :key="`${proof.source_document_id}-${proofIndex}`">
                      <a :href="proof.source_url" target="_blank" rel="noopener noreferrer">{{ proof.source_name }}</a>
                      <span v-if="proof.publisher"> ({{ proof.publisher }})</span>
                      · {{ formatDateTime(proof.retrieved_at) }} · {{ proof.fetch_status }}
                      · use {{ humanize(proof.allowed_use_policy) }}
                      <span v-if="proof.locator"> · {{ proof.locator }}</span>
                      <span v-if="proof.excerpt"> · “{{ proof.excerpt }}”</span>
                    </li>
                    <li v-if="!fact.evidence.length">No evidence is attached to this fact.</li>
                  </ul>
                </article>
              </details>
            </article>
          </section>

          <section class="card stack">
            <details><summary>Technical university facts and verification ({{ detail.data.value.facts.length }})</summary>
            <article v-for="fact in detail.data.value.facts" :key="fact.id" class="card card-flat stack-sm">
              <div class="row-between"><RouterLink :to="`/admin/review/${fact.id}`">{{ humanize(fact.fact_key) }}</RouterLink><StatusBadge :status="fact.status" /></div>
              <p class="small" style="margin: 0">{{ fact.display_value.summary }}</p>
              <p class="small muted" style="margin: 0">{{ fact.version_count }} historical version(s) · {{ fact.evidence.length }} evidence record(s)
                <span v-if="fact.applicability_key"> · applies {{ fact.applicability_key }}</span>
              </p>
              <ul class="small">
                <li v-for="(proof, index) in fact.evidence" :key="`${proof.source_document_id}-${index}`">
                  <a :href="proof.source_url" target="_blank" rel="noopener noreferrer">{{ proof.source_name }}</a>
                  <span v-if="proof.publisher"> ({{ proof.publisher }})</span>
                  · {{ formatDateTime(proof.retrieved_at) }} · {{ proof.fetch_status }}
                  · use {{ humanize(proof.allowed_use_policy) }}
                  <span v-if="proof.locator"> · {{ proof.locator }}</span>
                  <span v-if="proof.excerpt"> · “{{ proof.excerpt }}”</span>
                </li>
              </ul>
              <details><summary>Raw fact JSON</summary><pre class="small" style="white-space: pre-wrap">{{ JSON.stringify(fact.value, null, 2) }}</pre></details>
            </article>
            </details>
          </section>

          <section v-if="detail.data.value.campuses.length" class="card stack">
            <h2>Known campuses</h2>
            <ul><li v-for="campus in detail.data.value.campuses" :key="campus.id">{{ campus.name ?? 'Unnamed campus' }} · {{ campus.address_public ?? 'location unavailable' }}</li></ul>
          </section>

          <section class="card stack">
            <h2>Review history</h2>
            <p v-if="detail.data.value.review_reason" class="small">Current decision: {{ detail.data.value.review_reason }}</p>
            <ul v-if="detail.data.value.events.length" class="small">
              <li v-for="event in detail.data.value.events" :key="event.id">{{ humanize(event.action) }} · {{ formatDateTime(event.created_at) }} · reviewer {{ event.actor_user_id }} · {{ event.reason }}</li>
            </ul>
            <p v-else class="small muted">No human institution approval has been recorded.</p>
            <template v-if="!['approved', 'rejected'].includes(detail.data.value.status)">
              <div class="field">
                <label for="institution-decision">Decision</label>
                <select id="institution-decision" v-model="decision.action">
                  <option value="approve" :disabled="!detail.data.value.approval_eligibility.eligible">
                    Approve institution identity
                  </option>
                  <option value="needs_evidence">Request stronger evidence</option>
                  <option value="defer">Defer</option>
                  <option value="reject">Reject</option>
                </select>
              </div>
              <div class="field">
                <label for="institution-reason">Reviewer justification</label>
                <textarea id="institution-reason" v-model="decision.reason" rows="3" maxlength="2000"
                  :aria-invalid="Boolean(reasonError.value)"
                  aria-describedby="institution-reason-help institution-reason-error" />
                <p id="institution-reason-help" class="small muted">
                  Use at least 30 characters and five words. Name the source or evidence you reviewed
                  and explain why it supports this decision.
                </p>
                <p v-if="reasonError.value" id="institution-reason-error" class="small error" role="alert">
                  {{ reasonError.value }}
                </p>
              </div>
              <p v-if="error.value" class="error" role="alert">{{ error.value }}</p>
              <button class="btn btn-primary"
                :disabled="busy.value || !isSubstantivePublicationReason(decision.reason) ||
                  (decision.action === 'approve' && !detail.data.value.approval_eligibility.eligible)" @click="submit">
                Record institution decision
              </button>
            </template>
          </section>
        </template>
      </AsyncState>
    </template>
  </div>
</template>
