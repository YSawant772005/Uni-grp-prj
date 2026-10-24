<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import type { Country } from '../types/api'

const props = defineProps<{
  countries: Country[]
  selectedCodes: string[]
  disabled?: boolean
}>()
const emit = defineEmits<{ toggle: [code: string] }>()
const search = ref('')
const isOpen = ref(false)
const focusedIndex = ref(0)
const root = ref<HTMLElement | null>(null)
const input = ref<HTMLInputElement | null>(null)
const listId = 'preferred-country-options'

const selectedSet = computed(() => new Set(props.selectedCodes))
const matching = computed(() => {
  const needle = search.value.trim().toLocaleLowerCase()
  const source = needle
    ? props.countries.filter((c) => c.name.toLocaleLowerCase().includes(needle) || c.code.toLowerCase().includes(needle))
    : props.countries
  return source.slice(0, 90)
})
const selectedCountries = computed(() => props.selectedCodes.map((code) =>
  props.countries.find((c) => c.code === code) ?? { code, name: code },
))
const selectedCount = computed(() => selectedCountries.value.length)

watch(search, () => { focusedIndex.value = 0; isOpen.value = true })
watch(() => props.countries.length, () => { focusedIndex.value = 0 })

function choose(code: string) {
  if (props.disabled) return
  emit('toggle', code)
  search.value = ''
  isOpen.value = true
  focusedIndex.value = 0
  void nextTick(() => input.value?.focus())
}
function keydown(event: KeyboardEvent) {
  if (event.key === 'Escape') { isOpen.value = false; return }
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    isOpen.value = true
    focusedIndex.value = Math.min(focusedIndex.value + 1, matching.value.length - 1)
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    isOpen.value = true
    focusedIndex.value = Math.max(0, focusedIndex.value - 1)
  } else if (event.key === 'Enter' && isOpen.value && matching.value.length) {
    event.preventDefault()
    choose(matching.value[focusedIndex.value]?.code ?? matching.value[0]!.code)
  }
}
function onDocumentPointer(event: PointerEvent) {
  if (root.value && !root.value.contains(event.target as Node)) isOpen.value = false
}
document.addEventListener('pointerdown', onDocumentPointer)
onBeforeUnmount(() => document.removeEventListener('pointerdown', onDocumentPointer))
</script>

<template>
  <div ref="root" class="country-search">
    <div class="search-box">
      <span class="search-icon" aria-hidden="true">⌕</span>
      <input
        ref="input"
        v-model="search"
        type="search"
        autocomplete="off"
        role="combobox"
        aria-label="Search countries"
        :aria-controls="listId"
        :aria-expanded="isOpen"
        aria-autocomplete="list"
        :placeholder="`Search ${countries.length} countries by name...`"
        :disabled="disabled"
        @focus="isOpen = true"
        @keydown="keydown"
      />
      <span class="counter">{{ selectedCount }} selected</span>
    </div>
    <div v-if="isOpen && !disabled" :id="listId" class="options" role="listbox" aria-multiselectable="true">
      <div v-if="!matching.length" class="no-results">No countries match your search.</div>
      <button
        v-for="(country, index) in matching"
        :key="country.code"
        class="country-option"
        :class="{ highlighted: index === focusedIndex, chosen: selectedSet.has(country.code) }"
        type="button"
        role="option"
        :aria-selected="selectedSet.has(country.code)"
        @mouseenter="focusedIndex = index"
        @click="choose(country.code)"
      >
        <span class="tick">{{ selectedSet.has(country.code) ? '✓' : '' }}</span>
        <span>{{ country.name }}</span>
        <span class="country-code">{{ country.code }}</span>
      </button>
      <p v-if="matching.length === 90" class="search-hint">Type to narrow the country list.</p>
    </div>
    <div v-if="selectedCountries.length" class="selected-list" aria-label="Selected preferred countries">
      <span v-for="country in selectedCountries" :key="country.code" class="selected-chip">
        {{ country.name }}
        <button type="button" :disabled="disabled" :aria-label="`Remove ${country.name}`" @click="choose(country.code)">×</button>
      </span>
    </div>
    <p class="country-help">Choose one or more countries. Only destinations you select will affect your preferences.</p>
  </div>
</template>

<style scoped>
.country-search{position:relative;width:100%;min-width:0;font:inherit}
.search-box{display:flex;align-items:center;min-height:50px;gap:10px;border:1px solid #d4e6de;border-radius:12px;background:#fff;padding:0 13px;transition:border-color .2s,box-shadow .2s}
.search-box:focus-within{border-color:#0c936c;box-shadow:0 0 0 3px rgba(11,137,98,.12)}
.search-icon{font-size:1.45rem;color:#0c8662;line-height:1}
.search-box input{font:inherit;font-size:.91rem;outline:none!important;border:0!important;box-shadow:none!important;flex:1;min-width:0;min-height:48px;background:transparent;color:#153e33;padding:0}
.search-box input:disabled{cursor:not-allowed;background:transparent}
.search-box input::placeholder{color:#93a79e}
.counter{white-space:nowrap;font-weight:750;font-size:.74rem;color:#15805e;background:#e7f6ef;padding:6px 9px;border-radius:8px}
.options{position:absolute;top:55px;left:0;right:0;z-index:80;max-height:260px;overflow:auto;background:#fff;border:1px solid #d6e6df;border-radius:12px;box-shadow:0 15px 36px rgba(26,70,58,.16);padding:6px}
.country-option{display:flex;align-items:center;text-align:left;gap:10px;width:100%;min-height:40px;border:0;border-radius:8px;background:#fff;padding:8px 10px;color:#184636;font:inherit;font-size:.86rem;cursor:pointer}
.country-option:hover,.country-option.highlighted{background:#eef9f3}
.country-option.chosen{color:#087e55;font-weight:700}
.tick{width:22px;height:22px;border:1px solid #c7ded0;display:grid;place-items:center;border-radius:6px;flex-shrink:0;color:#fff}
.chosen .tick{background:#0d9468;border-color:#0d9468}
.country-code{font-size:.7rem;margin-left:auto;color:#829c90}
.no-results,.search-hint{padding:12px;margin:0;color:#718d7d;font-size:.79rem}
.selected-list{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}
.selected-chip{display:inline-flex;align-items:center;gap:8px;padding:7px 9px 7px 12px;border:1px solid #bce3cc;border-radius:10px;background:#eaf8f1;color:#096847;font-size:.82rem;font-weight:650}
.selected-chip button{border:0;background:transparent;color:#0a6c49;font:inherit;font-size:1.12rem;line-height:1;cursor:pointer;padding:0 2px}
.selected-chip button:hover{color:#b23a3a}
.country-help{font-size:.74rem;color:#779489;margin:10px 0 0;line-height:1.45}
@media(max-width:520px){.counter{font-size:.65rem;padding:5px}.selected-chip{font-size:.75rem}}
@media(prefers-reduced-motion:reduce){.search-box{transition:none}}
</style>
