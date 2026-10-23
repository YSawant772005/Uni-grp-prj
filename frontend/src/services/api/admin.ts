/** Reviewer/admin endpoints: queue, fact actions, sources, jobs, audit. */
import { request } from './client'
import type {
  AuditEvent,
  FactActionResult,
  FactDetail,
  Job,
  JobDetail,
  Paginated,
  ReviewQueueItem,
  Source,
  SourceDetail,
} from '../../types/api'

export const admin = {
  catalogueArchives: () => request<{ archive_available: boolean; items: { id: string; created_at: string; operator: string; reason: string; backup_sha256: string }[] }>('/admin/catalogue-archives'),
  catalogueArchiveRecords: (operationId: string, query: { table_name?: string; page?: number } = {}) =>
    request<Paginated<{ table_name: string; record_key: string; payload: Record<string, unknown>; row_sha256: string }>>(`/admin/catalogue-archives/${operationId}`, { query: { ...query } }),
  institutionReviews: (query: { status?: string; stage?: string; page?: number; page_size?: number } = {}) =>
    request<Paginated<InstitutionReviewSummary> & { stage_counts: Record<string, number> }>('/admin/institution-reviews', { query: { ...query } }),
  institutionReview: (universityId: string) =>
    request<InstitutionReviewDetail>(`/admin/institution-reviews/${universityId}`),
  decideInstitutionReview: (universityId: string, action: 'approve' | 'reject' | 'defer' | 'needs_evidence', reason: string) =>
    request<{ university_id: string; status: string; reviewed_by_user_id: string; reviewed_at: string }>(
      `/admin/institutions/${universityId}/review`, { method: 'POST', body: { action, reason } },
    ),
  identityReviews: (query: { status?: string; page?: number; page_size?: number } = {}) =>
    request<Paginated<IdentityReview>>('/admin/identity-reviews', { query: { ...query } }),
  programPublicationReviews: (query: { status?: string; page?: number; page_size?: number } = {}) =>
    request<Paginated<ProgramPublicationItem>>('/admin/program-publication-reviews', { query: { ...query } }),
  publishProgram: (programId: string, reason: string) =>
    request<{ program_id: string; publication_status: string; published_at: string | null }>(
      `/admin/programs/${programId}/publish`, { method: 'POST', body: { reason } },
    ),
  unpublishProgram: (programId: string, reason: string) =>
    request<{ program_id: string; publication_status: string; published_at: string | null }>(
      `/admin/programs/${programId}/unpublish`, { method: 'POST', body: { reason } },
    ),
  approveIdentityReview: (reviewId: string, universityId: string, reason: string) =>
    request<{ review_id: string; action: string; status: string; resolved_university_id: string }>(
      `/admin/identity-reviews/${reviewId}/approve`,
      { method: 'POST', body: { university_id: universityId, reason } },
    ),
  rejectIdentityReview: (reviewId: string, reason: string) =>
    request<{ review_id: string; action: string; status: string }>(
      `/admin/identity-reviews/${reviewId}/reject`, { method: 'POST', body: { reason } },
    ),
  deferIdentityReview: (reviewId: string, reason: string) =>
    request<{ review_id: string; action: string; status: string }>(
      `/admin/identity-reviews/${reviewId}/defer`, { method: 'POST', body: { reason } },
    ),
  reviewQueue: (query: {
    status?: string
    entity_type?: string
    fact_key?: string
    page?: number
    page_size?: number
  } = {}) => request<Paginated<ReviewQueueItem>>('/admin/review-queue', { query: { ...query } }),
  fact: (factId: string) => request<FactDetail>(`/admin/facts/${factId}`),
  approveFact: (factId: string, payload: { version_id?: string; reason?: string; description_summary?: string }) =>
    request<FactActionResult>(`/admin/facts/${factId}/approve`, {
      method: 'POST',
      body: payload,
    }),
  rejectFact: (factId: string, payload: { version_id?: string; reason: string }) =>
    request<FactActionResult>(`/admin/facts/${factId}/reject`, { method: 'POST', body: payload }),
  requestEvidence: (factId: string, reason: string) =>
    request<FactActionResult>(`/admin/facts/${factId}/request-evidence`, {
      method: 'POST',
      body: { reason },
    }),

  sources: (query: { enabled?: boolean; page?: number; page_size?: number } = {}) =>
    request<Paginated<Source>>('/admin/sources', { query: { ...query } }),
  source: (sourceId: string) => request<SourceDetail>(`/admin/sources/${sourceId}`),
  createSource: (payload: Record<string, unknown>) =>
    request<Source>('/admin/sources', { method: 'POST', body: payload }),
  patchSource: (sourceId: string, payload: Record<string, unknown>) =>
    request<Source>(`/admin/sources/${sourceId}`, { method: 'PATCH', body: payload }),
  refreshSource: (sourceId: string) =>
    request<Job>(`/admin/sources/${sourceId}/refresh`, { method: 'POST' }),

  jobs: (query: { status?: string; job_type?: string; source_id?: string; page?: number; page_size?: number } = {}) =>
    request<Paginated<Job>>('/admin/jobs', { query: { ...query } }),
  job: (jobId: string) => request<JobDetail>(`/admin/jobs/${jobId}`),
  retryJob: (jobId: string) => request<Job>(`/admin/jobs/${jobId}/retry`, { method: 'POST' }),

  auditEvents: (query: {
    action?: string
    actor_user_id?: string
    entity_type?: string
    since?: string
    page?: number
  } = {}) => request<Paginated<AuditEvent>>('/admin/audit-events', { query: { ...query } }),
}

export interface InstitutionReviewSummary {
  workflow_stage: string
  university_id: string
  name: string
  country_code: string
  official_website_url: string | null
  institution_type: string | null
  recognition_status: string
  location: string | null
  website_evidence_status: string
  status: string
  reviewed_at: string | null
  reviewed_by_user_id: string | null
  review_reason: string | null
  identifier_count: number
  fact_count: number
  program_count: number
  source_keys: string[]
  is_demo: boolean
  program_coverage: {
    status: string
    program_count: number
    evidence_backed_program_count: number
    message: string
  }
  approval_eligibility: { eligible: boolean; blockers: string[] }
}

export interface InstitutionReviewDetail extends InstitutionReviewSummary {
  workflow: { step: string; complete: boolean }[]
  source_discovery: { source_key: string; name: string; terms_url: string | null; allowed_use_policy: string; connection_status: string; status: string; requires_identity: string | null; matching_identifier: string | null; message: string }[]
    identifiers: Record<string, unknown>
  catalogue_sources: { id: string; title: string | null; url: string; source_key: string; source_name: string; allowed_use_policy: string; institution_linked: boolean; retrieved_at: string; academic_period: string | null; last_checked_at: string | null }[]
  identifier_claims: {
    namespace: string; value: string; normalized_value: string; scope: string
    claim_status: string; source_key: string; source_name: string; publisher: string | null
    source_document: { id: string; title: string | null; url: string; retrieved_at: string; http_status: number | null; fetch_status: string } | null
  }[]
  website_evidence: { url: string; title: string | null; source_name: string; publisher: string | null; allowed_use_policy: string; retrieved_at: string; excerpt: string | null; locator: string | null; status: string }[]
  facts: { id: string; fact_key: string; applicability_key: string; status: string; value: unknown; display_value: { summary: string; fields: { label: string; value: string }[] }; version_count: number; evidence: { source_name: string; publisher: string | null; allowed_use_policy: string; source_url: string; source_document_id: string; retrieved_at: string; http_status: number | null; fetch_status: string; excerpt: string | null; locator: string | null }[] }[]
  programs: {
    id: string; title: string; degree_level: string; publication_status: string
    official_program_url: string | null; duration_min_months: number | null
    duration_max_months: number | null; delivery_language: string | null; study_mode: string | null
    identity_layers: { record_scope: string; qualification: { level: string; mention: string | null; source_identifier: string | null }; pathway: { name: string | null; source_identifier: string | null }; study_stage: string | null; location_as_reported: unknown; awarding_institutions: unknown; relationship_note: string }
    evidence_backed: boolean
    review_readiness: { eligible: boolean; blockers: string[]; warnings: string[]; academic_periods: string[]; applicability: string }
    missing_information: string[]
    source_identities: {
      source_key: string; external_key: string; claim_status: string; source_name: string
      allowed_use_policy: string | null
      source_document: { id: string; title: string | null; url: string; retrieved_at: string; http_status: number | null; fetch_status: string } | null
    }[]
    program_facts: ProgramPublicationItem['program_facts']
    registry_page_evidence?: { status: string; url: string | null; reason: string | null }
    program_page_evidence: { status: string; url: string | null; reason: string | null }
    possible_same_title_program_ids: string[]
  }[]
  campuses: { id: string; name: string | null; city_id: string | null; address_public: string | null }[]
  events: { id: string; action: string; actor_user_id: string; reason: string; before: unknown; after: unknown; created_at: string }[]
  warnings: string[]
}

export interface IdentityReview {
  id: string
  status: string
  source: { id: string; name: string; source_key: string | null; owner_or_publisher?: string | null; allowed_use_policy?: string; license_notes?: string | null; terms_url?: string | null } | null
  source_document: { id: string; title?: string | null; url: string; retrieved_at: string; http_status?: number | null; fetch_status?: string; content_excerpt?: string } | null
  external_key: string
  candidate: {
    name?: string
    country_code?: string | null
    website?: string | null
    identifiers?: Record<string, string>
    aliases?: string[]
    program_candidate_count?: number
    program_candidates?: { external_key: string; title: string; discipline?: string | null }[]
  }
  identity_review: { code?: string; message?: string }[]
  suggested_university: { id: string; name: string; country_code: string; official_website_url?: string | null; external_identifiers?: Record<string, unknown>; accepted_identifiers?: { namespace: string; value: string; scope: string; source_key: string; claim_status: string }[] } | null
  resolved_university_id: string | null
  reviewed_by_user_id: string | null
  reviewed_at: string | null
  review_reason: string | null
  events?: { id: string; action: string; actor_user_id: string; reason: string; created_at: string }[]
}

export interface ProgramPublicationItem {
  id: string
  name: string
  degree_level: string
  country_code: string
  official_program_url: string | null
  official_program_url_classification: string
  publication_status: string
  published_at: string | null
  university: {
    id: string; name: string; country_code: string; official_website_url: string | null
    is_demo: boolean; identifiers: Record<string, unknown>
    identifier_claims: { namespace: string; value: string; scope: string; source_key: string; claim_status: string; source_document_id: string | null }[]
    website_evidence: { url: string; title: string | null; retrieved_at: string; excerpt: string | null; locator: string | null; status: string }[]
    website_evidence_status: string
  } | null
  academic_field: { id: string; key: string; display_name: string } | null
  source_identities: {
    source_key: string; external_key: string; claim_status: string
    source: { id: string; name: string; allowed_use_policy: string; authority_tier: number } | null
    document: { id: string; title: string | null; url: string; retrieved_at: string; http_status: number | null; fetch_status: string } | null
  }[]
  fact_count: number
  registry_page_evidence?: { status: string; url: string | null; reason: string | null }
  program_page_evidence: {
    status: string; url: string | null; reason: string | null
    fact_id?: string; version_id?: string
    evidence?: { source_name: string; source_url: string; source_document_id: string; retrieved_at: string; excerpt: string | null; locator: string | null }[]
  }
  program_facts: {
    fact_id: string; fact_key: string; applicability_key: string; status: string; value: unknown
    display_value: { summary: string; fields: { label: string; value: string }[] }
    applicable_intake_year: number | null; applicable_intake_term: string | null
    effective_from: string | null; effective_to: string | null
    evidence: { source_name: string; publisher: string | null; allowed_use_policy: string; source_url: string; source_document_id: string; retrieved_at: string; http_status: number | null; fetch_status: string; excerpt: string | null; locator: string | null; supports_or_conflicts: string }[]
  }[]
  missing_information: string[]
  can_publish: boolean
  publication_blocker: string | null
  publication_events: { action: string; actor_user_id: string | null; reason: string | null; created_at: string }[]
}
