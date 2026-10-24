<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { request } from '../services/api/client'

interface CollegeOption {
  name: string
  country_code: string
  is_demo: boolean
  directory_reference?: boolean
}

const props = withDefaults(defineProps<{
  modelValue: string
  id?: string
  invalid?: boolean
}>(), { id: 'institution', invalid: false })
const emit = defineEmits<{ (event: 'update:modelValue', value: string): void }>()

const options = ref<CollegeOption[]>([])
const open = ref(false)
const loading = ref(false)
const unavailable = ref(false)
const active = ref(-1)
let timer: ReturnType<typeof setTimeout> | undefined
let sequence = 0

watch(() => props.modelValue, (value) => {
  if (timer) clearTimeout(timer)
  const token = ++sequence
  active.value = -1
  unavailable.value = false
  const term = value.trim()
  if (term.length < 2) {
    options.value = []
    loading.value = false
    return
  }
  loading.value = true
  timer = setTimeout(async () => {
    try {
      const response = await request<{ items: CollegeOption[] }>('/universities/search', {
        query: { q: term, limit: 12 },
      })
      if (sequence !== token) return
      options.value = response.items
    } catch {
      if (sequence !== token) return
      options.value = []
      unavailable.value = true
    } finally {
      if (sequence === token) loading.value = false
    }
  }, 280)
}, { immediate: true })

onBeforeUnmount(() => {
  if (timer) clearTimeout(timer)
  sequence += 1
})

function choose(option: CollegeOption) {
  emit('update:modelValue', option.name)
  open.value = false
  active.value = -1
}

function onInput(event: Event) {
  emit('update:modelValue', (event.target as HTMLInputElement).value)
  open.value = true
}

function onKeyDown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    open.value = false
    active.value = -1
  }
  if (event.key === 'ArrowDown' && options.value.length) {
    event.preventDefault()
    open.value = true
    active.value = (active.value + 1) % options.value.length
  }
  if (event.key === 'ArrowUp' && options.value.length) {
    event.preventDefault()
    open.value = true
    active.value = (active.value - 1 + options.value.length) % options.value.length
  }
  if (event.key === 'Enter' && open.value && active.value >= 0) {
    event.preventDefault()
    const option = options.value[active.value]
    if (option) choose(option)
  }
}
</script>

<template>
  <div class="uni-college-search">
    <div class="uni-college-search__field">
      <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="10.8" cy="10.8" r="6.5"/><path d="m16 16 4.5 4.5"/></svg>
      <input
        :id="id"
        :value="modelValue"
        type="search"
        autocomplete="off"
        placeholder="Search or enter your college / university"
        role="combobox"
        aria-autocomplete="list"
        :aria-controls="`${id}-options`"
        :aria-expanded="open && modelValue.trim().length >= 2"
        :aria-activedescendant="active >= 0 && open ? `${id}-option-${active}` : undefined"
        :aria-invalid="invalid"
        @input="onInput"
        @focus="open = true"
        @blur="open = false"
        @keydown="onKeyDown"
      />
      <span v-if="loading" class="uni-college-search__loading" role="status">Searching…</span>
    </div>
    <div v-if="open && modelValue.trim().length >= 2" :id="`${id}-options`" class="uni-college-search__results" role="listbox">
      <template v-if="options.length">
        <button
          v-for="(college, index) in options"
          :id="`${id}-option-${index}`"
          :key="`${college.country_code}-${college.name}`"
          type="button"
          class="uni-college-search__option"
          :class="{ 'is-active': active === index }"
          role="option"
          :aria-selected="active === index"
          @mousedown.prevent="choose(college)"
          @click="choose(college)"
        >
          <span class="uni-college-search__option-name">{{ college.name }}</span>
          <span class="uni-college-search__meta">{{ college.country_code }}<span v-if="college.is_demo" class="uni-college-search__demo">Fictional demo</span><span v-if="college.directory_reference" class="uni-college-search__reference">Directory reference</span></span>
        </button>
      </template>
      <p v-else-if="loading" class="uni-college-search__hint">Searching the college database…</p>
      <p v-else-if="unavailable" class="uni-college-search__hint">Search unavailable. You can still type your university's full name.</p>
      <p v-else class="uni-college-search__hint">No matches found. You can still enter your university's full name.</p>
    </div>
    <small class="uni-college-search__help">Search the available colleges, or type your institution manually if it isn't listed.</small>
  </div>
</template>

<style scoped>
.uni-college-search { position: relative; width: 100%; }
.uni-college-search__field { position: relative; display:flex; align-items:center; }
.uni-college-search__field > svg { position:absolute; z-index:1; left:14px; width:18px; height:18px; color:#078969; pointer-events:none; }
.uni-college-search__field > input { box-sizing:border-box; width:100%; min-height:46px; padding: 10px 96px 10px 42px; border-radius:10px; border:1px solid #d5e5df; background:#fff; color:#103b32; }
.uni-college-search__field > input:focus { border-color:#078969; outline:3px solid #d5f4e8; outline-offset:1px; }
.uni-college-search__loading { position:absolute; right:14px; font-size:12px; color:#66877c; pointer-events:none; }
.uni-college-search__results { position:absolute; z-index:80; left:0; right:0; top:calc(100% + 6px); max-height:280px; overflow:auto; padding:6px; background:#fff; border:1px solid #d7e6de; box-shadow:0 14px 38px rgba(19,67,53,.17); border-radius:12px; }
.uni-college-search__option { display:flex; justify-content:space-between; align-items:center; gap:12px; width:100%; border:0; border-radius:8px; text-align:left; background:#fff; padding:11px 12px; color:#143e33; cursor:pointer; font:inherit; }
.uni-college-search__option:hover,.uni-college-search__option.is-active { background:#eaf8f1; }
.uni-college-search__option-name { font-weight:600; font-size:13px; }
.uni-college-search__meta { flex:none; display:inline-flex; align-items:center; gap:6px; color:#718c83; font-size:11px; }
.uni-college-search__demo { display:inline-block; border-radius:20px; color:#8b6008; background:#fff3d7; padding:3px 7px; font-weight:700; }
.uni-college-search__hint { margin:0; padding:13px; color:#68827a; font-size:12px; }
.uni-college-search__help { display:block; margin-top:7px; color:#69857b; font-size:11px; line-height:1.55; }
@media(max-width:680px) { .uni-college-search__option { align-items:flex-start; flex-direction:column; gap:4px; } }
.uni-college-search__reference { display:inline-block; padding:3px 7px; border-radius:20px; background:#e8f4fe; color:#175078; font-size:11px; font-weight:700; }
</style>
