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
  reviewQueue: (query: {
    status?: string
    entity_type?: string
    fact_key?: string
    page?: number
    page_size?: number
  } = {}) => request<Paginated<ReviewQueueItem>>('/admin/review-queue', { query: { ...query } }),
  fact: (factId: string) => request<FactDetail>(`/admin/facts/${factId}`),
  approveFact: (factId: string, payload: { version_id?: string; reason?: string }) =>
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
