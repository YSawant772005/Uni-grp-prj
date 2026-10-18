/** Auth, profile, recommendation runs, saved programs and comparisons. */
import { request } from './client'
import type {
  AuthUser,
  Completeness,
  Comparison,
  EligibilityEvaluation,
  ExplanationsResponse,
  Paginated,
  Profile,
  ProgramSummary,
  RecommendationRun,
  RunListItem,
  SavedProgram,
} from '../../types/api'
// --------------------------------------------------------------------- auth

export const auth = {
  me: () => request<AuthUser>('/auth/me'),
  register: (email: string, password: string) =>
    request<AuthUser>('/auth/register', { method: 'POST', body: { email, password } }),
  login: (email: string, password: string) =>
    request<AuthUser>('/auth/login', { method: 'POST', body: { email, password } }),
  logout: () => request<null>('/auth/logout', { method: 'POST' }),
}

// ------------------------------------------------------------------ profile

export const profile = {
  get: () => request<Profile>('/profile'),
  completeness: () => request<Completeness>('/profile/completeness'),
  patch: (payload: Partial<Profile>) =>
    request<Profile>('/profile', { method: 'PATCH', body: payload }),
  completeOnboarding: (payload: Record<string, unknown>) =>
    request<{ profile: Profile; completeness: Completeness }>(
      '/profile/onboarding/complete',
      { method: 'POST', body: payload },
    ),
}

// -------------------------------------------------------- recommendations

export const recommendations = {
  evaluate: (programIds: string[]) =>
    request<{ items: EligibilityEvaluation[] }>('/eligibility/evaluations', {
      method: 'POST',
      body: { program_ids: programIds },
    }),
  createRun: (payload: Record<string, unknown> = {}) =>
    request<RecommendationRun>('/recommendations', { method: 'POST', body: payload }),
  listRuns: () => request<{ items: RunListItem[] }>('/recommendations'),
  getRun: (runId: string) => request<RecommendationRun>(`/recommendations/${runId}`),
  explanations: (runId: string) =>
    request<ExplanationsResponse>(`/recommendations/${runId}/explanations`),
  refreshRun: (runId: string) =>
    request<RecommendationRun>(`/recommendations/${runId}/refresh`, { method: 'POST' }),
}

// ----------------------------------------------------------- saved + compare

export const library = {
  saved: () => request<{ items: SavedProgram[] }>('/saved-programs'),
  save: (programId: string, note?: string | null) =>
    request<SavedProgram>('/saved-programs', {
      method: 'POST',
      body: { program_id: programId, note: note ?? null },
    }),
  unsave: (programId: string) =>
    request<null>(`/saved-programs/${programId}`, { method: 'DELETE' }),
  compare: (programIds: string[]) =>
    request<{ items: import('../../types/api').CompareItem[]; count: number }>(
      '/programs/compare', { method: 'POST', body: { program_ids: programIds } }),
  comparisons: () => request<{ items: Comparison[] }>('/comparisons'),
  createComparison: (programIds: string[], title?: string) =>
    request<Comparison>('/comparisons', {
      method: 'POST',
      body: { program_ids: programIds, title: title ?? 'My comparison' },
    }),
  getComparison: (id: string) => request<Comparison>(`/comparisons/${id}`),
  patchComparison: (id: string, payload: { title?: string; program_ids?: string[] }) =>
    request<Comparison>(`/comparisons/${id}`, { method: 'PATCH', body: payload }),
  deleteComparison: (id: string) => request<null>(`/comparisons/${id}`, { method: 'DELETE' }),
}

export type { Paginated, ProgramSummary }
