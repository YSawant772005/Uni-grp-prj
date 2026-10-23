import { describe, expect, it, vi } from 'vitest'
import { createApp, nextTick } from 'vue'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import FactDetailView from '../features/admin/FactDetailView.vue'

const api = vi.hoisted(() => ({ fact: vi.fn(), approveFact: vi.fn() }))
vi.mock('../services/api/admin', () => ({ admin: api }))

async function settle() {
  for (let i = 0; i < 10; i += 1) await Promise.resolve()
  await nextTick()
}

describe('description evidence review', () => {
  it('requires explicit reviewer text and reason and sends them through existing fact approval', async () => {
    api.fact.mockResolvedValue({ id: 'description-fact', fact_key: 'program_description', entity_type: 'program',
      current_status: 'candidate', current_version_id: 'candidate-version', applicability_key: '', review_events: [],
      versions: [{ id: 'candidate-version', version_number: 1, status: 'candidate', evidence: [],
        value: { source_excerpt: 'Official reference passage for review.', summary: null },
        extraction_method: 'parser', extraction_confidence: null }],
    })
    api.approveFact.mockResolvedValue({ current_status: 'verified' })
    const router = createRouter({ history: createMemoryHistory(), routes: [
      { path: '/admin/review/:factId', component: FactDetailView },
      { path: '/admin/review', component: { template: '<div>Queue</div>' } },
    ] })
    await router.push('/admin/review/description-fact')
    await router.isReady()
    const container = document.createElement('div')
    document.body.append(container)
    const app = createApp(FactDetailView)
    app.use(createPinia()).use(router).mount(container)
    await settle()
    const click = (label: string) => [...container.querySelectorAll('button')]
      .find((button) => button.textContent?.trim() === label)?.click()
    click('Verify fact version')
    await settle()
    click('Confirm')
    await settle()
    expect(api.approveFact).not.toHaveBeenCalled()
    expect(container.textContent).toContain('Write an independent description summary')
    const summary = container.querySelector<HTMLTextAreaElement>('#description-summary')!
    summary.value = 'An independently written programme summary grounded in the official description.'
    summary.dispatchEvent(new Event('input', { bubbles: true }))
    const reason = container.querySelector<HTMLTextAreaElement>('#reason-approve')!
    reason.value = 'The official source evidence supports this independently written summary.'
    reason.dispatchEvent(new Event('input', { bubbles: true }))
    await settle()
    click('Confirm')
    await settle()
    expect(api.approveFact).toHaveBeenCalledWith('description-fact', {
      version_id: 'candidate-version', description_summary: summary.value, reason: reason.value,
    })
    app.unmount()
    container.remove()
  })
})
