import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, h, nextTick, type Component } from 'vue'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter, RouterView } from 'vue-router'
import type { ProgramDetail, ProgramSummary } from '../types/api'
import ProgramCard from '../components/ProgramCard.vue'
import DiscoverView from '../features/discovery/DiscoverView.vue'
import ProgramDetailView from '../features/program-detail/ProgramDetailView.vue'

const api = vi.hoisted(() => ({
  programs: vi.fn(),
  countries: vi.fn(),
  program: vi.fn(),
  evidence: vi.fn(),
  outcomes: vi.fn(),
}))

vi.mock('../services/api/catalog', () => ({ catalog: api }))

const ualProgram: ProgramSummary = {
  id: 'ual-program-1',
  name: 'Master of Evidence Based Testing',
  slug: 'master-evidence-based-testing',
  degree_level: 'masters',
  field: null,
  country_code: 'ES',
  duration_min_months: null,
  duration_max_months: null,
  duration_months: null,
  language: null,
  study_mode: null,
  university: {
    id: 'ual',
    name: 'University of Almería',
    country_code: 'ES',
    recognition_status: 'recognized',
    city: null,
  },
  nearest_intake: null,
  tuition_summary: {
    value: null,
    unit: null,
    period: null,
    academic_year: null,
    applicable_intake: null,
    status: 'unavailable',
    source: null,
  },
  data_quality: { status: 'partial', last_verified_at: null, warnings: [] },
}

function page(items: ProgramSummary[], p = 1) {
  return { items, page: p, page_size: 12, total_items: items.length, total_pages: 1 }
}

async function flushView() {
  for (let i = 0; i < 8; i += 1) await Promise.resolve()
  await nextTick()
}

async function mountView(component: Component, path: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/discover', component: DiscoverView },
      { path: '/programs/:programId', component: ProgramDetailView },
      { path: '/card', component: { render: () => h(ProgramCard, { program: ualProgram }) } },
      { path: '/finance', component: { render: () => h('div', 'Finance') } },
      { path: '/destinations', component: { render: () => h('div', 'Destinations') } },
    ],
  })
  await router.push(path)
  await router.isReady()
  const container = document.createElement('div')
  document.body.append(container)
  const app = createApp(component)
  app.use(createPinia())
  app.use(router)
  app.mount(container)
  await flushView()
  return { app, container, router }
}

describe('catalogue real-data rendering', () => {
  beforeEach(() => {
    api.programs.mockReset()
    api.countries.mockReset()
    api.program.mockReset()
    api.evidence.mockReset()
    api.outcomes.mockReset()
    api.countries.mockResolvedValue({ items: [] })
    api.programs.mockResolvedValue(page([ualProgram]))
    api.evidence.mockResolvedValue({ items: [], page: 1, page_size: 20, total_items: 0, total_pages: 0 })
    api.outcomes.mockResolvedValue({ items: [] })
  })

  it('renders a real-data program card with nullable fields and working actions', async () => {
    const { app, container } = await mountView(
      { render: () => h(ProgramCard, { program: ualProgram }) }, '/card',
    )
    const text = container.textContent ?? ''
    expect(text).toContain('Field not available')
    expect(text).toContain('Duration not available')
    expect(text).toContain('Language not specified')
    expect(text).toContain('City not available')
    expect(text).toContain('Intake and deadline not available')
    expect(text).toContain('Not available')
    expect(text).not.toMatch(/\b(null|undefined|NaN)\b/)
    expect(container.querySelector('button')?.textContent).toContain('Save')
    expect(container.textContent).toContain('Compare')
    expect(container.textContent).toContain('Estimate costs')
    expect(container.querySelector('a[href="/programs/ual-program-1"]')).not.toBeNull()
    expect(container.querySelector('a[href="/finance?program=ual-program-1"]')).not.toBeNull()
    const compare = [...container.querySelectorAll('button')]
      .find((button) => button.textContent?.trim() === 'Compare')
    compare?.click()
    await flushView()
    expect(container.textContent).toContain('In compare ✓')
    app.unmount()
  })

  it('renders returned discovery results and performs one fetch for a page change', async () => {
    const second = { ...ualProgram, id: 'ual-program-2', name: 'Another official Master' }
    api.programs
      .mockResolvedValueOnce({ items: [ualProgram], page: 1, page_size: 12, total_items: 13, total_pages: 2 })
      .mockResolvedValueOnce({ items: [second], page: 2, page_size: 12, total_items: 13, total_pages: 2 })
    const { app, container } = await mountView({ render: () => h(RouterView) }, '/discover')
    expect(container.textContent).toContain(ualProgram.name)
    expect(container.textContent).toContain('13 programs')
    expect(api.programs).toHaveBeenCalledTimes(1)

    const next = [...container.querySelectorAll('button')].find((button) => button.textContent?.includes('Next'))
    expect(next).toBeDefined()
    next?.click()
    await flushView()
    expect(api.programs).toHaveBeenCalledTimes(2)
    expect(api.programs.mock.calls[1][0]).toMatchObject({ page: 2 })
    expect(container.textContent).toContain(second.name)
    app.unmount()
  })

  it('fetches once per filter, sort, and route-query change', async () => {
    const { app, container, router } = await mountView({ render: () => h(RouterView) }, '/discover')
    const language = container.querySelector<HTMLSelectElement>('#filter-language')
    expect(language).not.toBeNull()
    if (language) {
      language.value = 'english'
      language.dispatchEvent(new Event('change', { bubbles: true }))
    }
    await flushView()
    expect(api.programs).toHaveBeenCalledTimes(2)
    expect(api.programs.mock.calls[1][0]).toMatchObject({ language: 'english', page: 1 })

    const sort = container.querySelector<HTMLSelectElement>('#filter-sort')
    expect(sort).not.toBeNull()
    if (sort) {
      sort.value = 'tuition'
      sort.dispatchEvent(new Event('change', { bubbles: true }))
    }
    await flushView()
    expect(api.programs).toHaveBeenCalledTimes(3)
    expect(api.programs.mock.calls[2][0]).toMatchObject({ language: 'english', sort: 'tuition' })

    await router.push('/discover?page=2&sort=country&order=desc')
    await flushView()
    expect(api.programs).toHaveBeenCalledTimes(4)
    expect(api.programs.mock.calls[3][0]).toMatchObject({ page: 2, sort: 'country', order: 'desc' })
    app.unmount()
  })

  it('does not let an older catalogue response replace the latest results', async () => {
    let finishFirst: ((value: ReturnType<typeof page>) => void) | undefined
    api.programs
      .mockImplementationOnce(() => new Promise<ReturnType<typeof page>>((resolve) => { finishFirst = resolve }))
      .mockResolvedValueOnce(page([{ ...ualProgram, id: 'new-result', name: 'Latest result' }]))
    const { app, container } = await mountView({ render: () => h(RouterView) }, '/discover')

    const language = container.querySelector<HTMLSelectElement>('#filter-language')
    if (language) {
      language.value = 'english'
      language.dispatchEvent(new Event('change', { bubbles: true }))
    }
    await flushView()
    expect(container.textContent).toContain('Latest result')

    finishFirst?.(page([{ ...ualProgram, id: 'old-result', name: 'Stale result' }]))
    await flushView()
    expect(container.textContent).toContain('Latest result')
    expect(container.textContent).not.toContain('Stale result')
    app.unmount()
  })

  it('keeps loading, error, and empty responses distinct', async () => {
    let finishLoad: ((value: ReturnType<typeof page>) => void) | undefined
    api.programs.mockImplementationOnce(() => new Promise<ReturnType<typeof page>>((resolve) => { finishLoad = resolve }))
    const loading = await mountView({ render: () => h(RouterView) }, '/discover')
    expect(loading.container.querySelector('[aria-label="Loading"]')).not.toBeNull()
    expect(loading.container.textContent).not.toContain('No programs match')
    finishLoad?.({ items: [], page: 1, page_size: 12, total_items: 0, total_pages: 0 })
    await flushView()
    expect(loading.container.textContent).toContain('No programs match')
    loading.app.unmount()

    api.programs.mockRejectedValueOnce(new TypeError('network down'))
    const failed = await mountView({ render: () => h(RouterView) }, '/discover')
    expect(failed.container.textContent).toContain('Could not load this content')
    failed.app.unmount()

    api.programs.mockResolvedValueOnce({ items: [], page: 1, page_size: 12, total_items: 0, total_pages: 0 })
    const empty = await mountView({ render: () => h(RouterView) }, '/discover')
    expect(empty.container.textContent).toContain('No programs match')
    expect(empty.container.textContent).not.toContain('Could not load this content')
    empty.app.unmount()
  })

  it('renders program details when field, city, study mode, language, duration and intake are unknown', async () => {
    const detail: ProgramDetail = {
      ...ualProgram,
      description: null,
      official_program_url: 'https://ual.example.test/programs/masters/test',
      intakes: [],
      fees: [],
      requirements: [],
      campus: null,
    }
    api.program.mockResolvedValue(detail)
    const { app, container } = await mountView({ render: () => h(RouterView) }, '/programs/ual-program-1')
    const text = container.textContent ?? ''
    expect(text).toContain('Field not available')
    expect(text).toContain('City not available')
    expect(text).toContain('Study mode not specified')
    expect(text).toContain('Language not specified')
    expect(text).toContain('Duration not available')
    expect(text).toContain('intake and deadline not available')
    const requirementsTab = [...container.querySelectorAll('button')]
      .find((button) => button.textContent?.trim() === 'Requirements')
    requirementsTab?.click()
    await flushView()
    expect(container.textContent).toContain('No admission requirements published')
    const feesTab = [...container.querySelectorAll('button')]
      .find((button) => button.textContent?.trim() === 'Fees')
    feesTab?.click()
    await flushView()
    expect(container.textContent).toContain('No fees published yet')
    expect(text).not.toMatch(/\b(null|undefined|NaN)\b/)
    app.unmount()
  })

  it.each(['verified', 'unverified_candidate', 'unavailable'] as const)(
    'distinguishes a %s official page from limited academic data without changing UUID routing', async (status) => {
      const id = '2fffabd2-fd80-43d9-a6a8-6d0e9d6702c8'
      const detail: ProgramDetail = {
        ...ualProgram, id, name: 'Máster en Comunicación Social', slug: 'm-ster-en-comunicaci-n-social',
        data_quality: { status: 'unavailable', last_verified_at: null,
          warnings: ['tuition_not_available', 'requirements_not_verified', 'intake_deadline_unknown', 'future_source_warning'] },
        academic_completeness: { status: 'limited', verified_count: 0, field_count: 7,
          fields: { tuition: 'unavailable' }, warnings: ['duration_not_available'] },
        official_program_url_status: status,
        official_program_url: status === 'verified' ? 'https://ual.es/estudios/masteres/presentacion/7101' : null,
        description: null, intakes: [], fees: [], requirements: [], campus: null,
      }
      api.program.mockResolvedValue(detail)
      const { app, container, router } = await mountView({ render: () => h(RouterView) }, `/programs/${id}`)
      const text = container.textContent ?? ''
      expect(text).toContain('Official program page:')
      expect(text).toContain(status === 'verified' ? 'Verified' : status === 'unverified_candidate' ? 'Candidate (not verified)' : 'Not available')
      expect(text).toContain('Academic information: Limited')
      expect(text).toContain('Tuition is not available.')
      expect(text).toContain('Admission requirements are not verified.')
      expect(text).toContain('Application deadline is unknown.')
      expect(text).toContain('Future source warning.')
      expect(text).not.toContain('tuition_not_available')
      expect(text).not.toContain('Data quality - unavailable')
      expect(text).toContain('No description published yet.')
      expect(router.currentRoute.value.path).toBe(`/programs/${id}`)
      expect(api.program).toHaveBeenCalledWith(id)
      expect(container.querySelector('a[href="https://ual.es/estudios/masteres/presentacion/7101"]') !== null).toBe(status === 'verified')
      app.unmount()
    },
  )

  it('shows reviewed description attribution and retrieval information', async () => {
    api.program.mockResolvedValue({ ...ualProgram,
      description: 'An independently written and reviewed programme summary.',
      description_source: { source_url: 'https://ual.es/estudios/masteres/presentacion/7101',
        attribution: 'Universidad de Almería', retrieved_at: '2026-10-22T00:00:00Z' },
      official_program_url: null, intakes: [], fees: [], requirements: [], campus: null,
    })
    const { app, container } = await mountView({ render: () => h(RouterView) }, '/programs/ual-program-1')
    expect(container.textContent).toContain('An independently written and reviewed programme summary.')
    expect(container.textContent).toContain('Reviewed summary based on')
    expect(container.textContent).toContain('Universidad de Almería')
    expect(container.textContent).toContain('source checked')
    app.unmount()
  })
})
