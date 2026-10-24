<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { specializationsForMaster } from '../data/masterSpecializations'

const props = defineProps<{
  id: string
  degreeTitle: string
  modelValue: string
  invalid?: boolean
}>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

const input = ref<HTMLInputElement | null>(null)
const menu = ref<HTMLDivElement | null>(null)
const isOpen = ref(false)
const typed = ref('')
const highlighted = ref(-1)
const menuStyle = ref<Record<string, string>>({})
const options = computed(() => specializationsForMaster(props.degreeTitle))
const current = computed(() => options.value.find((item) => item.value === props.modelValue))
const available = computed(() => options.value.length > 0)
const listId = computed(() => `${props.id}-specializations`)
const matches = computed(() => {
  const text = typed.value.trim().toLocaleLowerCase()
  return !text ? [...options.value] : options.value.filter((item) =>
    item.label.toLocaleLowerCase().includes(text),
  )
})

watch(() => props.modelValue, () => {
  if (!isOpen.value) typed.value = current.value?.label ?? ''
}, { immediate: true })
watch(() => props.degreeTitle, () => {
  if (!options.value.some((item) => item.value === props.modelValue) && props.modelValue) {
    emit('update:modelValue', '')
  }
  isOpen.value = false
  highlighted.value = -1
  typed.value = current.value?.label ?? ''
})

function placeMenu() {
  if (!isOpen.value || !input.value) return
  const rect = input.value.getBoundingClientRect()
  const spaceBelow = window.innerHeight - rect.bottom - 12
  const spaceAbove = rect.top - 12
  const flip = spaceBelow < 235 && spaceAbove > spaceBelow
  const height = Math.max(110, Math.min(310, (flip ? spaceAbove : spaceBelow) - 12))
  menuStyle.value = {
    position: 'fixed',
    left: `${Math.max(12, Math.min(rect.left, window.innerWidth - rect.width - 12))}px`,
    top: `${flip ? rect.top - height - 8 : rect.bottom + 8}px`,
    width: `${Math.min(rect.width, window.innerWidth - 24)}px`,
    maxHeight: `${height}px`,
  }
}
function openMenu() {
  if (!available.value) return
  isOpen.value = true
  highlighted.value = -1
  typed.value = ''
  void nextTick(placeMenu)
}
function changeInput(value: string) {
  typed.value = value
  if (props.modelValue) emit('update:modelValue', '')
  highlighted.value = -1
  isOpen.value = true
  void nextTick(placeMenu)
}
function select(value: string) {
  const item = options.value.find((option) => option.value === value)
  if (!item) return
  emit('update:modelValue', value)
  isOpen.value = false
  highlighted.value = -1
  typed.value = item.label
  void nextTick(() => input.value?.focus())
}
function closeMenu() {
  isOpen.value = false
  highlighted.value = -1
  typed.value = current.value?.label ?? ''
}
function onKeydown(event: KeyboardEvent) {
  if (!isOpen.value && (event.key === 'ArrowDown' || event.key === 'Enter')) {
    event.preventDefault()
    openMenu()
  } else if (isOpen.value && event.key === 'Escape') {
    event.preventDefault()
    closeMenu()
  } else if (isOpen.value && (event.key === 'ArrowDown' || event.key === 'ArrowUp') && matches.value.length) {
    event.preventDefault()
    highlighted.value = (highlighted.value + (event.key === 'ArrowDown' ? 1 : -1) + matches.value.length) % matches.value.length
    void nextTick(() => menu.value?.querySelector(`[data-specialization-index="${highlighted.value}"]`)?.scrollIntoView({ block: 'nearest' }))
  } else if (isOpen.value && event.key === 'Enter' && highlighted.value >= 0) {
    const item = matches.value[highlighted.value]
    if (item) { event.preventDefault(); select(item.value) }
  } else if (event.key === 'Tab') closeMenu()
}
function onDocumentPointer(event: PointerEvent) {
  if (event.target instanceof Node && !input.value?.contains(event.target) && !menu.value?.contains(event.target)) closeMenu()
}
onMounted(() => {
  document.addEventListener('pointerdown', onDocumentPointer)
  window.addEventListener('scroll', placeMenu, true)
  window.addEventListener('resize', placeMenu)
})
onUnmounted(() => {
  document.removeEventListener('pointerdown', onDocumentPointer)
  window.removeEventListener('scroll', placeMenu, true)
  window.removeEventListener('resize', placeMenu)
})
</script>

<template>
  <div class="specialization-search" :class="{ unavailable: !available }">
    <svg class="search-symbol" viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6" stroke="currentColor" stroke-width="1.8"/><path d="m15.5 15.5 5 5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>
    <input
      :id="id"
      ref="input"
      :value="typed"
      type="search"
      autocomplete="off"
      :disabled="!available"
      :aria-invalid="Boolean(invalid)"
      :placeholder="available ? 'Search related specializations…' : 'Choose a Master’s degree first'"
      role="combobox"
      aria-autocomplete="list"
      aria-haspopup="listbox"
      :aria-expanded="isOpen"
      :aria-controls="isOpen ? listId : undefined"
      :aria-activedescendant="isOpen && highlighted >= 0 && matches[highlighted] ? `${id}-option-${highlighted}` : undefined"
      class="specialization-input"
      @focus="openMenu"
      @input="changeInput(($event.target as HTMLInputElement).value)"
      @keydown="onKeydown"
    />
    <span v-if="current && !isOpen" class="chosen-icon" aria-hidden="true">✓</span>
    <Teleport to="body">
      <div v-if="isOpen" :id="listId" ref="menu" class="specialization-popup" :style="menuStyle" role="listbox" :aria-label="`Specializations related to ${degreeTitle}`">
        <div class="popup-header"><span>RELATED SPECIALIZATIONS</span><span>{{ matches.length }} OPTIONS</span></div>
        <p v-if="!matches.length" class="popup-empty">No matching specialization. Try a broader search.</p>
        <button
          v-for="(option, index) in matches"
          :id="`${id}-option-${index}`"
          :key="option.value"
          :data-specialization-index="index"
          type="button"
          role="option"
          :aria-selected="option.value === modelValue"
          class="popup-option"
          :class="{ highlighted: index === highlighted, chosen: option.value === modelValue }"
          @mousedown.prevent
          @pointerenter="highlighted = index"
          @click="select(option.value)"
        ><span>{{ option.label }}</span><span v-if="option.value === modelValue" class="option-check" aria-hidden="true">✓</span></button>
        <div class="popup-footer">Illustrative study areas; actual specializations vary by university.</div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.specialization-search { position: relative; width: 100%; min-width: 0; }
.specialization-input { display: block; width: 100%; min-width: 0; min-height: 49px; padding: 11px 43px; border: 1px solid #d7e4df; border-radius: 10px; background: #fff; color: #294540; font: inherit; font-size: .9rem; box-shadow: 0 1px 3px #123b2d08; box-sizing: border-box; transition: border-color .16s, box-shadow .16s; }
.specialization-input:focus { outline: none; border-color: #199d74; box-shadow: 0 0 0 3px #17966e1f; }
.specialization-input[aria-invalid='true'] { border-color: #d45555; }
.specialization-input:disabled { background: #f4f8f6 !important; color: #839c90; cursor: not-allowed; }
.search-symbol { width: 19px; height: 19px; position: absolute; left: 15px; top: 50%; transform: translateY(-50%); color: #12835f; pointer-events: none; }
.unavailable .search-symbol { color: #a8bab1; }
.chosen-icon { position: absolute; right: 17px; top: 50%; transform: translateY(-50%); color: #0b8b61; font-weight: 800; pointer-events: none; }
.specialization-popup { z-index: 5500; overflow: auto; overscroll-behavior: contain; box-sizing: border-box; padding: 7px; background: white; border: 1px solid #d4e7dd; border-radius: 14px; color: #194132; box-shadow: 0 22px 50px rgba(12, 70, 47, .16); font: inherit; }
.popup-header { padding: 11px 10px 13px; margin-bottom: 4px; display: flex; justify-content: space-between; gap: 8px; border-bottom: 1px solid #e6f0e9; font-size: .69rem; font-weight: 850; letter-spacing: .07em; color: #789382; }
.popup-option { width: 100%; min-height: 45px; padding: 10px 13px; display: flex; align-items: center; justify-content: space-between; gap: 12px; border: 0; border-radius: 10px; background: white; font: inherit; font-size: .87rem; font-weight: 620; color: #1f4539; text-align: left; cursor: pointer; }
.popup-option:hover, .popup-option.highlighted { background: #e8f7ef; color: #0b6849; }
.popup-option.chosen { background: #f0faf4; }
.popup-option:focus-visible { outline: 2px solid #1b9870; outline-offset: -2px; }
.option-check { color: #06875a; font-weight: 850; }
.popup-empty { padding: 14px; color: #71897f; font-size: .85rem; }
.popup-footer { padding: 11px 10px 7px; border-top: 1px solid #e7eee9; color: #81978d; font-size: .73rem; }
@media (prefers-reduced-motion: reduce) { .specialization-popup { scroll-behavior: auto; } }
</style>
