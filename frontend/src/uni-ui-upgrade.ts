/** Non-invasive styling scope for the user-facing workspace only. */
import { router } from './router'
import './styles/ui-upgrade.css'

const SCREENS = new Set([
  'discover', 'profile', 'saved', 'shortlist', 'shortlist-run', 'compare',
  'finance', 'roi', 'destination-country', 'program-detail',
  'destinations', 'destination-city', 'scholarships', 'loans', 'settings',
])

router.afterEach((to) => {
  const screen = String(to.name ?? '')
  if (SCREENS.has(screen)) {
    document.body.dataset.uniPolishRoute = screen
  } else {
    delete document.body.dataset.uniPolishRoute
  }
})
