import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import InstitutionReviewView from '../features/admin/InstitutionReviewView.vue'
import { ApiError } from '../services/api/client'

const api = vi.hoisted(() => ({
  institutionReview: vi.fn(),
  institutionReviews: vi.fn(),
  decideInstitutionReview: vi.fn(),
}))

vi.mock('../services/api/admin', () => ({ admin: api }))

const universityId = '00000000-0000-4000-8000-000000000001'
const detail = {
  university_id: universityId,
  name: 'Example University',
  country_code: 'US',
  official_website_url: 'https://example.edu',
  institution_type: 'public',
  recognition_status: 'recognized',
  location: 'Example City · EX',
  website_evidence_status: 'candidate',
  workflow_stage: 'discovery',
  status: 'pending',
  reviewed_at: null,
  reviewed_by_user_id: null,
  review_reason: null,
  identifier_count: 1,
  fact_count: 1,
  program_count: 0,
  source_keys: ['directory'],
  is_demo: false,
  program_coverage: {
    status: 'availability_not_established',
    program_count: 0,
    evidence_backed_program_count: 0,
    message: 'No named Master’s programme records are associated with this institution.',
  },
  approval_eligibility: {
    eligible: false,
    blockers: ['The official university website and its evidence must be verified first.'],
  },
  workflow: [],
  source_discovery: [],
  catalogue_sources: [],
  identifiers: {},
  identifier_claims: [],
  website_evidence: [],
  facts: [],
  programs: [],
  campuses: [],
  events: [],
  warnings: [],
}

async function flushView() {
  for (let index = 0; index < 8; index += 1) await Promise.resolve()
  await nextTick()
}

async function mountReview() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/admin/institution-reviews', component: InstitutionReviewView },
      { path: '/admin/institution-reviews/:universityId', component: InstitutionReviewView },
    ],
  })
  await router.push(`/admin/institution-reviews/${universityId}`)
  await router.isReady()
  const container = document.createElement('div')
  document.body.append(container)
  const app = createApp(InstitutionReviewView)
  app.use(router)
  app.mount(container)
  await flushView()
  return { app, container }
}

describe('institution review evidence and decisions', () => {
  beforeEach(() => {
    api.institutionReview.mockReset().mockResolvedValue(detail)
    api.institutionReviews.mockReset()
    api.decideInstitutionReview.mockReset().mockResolvedValue({ status: 'needs_evidence' })
  })

  it('shows programme-coverage blockers and leaves approval unavailable when evidence is missing', async () => {
    const { app, container } = await mountReview()
    expect(container.textContent).toContain("Master's programme coverage")
    expect(container.textContent).toContain('Availability not established')
    expect(container.textContent).toContain('official university website')
    const approve = [...container.querySelectorAll('option')]
      .find((option) => option.textContent?.includes('Approve institution identity'))
    expect(approve?.disabled).toBe(true)
    app.unmount()
  })

  it('submits the supported evidence-request action with the reviewer’s reason', async () => {
    const { app, container } = await mountReview()
    const action = container.querySelector<HTMLSelectElement>('#institution-decision')
    const reason = container.querySelector<HTMLTextAreaElement>('#institution-reason')
    expect(action).not.toBeNull()
    expect(reason).not.toBeNull()
    if (action && reason) {
      action.value = 'needs_evidence'
      action.dispatchEvent(new Event('change', { bubbles: true }))
      reason.value = 'The official university website could not be verified.'
      reason.dispatchEvent(new Event('input', { bubbles: true }))
      await flushView()
      const submit = [...container.querySelectorAll('button')]
        .find((button) => button.textContent?.includes('Record institution decision'))
      expect(submit?.disabled).toBe(false)
      submit?.click()
      await flushView()
    }
    expect(api.decideInstitutionReview).toHaveBeenCalledWith(
      universityId, 'needs_evidence', 'The official university website could not be verified.',
    )
    app.unmount()
  })

  it('shows backend reason validation beside the input instead of a generic form error', async () => {
    api.decideInstitutionReview.mockRejectedValue(new ApiError(422, {
      code: 'VALIDATION_ERROR',
      message: 'The reviewer reason must describe the evidence reviewed and why it supports this decision.',
      request_id: null,
      details: [{ field: 'reason', code: 'insufficient_detail', message: 'Name the source or evidence and explain why it supports this decision.' }],
    }))
    const { app, container } = await mountReview()
    const action = container.querySelector<HTMLSelectElement>('#institution-decision')
    const reason = container.querySelector<HTMLTextAreaElement>('#institution-reason')
    if (action && reason) {
      action.value = 'reject'
      action.dispatchEvent(new Event('change', { bubbles: true }))
      reason.value = 'The official source document supports institution identity.'
      reason.dispatchEvent(new Event('input', { bubbles: true }))
      await flushView()
      container.querySelector<HTMLButtonElement>('button.btn-primary')?.click()
      await flushView()
    }
    expect(container.textContent).toContain('Name the source or evidence and explain why it supports this decision.')
    expect(container.textContent).not.toContain('Unable to record this institution decision.')
    app.unmount()
  })
})
