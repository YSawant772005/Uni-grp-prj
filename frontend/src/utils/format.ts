/** Presentation helpers shared across views. No business logic here. */

/** "data_science" -> "Data science"; null-safe. */
export function humanize(value: string | null | undefined): string {
  if (!value) return ''
  return value
    .split('_')
    .map((word, index) => (index === 0 ? word.charAt(0).toUpperCase() + word.slice(1) : word))
    .join(' ')
}

export function formatNumber(value: number | null | undefined, maxFraction = 2): string {
  if (value === null || value === undefined) return ''
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: maxFraction }).format(value)
}

/** Money formatting that never invents values: caller decides what to show for null. */
export function formatMoney(
  value: number | null | undefined,
  currency?: string | null,
): string {
  if (value === null || value === undefined) return ''
  if (!currency) return formatNumber(value)
  try {
    return new Intl.NumberFormat(undefined, {
      style: 'currency',
      currency,
      maximumFractionDigits: 0,
    }).format(value)
  } catch {
    return `${formatNumber(value)} ${currency.toUpperCase()}`
  }
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return ''
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return ''
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatDuration(months: number | null | undefined): string {
  if (!months) return ''
  const years = Math.floor(months / 12)
  const rest = months % 12
  const parts = [years ? `${years} yr` : '', rest ? `${rest} mo` : ''].filter(Boolean)
  return `${months} months (${parts.join(' ')})`
}

/** Pretty JSON for evidence values (objects/arrays only; primitives as-is). */
export function formatValue(value: unknown): string {
  if (value === null || value === undefined) return 'Not available'
  if (typeof value === 'object') return JSON.stringify(value, null, 2)
  return String(value)
}

/** Short one-line preview of a JSON value for tables. */
export function valuePreview(value: unknown, max = 60): string {
  const text =
    value !== null && typeof value === 'object' ? JSON.stringify(value) : String(value ?? '')
  return text.length > max ? `${text.slice(0, max - 1)}…` : text
}

/** Truncate with ellipsis for card copy. */
export function truncate(text: string | null | undefined, max = 200): string {
  if (!text) return ''
  return text.length > max ? `${text.slice(0, max - 1)}…` : text
}
