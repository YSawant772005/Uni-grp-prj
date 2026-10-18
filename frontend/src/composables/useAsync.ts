import { ref, type Ref } from 'vue'

export interface AsyncState<T> {
  data: Ref<T | null>
  loading: Ref<boolean>
  /** The last error thrown by `fn`, if any (ApiError when it came from the API). */
  error: Ref<unknown>
  /** Runs the task; resolves to `null` on failure (error is stored, not thrown). */
  run: () => Promise<T | null>
}

/**
 * Loading/error/data lifecycle for a request, with race protection:
 * a slower older response never overwrites a newer one (safe cancellation
 * behaviour when navigating quickly between screens).
 */
export function useAsync<T>(
  fn: () => Promise<T>,
  options: { immediate?: boolean } = {},
): AsyncState<T> {
  const data = ref<T | null>(null) as Ref<T | null>
  const loading = ref(false)
  const error = ref<unknown>(null)
  let generation = 0

  async function run(): Promise<T | null> {
    const gen = ++generation
    loading.value = true
    error.value = null
    try {
      const result = await fn()
      if (gen === generation) data.value = result
      return result
    } catch (err) {
      if (gen === generation) error.value = err
      return null
    } finally {
      if (gen === generation) loading.value = false
    }
  }

  if (options.immediate) void run()

  return { data, loading, error, run }
}
