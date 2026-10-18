/**
 * Response types for the University Shortlisting Tool API.
 *
 * Hand-mirrored from API_Contract.md and the live response shapes
 * (OpenAPI only describes request bodies, since service responses are plain
 * dicts). Keep in sync with backend serializers when they change.
 */

// ---------------------------------------------------------------- conventions

export interface Paginated<T> {
  items: T[]
  page: number
  page_size: number
  total_items: number
  total_pages: number
}

export interface ErrorDetail {
  field: string | null
  code: string
  message: string
}

export interface ApiErrorBody {
  code: string
  message: string
  request_id: string | null
  details: ErrorDetail[]
}

/** Provenance attached to every published fact cell. */
export interface SourceRef {
  source_id: string | null
  title: string | null
  url: string | null
  retrieved_at: string | null
  verified_at: string | null
}

/** Money cell: value may be null (unknown) - never rendered as zero. */
export interface MoneyCell {
  value: number | null
  unit: string | null
  period: string | null
  academic_year: string | null
  applicable_intake: string | null
  status: string
  source: SourceRef | null
}

export interface DataQuality {
  status: string
  last_verified_at: string | null
  warnings: string[]
}

export type EligibilityStatus =
  | 'eligible'
  | 'conditionally_eligible'
  | 'ineligible'
  | 'unknown_needs_review'
  | null

// ------------------------------------------------------------------- identity

export interface AuthUser {
  id: string
  email: string
  display_name: string | null
  roles: string[]
}

export interface CountryPreference {
  country_code: string
  preference_rank: number
  is_mandatory: boolean
}

export interface Profile {
  id: string
  user_id: string
  intended_degree_level: string | null
  field_key: string | null
  country_mode: string | null
  risk_tolerance: string | null
  academic_degree: string | null
  academic_major: string | null
  institution_name: string | null
  grade_value: number | null
  grade_scale_min: number | null
  grade_scale_max: number | null
  grade_system: string | null
  graduation_status: string | null
  graduation_year: number | null
  backlog_count: number | null
  english_test_status: string | null
  english_test_type: string | null
  english_test_overall: number | null
  english_test_component_scores: Record<string, number> | null
  other_test_scores: Record<string, number> | null
  work_experience_months: number | null
  projects_summary: string | null
  career_goal: string | null
  budget_amount: number | null
  budget_currency: string | null
  budget_basis: string | null
  target_intake_year: number | null
  target_intake_term: string | null
  profile_completed_at: string | null
  country_preferences: CountryPreference[]
  priorities: { key: string; weight: number | null }[]
}

export interface Completeness {
  required_complete: boolean
  optional_complete: boolean
  percentage: number
  items: { key: string; label: string; required: boolean; complete: boolean }[]
}

// -------------------------------------------------------------------- catalogue

export interface FieldRef {
  key: string
  display_name: string
}

export interface UniversityRef {
  id: string
  name: string
  country_code: string
  recognition_status: string
  city: string
}

export interface NearestIntake {
  intake_year: number
  intake_term: string
  application_deadline: string | null
  is_open_for_applications: boolean
}

export interface ProgramSummary {
  id: string
  name: string
  slug: string
  degree_level: string
  field: FieldRef
  country_code: string
  duration_min_months: number
  duration_max_months: number
  duration_months: number
  language: string
  study_mode: string
  university: UniversityRef
  nearest_intake: NearestIntake | null
  tuition_summary: MoneyCell
  data_quality: DataQuality
}

export interface ProgramFee {
  id: string
  fee_type: string
  amount: number | null
  currency: string | null
  period: string | null
  academic_year: string | null
  student_category: string | null
  is_mandatory: boolean
  status: string
  provenance: {
    status: string
    version_number: number
    value: unknown
    extraction_method: string | null
    source: SourceRef | null
  } | null
}

export interface ProgramRequirement {
  id: string
  requirement_type: string
  requirement_key: string
  operator: string
  expected_value: { scale: string | null; value: number | string | null } | null
  is_mandatory: boolean
  group_key: string | null
  group_operator: string | null
  applicability_notes: string | null
  evidence: { status: string; source: SourceRef | null }
}

export interface ProgramIntake {
  id: string
  intake_year: number
  intake_term: string
  application_open_date: string | null
  application_deadline: string | null
  start_date: string | null
  is_open_for_applications: boolean
  status: string
}

export interface ProgramDetail extends ProgramSummary {
  description: string | null
  official_program_url: string | null
  intakes: ProgramIntake[]
  fees: ProgramFee[]
  requirements: ProgramRequirement[]
  campus: { id: string | null; name: string | null; city: string | null }
}

export interface EvidenceVersion {
  version_number: number
  value: unknown
  status: string
  extraction_method: string | null
  applicable_intake_year: number | null
  applicable_intake_term: string | null
  created_at: string | null
}

export interface EvidenceSource {
  source_id: string | null
  title: string | null
  url: string | null
  retrieved_at: string | null
  excerpt: string | null
  supports_or_conflicts: string
}

export interface EvidenceItem {
  fact_id: string
  fact_key: string
  applicability_key: string
  current_status: string
  current_version_id: string | null
  versions: EvidenceVersion[]
  sources: EvidenceSource[]
}

export interface ProgramOutcome {
  metric_key: string
  metric_value: number
  metric_unit: string
  currency: string | null
  cohort_label: string | null
  cohort_year: number | null
  sample_size: number | null
  population_scope: string
  methodology_note: string | null
  applies_to_this_program: boolean
  provenance: unknown
}

// ------------------------------------------------------------ eligibility / runs

export interface EligibilityOutcome {
  requirement_id: string
  requirement_key: string
  requirement_type: string
  is_mandatory: boolean
  group_key: string | null
  operator: string
  expected_value: unknown
  status: string
  evaluated_value: unknown
  explanation: string | null
}

export interface EligibilityEvaluation {
  program_id: string
  program_name: string
  status: string
  requirements: EligibilityOutcome[]
  groups: { group_key: string; group_operator: string; status: string; requirement_keys: string[] }[]
  unsatisfied: string[]
  unknowns: string[]
  conditions: string[]
}

export interface RecommendationItem {
  id: string
  program_id: string
  program_name: string
  university: string
  country_code: string
  tier: string | null
  eligibility_status: string
  fit_score: number | null
  reason_codes: string[]
  concerns: string[]
  missing_information: string[]
}

export type TierKey = 'ambitious' | 'target' | 'safer_fit'

export interface RecommendationRun {
  run_id: string
  created_at: string | null
  status: string
  ruleset_version: string | null
  tiers: Record<TierKey, RecommendationItem[]>
  excluded_count: number
  data_warnings: string[]
  result_summary: Record<TierKey, number> | null
}

export interface RunListItem {
  run_id: string
  created_at: string | null
  status: string
  result_summary: Record<TierKey, number> | null
  ruleset_version: string | null
}

export interface ScoreBreakdownEntry {
  dimension: string
  weight: number
  score: number | null
  note: string | null
}

export interface ExplanationEntry extends RecommendationItem {
  score_breakdown: ScoreBreakdownEntry[]
  why: {
    reasons: string[]
    concerns: string[]
    missing_information: string[]
    hard_constraint_status: string
    requirement_outcomes: {
      requirement_id: string
      status: string
      applicant_value: unknown
      expected: unknown
      explanation: string | null
    }[]
  }
}

export interface ExplanationsResponse {
  run_id: string
  ruleset_version: string | null
  items: ExplanationEntry[]
  data_warnings: string[]
}

// ---------------------------------------------------------------- comparison

export interface CompareItem {
  program_id: string
  name: string
  university: string
  country_code: string
  degree_level: string
  duration_months: number
  language: string
  tuition: MoneyCell
  nearest_deadline: string | null
  requirements_total: number
  requirements_unverified: number
  recognition_status: string
  eligibility_status: EligibilityStatus
  data_quality: DataQuality
}

export interface CompareResponse {
  items: CompareItem[]
  count: number
}

export interface Comparison {
  id: string
  title: string
  created_at: string | null
  updated_at: string | null
  program_ids: string[]
  positions: Record<string, number>
}

export interface SavedProgram {
  program_id: string
  note: string | null
  saved_at: string | null
  program: ProgramSummary
}

// ------------------------------------------------------------------- finance

export interface CostItem {
  cost_type: string
  label: string
  amount: number | null
  currency: string | null
  period: string | null
  status: string
  note: string | null
  /** Present when the amount was converted from another currency. */
  converted_from?: string
}

export interface CostAssumptions {
  scenario: string
  tuition_period: string | null
  duration_months: number | null
  currency_conversion: string | null
}

export interface CostEstimate {
  program_id: string
  scenario: string
  currency: string
  items: CostItem[]
  total: number | null
  total_status: string
  funding_amount: number | null
  funding_currency: string | null
  funding_gap: number | null
  assumptions: CostAssumptions
  calculation_version: string
  data_warnings: string[]
}

export interface CostScenariosResponse {
  program_id: string
  scenarios: Record<'low' | 'base' | 'high', CostEstimate>
}

export interface ScholarshipAmount {
  min: number | null
  max: number | null
  currency: string
  status: string
}

export interface ScholarshipRule {
  rule_key: string
  operator: string
  expected_value: unknown
  is_mandatory: boolean
  group_key: string | null
}

export interface Scholarship {
  id: string
  name: string
  provider_name: string
  official_url: string | null
  country_code: string | null
  award_type: string | null
  amount: ScholarshipAmount
  coverage_type: string | null
  renewable: boolean
  deadline: string | null
  status: string
  eligibility_rules: ScholarshipRule[]
}

export interface ScholarshipDetail extends Scholarship {
  linked_program_ids: string[]
}

export interface ScholarshipMatch {
  scholarship_id: string
  name: string
  provider_name: string
  match_status: string
  outcomes: { rule: string; status: string; explanation: string }[]
  concerns: string[]
  unverified: string[]
  amount: { min: number | null; max: number | null; currency: string }
  deadline: string | null
  official_url: string | null
  program_id: string | null
}

export interface ScholarshipMatchesResponse {
  items: ScholarshipMatch[]
  note: string
}

export interface FundingOpportunity {
  id: string
  name: string
  provider_name: string
  opportunity_type: string
  official_url: string | null
  eligible_countries: string[]
  eligible_nationalities: string[]
  study_levels: string[]
  field_eligibility: string[]
  award_summary: string | null
  opening_date: string | null
  deadline: string | null
  status: string
}

export interface LoanInputs {
  principal_amount: number
  currency: string
  annual_interest_rate: number
  tenure_months: number
  moratorium_months: number
  interest_during_moratorium: string
  repayment_method: string
}

export interface ScheduleRow {
  month: number
  emi: number
  interest: number
  principal: number
  closing_balance: number
}

export interface LoanResults {
  emi: number
  repayment_months: number
  principal_after_moratorium: number
  moratorium_interest: number
  total_interest: number
  total_payable: number
  schedule: ScheduleRow[]
}

export interface LoanScenario {
  id: string
  name: string
  inputs: LoanInputs
  results: LoanResults
  interest_method: string
  assumptions: string[]
  calculation_version: string
  created_at: string | null
  disclaimer: string
}

export interface RoiResults {
  payback_months: number | null
  payback_status: string
  monthly_surplus?: number | null
  discounted_net_present_value?: number | null
  warnings?: string[]
}

export interface RoiScenario {
  id: string
  name: string
  program_id: string | null
  currency: string
  scope: string
  input_provenance: string
  inputs: {
    education_cost: number | null
    expected_annual_income: number | null
    employment_delay_months: number
    annual_expenses: number | null
    discount_rate: number | null
  }
  results: RoiResults
  assumptions: Record<string, unknown> | null
  calculation_version?: string
  created_at: string | null
  disclaimer: string
}

// -------------------------------------------------------------- destinations

export interface Country {
  code: string
  name: string
  region: string
  official_study_url: string | null
  official_immigration_url: string | null
  city_count: number
  university_count: number
}

export interface CityRef {
  id: string
  name: string
  slug: string
  country_code: string
  admin_region: string | null
}

export interface CountryDetail extends Omit<Country, 'city_count' | 'university_count'> {
  cities: CityRef[]
  official_rules: OfficialRule[]
}

export interface OfficialRule {
  id: string
  country_code: string | null
  rule_type: string
  title: string
  official_url: string | null
  summary: string | null
  effective_from: string | null
  effective_to: string | null
  last_checked_at: string | null
  freshness_note: string | null
}

export interface LivingCost {
  category: string
  min: number
  typical: number
  max: number
  currency: string
  period: string
  effective_year: number
  status: string
}

export interface CityDetail extends CityRef {
  living_costs: LivingCost[]
  living_cost_year: number | null
}

export interface OutcomeEvidence {
  id: string
  program_id: string | null
  university_id: string | null
  field_id: string | null
  country_code: string | null
  metric_key: string
  metric_value: number
  metric_unit: string
  currency: string | null
  cohort_label: string | null
  cohort_year: number | null
  sample_size: number | null
  population_scope: string
  methodology_note: string | null
  status: string
}

export interface OutcomesResponse extends Paginated<OutcomeEvidence> {
  scope_note: string
}

// --------------------------------------------------------------------- admin

export interface ReviewQueueItem {
  fact_id: string
  entity_type: string
  entity_id: string
  entity_label: string | null
  fact_key: string
  applicability_key: string
  current_status: string
  current_version_id: string | null
  current_value: unknown
  version_count: number
  evidence_count: number
  last_review: {
    action: string
    reason: string | null
    reviewer_user_id: string
    created_at: string
  } | null
}

export interface FactEvidenceDetail {
  evidence_id: string
  supports_or_conflicts: string
  excerpt: string | null
  locator: string | null
  reviewer_note: string | null
  source_document_id: string
  canonical_url: string | null
  retrieved_at: string | null
  fetch_status: string | null
  source: {
    id: string
    name: string
    authority_tier: number
    allowed_use_policy: string
  } | null
}

export interface FactVersionDetail {
  id: string
  version_number: number
  value: unknown
  normalized_value: unknown
  status: string
  effective_from: string | null
  effective_to: string | null
  applicable_intake_year: number | null
  applicable_intake_term: string | null
  extraction_method: string | null
  extraction_confidence: number | null
  reviewed_by_user_id: string | null
  reviewed_at: string | null
  review_reason: string | null
  created_by_user_id: string | null
  created_at: string
  evidence: FactEvidenceDetail[]
}

export interface FactDetail {
  fact_id: string
  entity_type: string
  entity_id: string
  entity_label: string | null
  fact_key: string
  applicability_key: string
  current_status: string
  current_version_id: string | null
  versions: FactVersionDetail[]
  review_events: {
    id: string
    fact_version_id: string | null
    action: string
    reason: string | null
    reviewer_user_id: string
    created_at: string
  }[]
}

export interface FactActionResult {
  fact_id: string
  version_id?: string
  action: string
  current_status: string
  version_status?: string
  reviewed_by_user_id?: string
}

export interface Source {
  id: string
  name: string
  base_url: string
  source_type: string
  authority_tier: number
  owner_or_publisher: string | null
  allowed_use_policy: string
  terms_url: string | null
  robots_policy_checked_at: string | null
  rate_limit_notes: string | null
  license_notes: string | null
  refresh_interval_hours: number | null
  enabled: boolean
  metadata: Record<string, unknown>
  created_at: string | null
  updated_at: string | null
  document_count?: number
  job_count?: number
}

export interface SourceDetail extends Source {
  documents: {
    id: string
    canonical_url: string | null
    title: string | null
    document_type: string | null
    fetch_status: string | null
    http_status: number | null
    retrieved_at: string | null
  }[]
  recent_jobs: Job[]
}

export interface Job {
  id: string
  source_id: string | null
  job_type: string
  status: string
  started_at: string | null
  finished_at: string | null
  records_seen: number
  records_created: number
  records_updated: number
  records_rejected: number
  error_summary: string | null
  worker_version: string | null
  created_by_user_id: string | null
  created_at: string | null
  reused?: boolean
}

export interface JobDetail extends Job {
  items: {
    id: string
    source_document_id: string | null
    entity_type: string | null
    external_key: string | null
    status: string
    validation_errors: Record<string, unknown> | null
    fact_record_id: string | null
  }[]
}

export interface AuditEvent {
  id: string
  actor_user_id: string | null
  actor_type: string
  action: string
  entity_type: string | null
  entity_id: string | null
  request_id: string | null
  reason: string | null
  before_summary: Record<string, unknown> | null
  after_summary: Record<string, unknown> | null
  created_at: string
}

export interface MetaResponse {
  name: string
  version: string
  environment: string
  base_path: string
  features: Record<string, boolean>
}
