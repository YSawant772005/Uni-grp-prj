/** Cost estimates, scholarship matching, loans and ROI scenarios. */
import { request } from './client'
import type {
  CostEstimate,
  CostScenariosResponse,
  LoanScenario,
  RoiScenario,
  ScholarshipMatchesResponse,
} from '../../types/api'

export const finance = {
  estimate: (payload: {
    program_id: string
    scenario?: string
    currency?: string
    save?: boolean
    name?: string
    funding_amount?: number
    funding_currency?: string
  }) =>
    request<CostEstimate & { scenario_id?: string }>('/cost-estimates', {
      method: 'POST',
      body: payload,
    }),
  programEstimates: (programId: string) =>
    request<CostScenariosResponse>(`/programs/${programId}/cost-estimates`),

  scholarshipMatches: () =>
    request<ScholarshipMatchesResponse>('/scholarships/matches', { method: 'POST' }),

  createLoan: (payload: Record<string, unknown>) =>
    request<LoanScenario>('/loan-scenarios', { method: 'POST', body: payload }),
  loans: () => request<{ items: LoanScenario[] }>('/loan-scenarios'),
  loan: (id: string) => request<LoanScenario>(`/loan-scenarios/${id}`),
  deleteLoan: (id: string) => request<null>(`/loan-scenarios/${id}`, { method: 'DELETE' }),

  createRoi: (payload: Record<string, unknown>) =>
    request<RoiScenario>('/roi-scenarios', { method: 'POST', body: payload }),
  rois: () => request<{ items: RoiScenario[] }>('/roi-scenarios'),
  roi: (id: string) => request<RoiScenario>(`/roi-scenarios/${id}`),
  deleteRoi: (id: string) => request<null>(`/roi-scenarios/${id}`, { method: 'DELETE' }),
}
