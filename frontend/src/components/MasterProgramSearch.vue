<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { MASTER_DEGREE_TITLES, isMasterDegreeTitle } from '../data/masterDegreeTitles'
import type { MasterDegreeTitle } from '../data/masterDegreeTitles'

const props = defineProps<{ id: string; modelValue: string }>()
const emit = defineEmits<{
  'update:modelValue': [value: string]
  // Retained for compatibility with earlier Academic Profile screens.
  selected: [program: { title: string; fieldKey: string; fieldName: string }]
}>()

const input = ref<HTMLInputElement | null>(null)
const menu = ref<HTMLDivElement | null>(null)
const open = ref(false)
const typed = ref(props.modelValue)
const activeIndex = ref(-1)
const menuPosition = ref<Record<string, string>>({})
const listId = computed(() => `${props.id}-suggestions`)
const searchTerm = computed(() => typed.value.trim().toLocaleLowerCase())
const matches = computed(() => {
  const term = searchTerm.value
  if (!term) return MASTER_DEGREE_TITLES.slice()
  return MASTER_DEGREE_TITLES.filter((item) =>
    item.title.toLocaleLowerCase().includes(term) ||
    item.abbreviation.toLocaleLowerCase().includes(term),
  ).sort((a, b) => {
    // Prioritize abbreviation/exact-prefix searches (e.g. MBA or MSc).
    const score = (d: MasterDegreeTitle) => {
      const abbr = d.abbreviation.toLocaleLowerCase()
      const title = d.title.toLocaleLowerCase()
      return abbr.split(/\s*\/\s*/).includes(term) ? 0 : abbr.startsWith(term) ? 1 : title.startsWith(term) ? 2 : 3
    }
    return score(a) - score(b)
  })
})
const currentChoice = computed(() => MASTER_DEGREE_TITLES.find((item) => item.title === props.modelValue))

watch(() => props.modelValue, (value) => {
  // Older version stored arbitrary subject specializations. Don't accept them
  // as degree types when restoring a saved local draft.
  if (value && !isMasterDegreeTitle(value)) {
    emit('update:modelValue', '')
    typed.value = ''
    return
  }
  if (!open.value) typed.value = value
}, { immediate: true })

function positionMenu() {
  if (!open.value || !input.value) return
  const rect = input.value.getBoundingClientRect()
  const above = rect.top - 12
  const below = window.innerHeight - rect.bottom - 12
  const flip = below < 270 && above > below
  const height = Math.max(115, Math.min(355, (flip ? above : below) - 10))
  menuPosition.value = {
    position: 'fixed',
    left: `${Math.max(12, Math.min(rect.left, window.innerWidth - rect.width - 12))}px`,
    top: `${flip ? rect.top - height - 8 : rect.bottom + 8}px`,
    width: `${Math.min(rect.width, window.innerWidth - 24)}px`,
    maxHeight: `${height}px`,
  }
}
function focus() {
  open.value = true
  activeIndex.value = -1
  positionMenu()
}
function onInput(value: string) {
  typed.value = value
  // A title is committed only when the user picks an item from the list.
  // Free text or subject specialization is never persisted as a degree type.
  if (props.modelValue) emit('update:modelValue', '')
  activeIndex.value = -1
  open.value = true
  void nextTick(positionMenu)
}
function selectDegree(item: MasterDegreeTitle) {
  emit('update:modelValue', item.title)
  typed.value = item.title
  close()
  void nextTick(() => input.value?.focus())
}
function close() {
  open.value = false
  activeIndex.value = -1
  typed.value = currentChoice.value?.title ?? ''
}
function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && open.value) {
    event.preventDefault()
    close()
  } else if ((event.key === 'ArrowDown' || event.key === 'ArrowUp') && open.value && matches.value.length) {
    event.preventDefault()
    const delta = event.key === 'ArrowDown' ? 1 : -1
    activeIndex.value = (activeIndex.value + delta + matches.value.length) % matches.value.length
    void nextTick(() => menu.value?.querySelector(`[data-option-index="${activeIndex.value}"]`)?.scrollIntoView({ block: 'nearest' }))
  } else if (event.key === 'Enter' && open.value && activeIndex.value >= 0) {
    const item = matches.value[activeIndex.value]
    if (item) { event.preventDefault(); selectDegree(item) }
  } else if (event.key === 'Tab') close()
}
function outside(event: PointerEvent) {
  const target = event.target
  if (target instanceof Node && !input.value?.contains(target) && !menu.value?.contains(target)) close()
}
onMounted(() => {
  document.addEventListener('pointerdown', outside)
  window.addEventListener('scroll', positionMenu, true)
  window.addEventListener('resize', positionMenu)
})
onUnmounted(() => {
  document.removeEventListener('pointerdown', outside)
  window.removeEventListener('scroll', positionMenu, true)
  window.removeEventListener('resize', positionMenu)
})
</script>

<template>
  <div class="master-degree-search">
    <svg class="degree-search-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="10.6" cy="10.6" r="6.6" stroke="currentColor" stroke-width="1.7"/><path d="m16 16 5 5" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>
    <input
      :id="id"
      ref="input"
      class="degree-search-input"
      type="search"
      autocomplete="off"
      :value="typed"
      placeholder="Search MBA, MSc, MEng, MPH…"
      role="combobox"
      aria-autocomplete="list"
      aria-haspopup="listbox"
      :aria-expanded="open"
      :aria-controls="open ? listId : undefined"
      :aria-activedescendant="open && activeIndex >= 0 && matches[activeIndex] ? `${id}-degree-${activeIndex}` : undefined"
      @focus="focus"
      @input="onInput(($event.target as HTMLInputElement).value)"
      @keydown="onKeydown"
    />
    <span v-if="currentChoice && !open" class="degree-selected" aria-hidden="true">✓</span>
    <Teleport to="body">
      <div v-if="open" :id="listId" ref="menu" class="master-degree-menu" :style="menuPosition" role="listbox" aria-label="Master's degree titles">
        <div class="degree-menu-heading">
          <span>MASTER'S DEGREE TITLES</span>
          <span>{{ matches.length }} of 98</span>
        </div>
        <p v-if="matches.length === 0" class="degree-empty">No matching degree title in the reference list. Try MSc, MBA, MEng, or MPH.</p>
        <button
          v-for="(item, index) in matches"
          :id="`${id}-degree-${index}`"
          :key="`${item.title}-${index}`"
          type="button"
          class="master-degree-option"
          :class="{ active: activeIndex === index, chosen: item.title === modelValue }"
          role="option"
          :data-option-index="index"
          :aria-selected="item.title === modelValue"
          @pointerenter="activeIndex = index"
          @mousedown.prevent
          @click="selectDegree(item)"
        >
          <span class="degree-abbr">{{ item.abbreviation }}</span>
          <span class="degree-name"><strong>{{ item.title }}</strong><small>{{ item.category }}</small></span>
          <span v-if="item.title === modelValue" class="degree-option-check" aria-hidden="true">✓</span>
        </button>
        <div class="degree-menu-footer">Choose a named Master's degree. Subject specializations are selected separately under Field of Study.</div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.master-degree-search { min-width: 0; position: relative; width: 100%; }
.degree-search-input { width: 100%; padding-left: 46px !important; padding-right: 43px !important; border-radius: 11px !important; }
.degree-search-icon { position: absolute; width: 20px; height: 20px; left: 15px; top: 50%; transform: translateY(-50%); color: #118261; pointer-events: none; }
.degree-selected { position: absolute; top: 50%; right: 18px; transform: translateY(-50%); color: #0c9a6b; font-weight: 800; }
.master-degree-menu { z-index: 4900; overflow-y: auto; overscroll-behavior: contain; background: #fff; border: 1px solid #d3e6dc; border-radius: 14px; box-shadow: 0 21px 45px rgba(18,72,54,.16); color: #20463c; font: inherit; padding: 7px; box-sizing: border-box; }
.degree-menu-heading { display: flex; justify-content: space-between; align-items: center; gap: 15px; padding: 11px 12px 13px; margin-bottom: 3px; border-bottom: 1px solid #e5eee9; color: #718e7f; font-size: .71rem; font-weight: 800; letter-spacing: .065em; }
.master-degree-option { display: flex; align-items: center; gap: 12px; text-align: left; width: 100%; border: 0; border-radius: 10px; background: transparent; padding: 11px; cursor: pointer; color: #193e33; font: inherit; min-height: 60px; }
.master-degree-option:hover, .master-degree-option.active { background: #eaf7f0; }
.master-degree-option.chosen { background: #f3fbf6; }
.master-degree-option:focus-visible { outline: 2px solid #148663; outline-offset: -2px; }
.degree-abbr { flex: 0 0 95px; min-width: 0; padding: 8px 7px; background: #e8f4ee; color: #087952; border-radius: 8px; font-weight: 800; font-size: .79rem; text-align: center; overflow-wrap: anywhere; }
.degree-name { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.degree-name strong { font-size: .87rem; font-weight: 750; line-height: 1.35; }
.degree-name small { color: #7a9688; font-size: .73rem; line-height: 1.3; }
.degree-option-check { margin-left: auto; color: #0a875e; font-weight: 800; }
.degree-empty { color: #677f75; font-size: .84rem; line-height: 1.6; margin: 8px 12px 16px; }
.degree-menu-footer { margin-top: 7px; padding: 12px; border-top: 1px solid #e7efea; color: #638372; font-size: .74rem; line-height: 1.5; }
@media (max-width: 480px) { .degree-abbr { flex-basis: 76px; } .degree-name strong { font-size: .82rem; } .master-degree-menu { border-radius: 10px; } }
</style>
