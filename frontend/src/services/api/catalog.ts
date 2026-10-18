/** Public catalogue: programs, evidence, outcomes, funding, destinations. */
import { request } from './client'
import type {
  CityDetail,
  CityRef,
  Country,
  CountryDetail,
  EvidenceItem,
  FundingOpportunity,
  OfficialRule,
  OutcomeEvidence,
  OutcomesResponse,
  Paginated,
  ProgramDetail,
  ProgramOutcome,
  ProgramSummary,
  Scholarship,
  ScholarshipDetail,
} from '../../types/api'

export interface ProgramQuery {
  q?: string
  country?: string
  city?: string
  field?: string
  degree_level?: string
  language?: string
  min_duration_months?: number
  max_duration_months?: number
  max_tuition?: number
  currency?: string
  recognition_status?: string
  page?: number
  page_size?: number
  sort?: 'name' | 'deadline' | 'tuition' | 'country'
  order?: 'asc' | 'desc'
}

export const catalog = {
  programs: (query: ProgramQuery = {}) =>
    request<Paginated<ProgramSummary>>('/programs', { query: { ...query } }),
  program: (id: string) => request<ProgramDetail>(`/programs/${id}`),
  requirements: (id: string) =>
    request<{ items: ProgramDetail['requirements'] }>(`/programs/${id}/requirements`),
  fees: (id: string) => request<{ items: ProgramDetail['fees'] }>(`/programs/${id}/fees`),
  intakes: (id: string) => request<{ items: ProgramDetail['intakes'] }>(`/programs/${id}/intakes`),
  evidence: (id: string, page = 1) =>
    request<Paginated<EvidenceItem>>(`/programs/${id}/evidence`, { query: { page } }),
  outcomes: (id: string) =>
    request<{ items: ProgramOutcome[] }>(`/programs/${id}/outcomes`),

  scholarships: (query: { q?: string; country?: string; page?: number; page_size?: number } = {}) =>
    request<Paginated<Scholarship>>('/scholarships', { query: { ...query } }),
  scholarship: (id: string) => request<ScholarshipDetail>(`/scholarships/${id}`),

  funding: (query: { opportunity_type?: string; country?: string; q?: string; page?: number; page_size?: number } = {}) =>
    request<Paginated<FundingOpportunity>>('/funding-opportunities', { query: { ...query } }),

  outcomesSearch: (query: { field?: string; country?: string; program_id?: string; page?: number } = {}) =>
    request<OutcomesResponse>('/outcomes', { query: { ...query } }),

  countries: () => request<{ items: Country[] }>('/destinations/countries'),
  country: (code: string) => request<CountryDetail>(`/destinations/countries/${code}`),
  cities: (code: string) => request<{ items: CityRef[] }>(`/destinations/countries/${code}/cities`),
  city: (cityId: string) => request<CityDetail>(`/destinations/cities/${cityId}`),
  rules: (query: { country?: string; rule_type?: string; page?: number } = {}) =>
    request<Paginated<OfficialRule>>('/destinations/rules', { query: { ...query } }),
}

export type { OutcomeEvidence }
