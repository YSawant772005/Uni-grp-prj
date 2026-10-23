import type { ProgramDetail, ProgramSummary } from '../types/api'
import { humanize } from './format'

export function pageStatus(program: ProgramSummary & Partial<Pick<ProgramDetail, 'official_program_url_status'>>) {
  const status = program.source_verification?.official_program_page_status ?? program.official_program_url_status
  if (status === 'verified' || status === 'demo_fixture') return status
  if (status === 'candidate' || status === 'unverified_candidate') return 'candidate'
  return status ? 'unavailable' : 'unknown'
}

export function academicLabel(program: ProgramSummary) {
  const status = program.academic_completeness?.status
  return status ? humanize(status) : 'Coverage not assessed'
}

const WARNINGS: Record<string, string> = {
  tuition_not_available: 'Tuition is not available.',
  tuition_not_verified: 'Tuition is not verified.',
  requirements_not_verified: 'Admission requirements are not verified.',
  admissions_requirements_not_available: 'Admission requirements are not available.',
  admissions_requirements_not_verified: 'Admission requirements are not verified.',
  intake_deadline_unknown: 'Application deadline is unknown.',
  application_deadline_not_available: 'Application deadline is unknown.',
  application_deadline_not_verified: 'Application deadline is not verified.',
  no_program_level_outcome_data: 'Programme-specific outcome data is not available.',
  program_outcomes_not_available: 'Programme-specific outcome data is not available.',
  program_outcomes_not_verified: 'Programme-specific outcome data is not verified.',
  duration_not_available: 'Duration is not available.',
  duration_not_verified: 'Duration is not verified.',
  teaching_language_not_available: 'Teaching language is not available.',
  teaching_language_not_verified: 'Teaching language is not verified.',
  intake_dates_not_available: 'Intake dates are not available.',
  intake_dates_not_verified: 'Intake dates are not verified.',
}

export function qualityWarnings(program: ProgramSummary) {
  return [...new Set([...program.data_quality.warnings, ...(program.academic_completeness?.warnings ?? [])]
    .map((code) => WARNINGS[code] ?? `${humanize(code)}.`))]
}
