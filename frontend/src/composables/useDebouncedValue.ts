import { onScopeDispose, ref, watch, type Ref } from 'vue'

/** Mirrors a ref after `delay` ms of quiet - used for search inputs. */
export function useDebouncedValue<T>(source: Ref<T>, delay = 350): Ref<T> {
  const debounced = ref(source.value) as Ref<T>
  let timer: ReturnType<typeof setTimeout> | undefined
  const stop = watch(source, (value) => {
    clearTimeout(timer)
    timer = setTimeout(() => {
      debounced.value = value
    }, delay)
  })
  onScopeDispose(() => {
    clearTimeout(timer)
    stop()
  })
  return debounced
}
