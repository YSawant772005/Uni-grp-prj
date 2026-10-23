const evidenceTerms = new Set([
  'source', 'evidence', 'official', 'identity', 'document', 'catalogue', 'institution',
  'university', 'requirement', 'page', 'retrieval', 'record', 'website', 'site', 'domain',
  'program', 'programme', 'course', 'degree', 'campus', 'identifier', 'location', 'name',
  'url', 'offering',
])
const rationaleTerms = new Set([
  'confirm', 'confirms', 'confirmed', 'support', 'supports', 'supported', 'contradict',
  'contradicts', 'contradicted', 'match', 'matches', 'matched', 'mismatch', 'missing',
  'changed', 'failed', 'requires', 'needs', 'because', 'establishes', 'indicates', 'conflict', 'conflicts', 'conflicting',
  'incomplete', 'incorrect', 'unavailable', 'verify', 'verifies', 'verified', 'verification',
  'cannot', 'could', 'unable', 'not', 'unresolved', 'shows',
])

/** Keep publication-review controls aligned with the backend's substantive-reason check. */
export function isSubstantivePublicationReason(reason: string | null | undefined): boolean {
  const normalized = (reason ?? '').trim().replace(/\s+/g, ' ')
  const words = normalized.toLocaleLowerCase().match(/[a-z0-9]+/g) ?? []
  return normalized.length >= 30
    && words.length >= 5
    && new Set(words).size >= 4
    && words.some((word) => evidenceTerms.has(word))
    && words.some((word) => rationaleTerms.has(word))
}
