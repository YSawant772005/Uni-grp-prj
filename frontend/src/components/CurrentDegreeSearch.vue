<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import {
  CURRENT_DEGREE_TITLES,
  canonicalCurrentDegree,
  degreeSearchToken,
} from '../data/currentDegreeTitles'
import type { CurrentDegreeTitle } from '../data/currentDegreeTitles'

const props = defineProps<{ id: string; modelValue: string; invalid?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
const input = ref<HTMLInputElement | null>(null)
const menu = ref<HTMLDivElement | null>(null)
const isOpen = ref(false)
const typed = ref('')
const activeIndex = ref(-1)
const menuPosition = ref<Record<string, string>>({})
const listId = computed(() => `${props.id}-title-list`)
const query = computed(() => degreeSearchToken(typed.value.trim()))
const choice = computed(() => CURRENT_DEGREE_TITLES.find((item) => item.title === props.modelValue))
const matches = computed(() => {
  if (!query.value) return CURRENT_DEGREE_TITLES
  const term = query.value
  const score = (item: CurrentDegreeTitle) => {
    const abbreviations = item.abbreviations.map(degreeSearchToken)
    const title = degreeSearchToken(item.title)
    if (abbreviations.includes(term)) return 0
    if (abbreviations.some((abbr) => abbr.startsWith(term))) return 1
    if (title.startsWith(term)) return 2
    return 3
  }
  return CURRENT_DEGREE_TITLES.filter((item) =>
    degreeSearchToken(item.title).includes(term) ||
    item.abbreviations.some((abbreviation) => degreeSearchToken(abbreviation).includes(term)),
  ).sort((a, b) => score(a) - score(b))
})

watch(() => props.modelValue, (value) => {
  if (!value) {
    if (!isOpen.value) typed.value = ''
    return
  }
  const canonical = canonicalCurrentDegree(value)
  if (!canonical) {
    // A previously saved unsupported value must be reselected, not silently
    // treated as a valid degree title.
    emit('update:modelValue', '')
    if (!isOpen.value) typed.value = ''
    return
  }
  if (canonical !== value) {
    // Convert previous select values, such as B.Tech, to a canonical title.
    emit('update:modelValue', canonical)
  }
  if (!isOpen.value) typed.value = canonical
}, { immediate: true })

function positionMenu() {
  if (!isOpen.value || !input.value) return
  const r = input.value.getBoundingClientRect()
  const below = window.innerHeight - r.bottom - 12
  const above = r.top - 12
  const flip = below < 250 && above > below
  const available = flip ? above : below
  const height = Math.min(350, Math.max(110, available - 12))
  menuPosition.value = {
    position: 'fixed',
    left: `${Math.max(12, Math.min(r.left, window.innerWidth - 24 - Math.min(r.width, window.innerWidth - 24)))}px`,
    top: `${flip ? r.top - height - 8 : r.bottom + 8}px`,
    width: `${Math.min(r.width, window.innerWidth - 24)}px`,
    maxHeight: `${height}px`,
  }
}
function openMenu() {
  isOpen.value = true
  activeIndex.value = -1
  void nextTick(positionMenu)
}
function closeMenu() {
  isOpen.value = false
  activeIndex.value = -1
  typed.value = choice.value?.title ?? ''
}
function onInput(event: Event) {
  typed.value = (event.target as HTMLInputElement).value
  // Never save free-text as a selected qualification.
  if (props.modelValue) emit('update:modelValue', '')
  activeIndex.value = -1
  isOpen.value = true
  void nextTick(positionMenu)
}
function select(item: CurrentDegreeTitle) {
  emit('update:modelValue', item.title)
  typed.value = item.title
  closeMenu()
  void nextTick(() => input.value?.focus())
}
function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && isOpen.value) {
    event.preventDefault()
    closeMenu()
  } else if ((event.key === 'ArrowDown' || event.key === 'ArrowUp') && isOpen.value && matches.value.length) {
    event.preventDefault()
    const delta = event.key === 'ArrowDown' ? 1 : -1
    activeIndex.value = (activeIndex.value + delta + matches.value.length) % matches.value.length
    void nextTick(() => menu.value?.querySelector(`[data-option-index="${activeIndex.value}"]`)?.scrollIntoView({ block: 'nearest' }))
  } else if (event.key === 'Enter' && isOpen.value) {
    event.preventDefault()
    const item = activeIndex.value >= 0 ? matches.value[activeIndex.value] : matches.value.length === 1 ? matches.value[0] : undefined
    if (item) select(item)
  } else if (event.key === 'Tab') {
    closeMenu()
  } else if (event.key === 'ArrowDown' && !isOpen.value) {
    event.preventDefault()
    openMenu()
  }
}
function outside(event: PointerEvent) {
  const target = event.target
  if (target instanceof Node && !input.value?.contains(target) && !menu.value?.contains(target)) closeMenu()
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
  <div class="current-degree-search">
    <svg class="search-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="10.5" cy="10.5" r="6.5" stroke="currentColor" stroke-width="1.8" />
      <path d="m16 16 5 5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
    </svg>
    <input
      :id="id"
      ref="input"
      type="search"
      class="search-input"
      :value="typed"
      autocomplete="off"
      placeholder="Search B.Tech, BSc, BBA, MSc…"
      :aria-invalid="Boolean(invalid)"
      role="combobox"
      aria-haspopup="listbox"
      aria-autocomplete="list"
      :aria-expanded="isOpen"
      :aria-controls="isOpen ? listId : undefined"
      :aria-activedescendant="isOpen && activeIndex >= 0 ? `${id}-option-${activeIndex}` : undefined"
      @focus="openMenu"
      @input="onInput"
      @keydown="onKeydown"
    />
    <span v-if="choice && !isOpen" class="selected-icon" aria-hidden="true">✓</span>
    <Teleport to="body">
      <div
        v-if="isOpen"
        :id="listId"
        ref="menu"
        class="degree-search-menu"
        :style="menuPosition"
        role="listbox"
        aria-label="Bachelor's and Master's degree titles"
      >
        <div class="search-menu-heading">
          <strong>CURRENT QUALIFICATION</strong>
          <span>{{ matches.length }} of 210</span>
        </div>
        <p v-if="matches.length === 0" class="no-matches">
          No matching title in the reference list. Try an abbreviation or the full award name.
        </p>
        <button
          v-for="(item, index) in matches"
          :id="`${id}-option-${index}`"
          :key="item.title"
          type="button"
          role="option"
          class="degree-search-option"
          :class="{ active: activeIndex === index, chosen: item.title === modelValue }"
          :aria-selected="item.title === modelValue"
          :data-option-index="index"
          @pointerenter="activeIndex = index"
          @mousedown.prevent
          @click="select(item)"
        >
          <span class="abbreviation">{{ item.abbreviations.join(' / ') }}</span>
          <span class="option-text">
            <strong>{{ item.title }}</strong>
            <small>{{ item.level === 'bachelor' ? 'Bachelor’s degree' : 'Master’s degree' }}</small>
          </span>
          <span v-if="item.title === modelValue" class="option-check" aria-hidden="true">✓</span>
        </button>
        <div class="search-menu-footer">Choose your existing qualification. Branch/major and desired Master’s specialization are separate fields.</div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.current-degree-search { width: 100%; min-width: 0; position: relative; }
.search-input { display: block; box-sizing: border-box; width: 100%; min-width: 0; min-height: 49px; padding: 11px 40px 11px 44px; border: 1px solid #d7e4df; border-radius: 11px; background: #fff; color: #294540; font: inherit; font-size: .9rem; box-shadow: 0 1px 3px #123b2d08; transition: border-color .16s,box-shadow .16s; }
.search-input:focus { outline: none; border-color: #199d74; box-shadow: 0 0 0 3px #17966e1f; }
.search-input[aria-invalid='true'] { border-color: #d45555; }
.search-input::placeholder { color: #9bb1a8; }
.search-icon { position: absolute; left: 14px; top: 50%; width: 20px; height: 20px; transform: translateY(-50%); pointer-events: none; color: #168a62; }
.selected-icon { position: absolute; right: 17px; top: 50%; transform: translateY(-50%); color: #0c9469; font-weight: 800; }
.degree-search-menu { z-index: 4900; overflow-y: auto; overscroll-behavior: contain; box-sizing: border-box; padding: 7px; background: white; border: 1px solid #d3e6dc; border-radius: 14px; box-shadow: 0 20px 48px rgba(18,72,54,.17); color: #20463c; font: inherit; }
.search-menu-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 12px; border-bottom: 1px solid #e3ece7; color: #5f7f70; font-size: .73rem; }
.search-menu-heading strong { font-weight: 800; letter-spacing: .06em; }
.degree-search-option { display: flex; align-items: center; gap: 12px; width: 100%; padding: 10px; min-height: 60px; border: 0; border-radius: 10px; background: transparent; color: #173b31; text-align: left; cursor: pointer; font: inherit; }
.degree-search-option:hover, .degree-search-option.active { background: #e9f7ee; }
.degree-search-option.chosen { background: #f2faf6; }
.degree-search-option:focus-visible { outline: 2px solid #118563; outline-offset: -2px; }
.abbreviation { display: block; flex: 0 0 95px; overflow-wrap: anywhere; text-align: center; font-size: .77rem; font-weight: 800; color: #0a7654; background: #e6f5ed; border-radius: 8px; padding: 8px 6px; }
.option-text { display: flex; min-width: 0; flex-direction: column; gap: 4px; }
.option-text strong { font-size: .87rem; font-weight: 750; line-height: 1.4; }
.option-text small { color: #80998e; font-size: .73rem; }
.option-check { margin-left: auto; font-weight: 900; color: #0a9768; }
.no-matches { padding: 10px 12px 20px; font-size: .85rem; color: #667e72; line-height: 1.5; }
.search-menu-footer { padding: 12px; color: #6a8879; border-top: 1px solid #e3ece7; font-size: .74rem; line-height: 1.5; }
@media (max-width: 520px) { .abbreviation { flex-basis: 73px; font-size: .69rem; } .option-text strong { font-size: .81rem; } .degree-search-menu { border-radius: 10px; } }
</style>
