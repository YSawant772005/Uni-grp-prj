import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useUiStore } from '../stores/ui'

/**
 * Redirect targets must be local paths: prevents open-redirect via the
 * `redirect` query parameter (UI doc section 4).
 */
export function safeRedirect(raw: unknown): string | null {
  if (typeof raw !== 'string' || raw.length === 0) return null
  if (!raw.startsWith('/') || raw.startsWith('//') || raw.includes('\\')) return null
  return raw
}

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: () => import('../layouts/PublicLayout.vue'),
    children: [
      {
        path: '',
        name: 'landing',
        component: () => import('../features/static/LandingView.vue'),
        meta: { title: 'Evidence-first shortlisting' },
      },
      {
        path: 'privacy',
        name: 'privacy',
        component: () => import('../features/static/PrivacyView.vue'),
        meta: { title: 'Privacy' },
      },
      {
        path: 'terms',
        name: 'terms',
        component: () => import('../features/static/TermsView.vue'),
        meta: { title: 'Terms' },
      },
    ],
  },
  {
    path: '/',
    component: () => import('../layouts/BareLayout.vue'),
    children: [
      {
        path: 'login',
        name: 'login',
        component: () => import('../features/auth/LoginView.vue'),
        meta: { title: 'Log in', guestOnly: true },
      },
      {
        path: 'signup',
        name: 'signup',
        component: () => import('../features/auth/SignupView.vue'),
        meta: { title: 'Create your account', guestOnly: true },
      },
      {
        path: 'onboarding',
        name: 'onboarding',
        component: () => import('../features/onboarding/OnboardingView.vue'),
        meta: { title: 'Build your profile', requiresAuth: true },
      },
    ],
  },
  {
    path: '/',
    component: () => import('../layouts/AppLayout.vue'),
    children: [
      {
        path: 'profile',
        name: 'profile',
        component: () => import('../features/profile/ProfileView.vue'),
        meta: { title: 'Your profile', requiresAuth: true },
      },
      {
        path: 'discover',
        name: 'discover',
        component: () => import('../features/discovery/DiscoverView.vue'),
        meta: { title: 'Discover programs' },
      },
      {
        path: 'programs/:programId',
        name: 'program-detail',
        component: () => import('../features/program-detail/ProgramDetailView.vue'),
        meta: { title: 'Program details' },
      },
      {
        path: 'shortlist',
        name: 'shortlist',
        component: () => import('../features/shortlist/ShortlistView.vue'),
        meta: { title: 'Your shortlist', requiresAuth: true },
      },
      {
        path: 'shortlist/:runId',
        name: 'shortlist-run',
        component: () => import('../features/shortlist/RunDetailView.vue'),
        meta: { title: 'Shortlist results', requiresAuth: true },
      },
      {
        path: 'compare',
        name: 'compare',
        component: () => import('../features/comparison/CompareView.vue'),
        meta: { title: 'Compare programs' },
      },
      {
        path: 'saved',
        name: 'saved',
        component: () => import('../features/saved/SavedView.vue'),
        meta: { title: 'Saved programs', requiresAuth: true },
      },
      {
        path: 'finance',
        name: 'finance',
        component: () => import('../features/finance/FinanceView.vue'),
        meta: { title: 'Cost estimates' },
      },
      {
        path: 'scholarships',
        name: 'scholarships',
        component: () => import('../features/scholarships/ScholarshipsView.vue'),
        meta: { title: 'Scholarships and funding' },
      },
      {
        path: 'loans',
        name: 'loans',
        component: () => import('../features/loans/LoansView.vue'),
        meta: { title: 'Loan scenarios', requiresAuth: true },
      },
      {
        path: 'roi',
        name: 'roi',
        component: () => import('../features/roi/RoiView.vue'),
        meta: { title: 'Career evidence and ROI' },
      },
      {
        path: 'destinations',
        name: 'destinations',
        component: () => import('../features/destinations/DestinationsIndexView.vue'),
        meta: { title: 'Destination guides' },
      },
      {
        path: 'destinations/:countryCode',
        name: 'destination-country',
        component: () => import('../features/destinations/CountryGuideView.vue'),
        meta: { title: 'Country guide' },
      },
      {
        path: 'destinations/:countryCode/:citySlug',
        name: 'destination-city',
        component: () => import('../features/destinations/CityGuideView.vue'),
        meta: { title: 'City guide' },
      },
      {
        path: 'settings',
        name: 'settings',
        component: () => import('../features/settings/SettingsView.vue'),
        meta: { title: 'Settings', requiresAuth: true },
      },
    ],
  },
  {
    path: '/admin',
    component: () => import('../layouts/AdminLayout.vue'),
    children: [
      {
        path: '',
        name: 'admin',
        component: () => import('../features/admin/AdminHomeView.vue'),
        meta: { title: 'Admin console', roles: ['reviewer', 'admin'] },
      },
      {
        path: 'review',
        name: 'admin-review',
        component: () => import('../features/admin/ReviewQueueView.vue'),
        meta: { title: 'Review queue', roles: ['reviewer', 'admin'] },
      },
      {
        path: 'review/:factId',
        name: 'admin-fact',
        component: () => import('../features/admin/FactDetailView.vue'),
        meta: { title: 'Fact review', roles: ['reviewer', 'admin'] },
      },
      {
        path: 'identity-reviews',
        name: 'admin-identity-reviews',
        component: () => import('../features/admin/IdentityReviewView.vue'),
        meta: { title: 'Institution identity review', roles: ['reviewer', 'admin'] },
      },
      {
        path: 'institution-reviews',
        name: 'admin-institution-reviews',
        component: () => import('../features/admin/InstitutionReviewView.vue'),
        meta: { title: 'Institution approval review', roles: ['reviewer', 'admin'] },
      },
      {
        path: 'institution-reviews/:universityId',
        name: 'admin-institution-review',
        component: () => import('../features/admin/InstitutionReviewView.vue'),
        meta: { title: 'Institution review detail', roles: ['reviewer', 'admin'] },
      },
      {
        path: 'program-publication',
        name: 'admin-program-publication',
        component: () => import('../features/admin/ProgramPublicationView.vue'),
        meta: { title: 'Program publication review', roles: ['reviewer', 'admin'] },
      },
      {
        path: 'sources',
        name: 'admin-sources',
        component: () => import('../features/admin/SourcesView.vue'),
        meta: { title: 'Source registry', roles: ['reviewer', 'admin'] },
      },
      {
        path: 'sources/:sourceId',
        name: 'admin-source',
        component: () => import('../features/admin/SourceDetailView.vue'),
        meta: { title: 'Source details', roles: ['reviewer', 'admin'] },
      },
      {
        path: 'jobs',
        name: 'admin-jobs',
        component: () => import('../features/admin/JobsView.vue'),
        meta: { title: 'Ingestion jobs', roles: ['admin'] },
      },
      {
        path: 'audit',
        name: 'admin-audit',
        component: () => import('../features/admin/AuditView.vue'),
        meta: { title: 'Audit log', roles: ['admin'] },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('../features/static/NotFoundView.vue'),
    meta: { title: 'Page not found' },
  },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(_to, _from, saved) {
    return saved ?? { top: 0 }
  },
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  await auth.ensureLoaded()

  if (to.meta.guestOnly && auth.isAuthenticated) {
    return safeRedirect(to.query.redirect) ?? '/'
  }

  const requiresAuth = to.matched.some((record) => record.meta.requiresAuth)
  if (requiresAuth && !auth.isAuthenticated) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  // role gate mirrors backend require_roles (OR across listed roles);
  // the backend remains the authoritative check for every request.
  const roles = (to.meta.roles as string[] | undefined) ?? []
  if (roles.length > 0 && !roles.some((role) => auth.roleKeys.includes(role))) {
    useUiStore().push('You do not have permission to open that page.', 'error')
    return { path: '/' }
  }

  return true
})

router.afterEach((to) => {
  const title = (to.meta.title as string | undefined) ?? 'Page not found'
  document.title = `${title} · University Shortlisting Tool`
})
