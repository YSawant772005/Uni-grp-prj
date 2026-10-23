import { describe, expect, it } from 'vitest'
import { isSubstantivePublicationReason } from '../utils/publicationReason'

describe('publication review reason validation', () => {
  it.each(['', '   ', 'good', 'checking', 'This is a good reason to publish this program.'])('rejects missing, generic, or unsupported reasons: %s', (reason) => {
    expect(isSubstantivePublicationReason(reason)).toBe(false)
  })

  it('accepts a specific source and identity review explanation', () => {
    expect(isSubstantivePublicationReason(
      'The official source document confirms this program identity and catalogue entry.',
    )).toBe(true)
  })
})
