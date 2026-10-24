<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { branchesForCurrentDegree } from '../data/currentDegreeBranches'

const props = withDefaults(defineProps<{
  id: string
  modelValue: string
  degreeTitle: string
  invalid?: boolean
}>(), { invalid: false })
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
const input = ref<HTMLInputElement | null>(null)
const menu = ref<HTMLDivElement | null>(null)
const open = ref(false)
const selectedIndex = ref(-1)
const position = ref<Record<string, string>>({})
const query = ref(props.modelValue)
const options = computed(() => branchesForCurrentDegree(props.degreeTitle))
const results = computed(() => {
  const text = query.value.trim().toLowerCase()
  return (text ? options.value.filter((branch) => branch.toLowerCase().includes(text)) : options.value).slice(0, 60)
})
const available = computed(() => options.value.length > 0)
const listId = computed(() => `${props.id}-suggestions`)

watch(() => props.modelValue, (value) => { if (query.value !== value) query.value = value })
watch(() => props.degreeTitle, () => { closeMenu() })

function positionMenu() {
  if (!open.value || !input.value) return
  const rect = input.value.getBoundingClientRect()
  const below = window.innerHeight - rect.bottom - 12
  const above = rect.top - 12
  const flip = below < 210 && above > below
  const height = Math.min(290, Math.max(100, (flip ? above : below) - 12))
  position.value = {
    position: 'fixed',
    left: `${Math.max(12, Math.min(rect.left, window.innerWidth - Math.min(rect.width, window.innerWidth - 24) - 12))}px`,
    top: `${flip ? rect.top - height - 7 : rect.bottom + 7}px`,
    width: `${Math.min(rect.width, window.innerWidth - 24)}px`,
    maxHeight: `${height}px`,
  }
}
function openMenu() {
  if (!available.value) return
  open.value = true
  selectedIndex.value = -1
  void nextTick(positionMenu)
}
function closeMenu() { open.value = false; selectedIndex.value = -1 }
function typeBranch(event: Event) {
  const nextValue = (event.target as HTMLInputElement).value
  query.value = nextValue
  emit('update:modelValue', nextValue)
  selectedIndex.value = -1
  openMenu()
}
function pick(value: string) {
  query.value = value
  emit('update:modelValue', value)
  closeMenu()
  void nextTick(() => input.value?.focus())
}
function keydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && open.value) { event.preventDefault(); closeMenu() }
  else if ((event.key === 'ArrowDown' || event.key === 'ArrowUp') && open.value && results.value.length) {
    event.preventDefault()
    const delta = event.key === 'ArrowDown' ? 1 : -1
    selectedIndex.value = (selectedIndex.value + delta + results.value.length) % results.value.length
    void nextTick(() => menu.value?.querySelector(`[data-branch-index="${selectedIndex.value}"]`)?.scrollIntoView({ block: 'nearest' }))
  } else if (event.key === 'Enter' && open.value) {
    event.preventDefault()
    if (selectedIndex.value >= 0 && results.value[selectedIndex.value]) pick(results.value[selectedIndex.value]!)
    else if (results.value.length === 1) pick(results.value[0]!)
    else closeMenu() // Keep a user-entered branch when no suggestion was selected.
  } else if (event.key === 'Tab') closeMenu()
  else if (event.key === 'ArrowDown' && !open.value) { event.preventDefault(); openMenu() }
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
  <div class="degree-branch-input">
    <svg class="branch-search-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5" stroke="currentColor" stroke-width="1.8" /><path d="m16 16 5 5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" /></svg>
    <input
      :id="id" ref="input" class="branch-input" type="search" :value="query" :disabled="!available" maxlength="160"
      :aria-invalid="invalid" :aria-expanded="open" :aria-controls="open ? listId : undefined"
      :aria-activedescendant="open && selectedIndex >= 0 ? `${id}-option-${selectedIndex}` : undefined"
      role="combobox" aria-haspopup="listbox" aria-autocomplete="list" autocomplete="off"
      :placeholder="available ? 'Search or enter your branch' : 'Choose Current Degree first'"
      @focus="openMenu" @input="typeBranch" @keydown="keydown"
    />
    <Teleport to="body">
      <div v-if="open" :id="listId" ref="menu" class="degree-branch-menu" :style="position" role="listbox" aria-label="Related branches and majors">
        <div class="branch-menu-header"><strong>RELATED BRANCHES</strong><span>{{ results.length }} suggestions</span></div>
        <div v-if="!results.length" class="branch-empty">No preset match. You can keep the branch you typed.</div>
        <button v-for="(branch, index) in results" :id="`${id}-option-${index}`" :key="branch" type="button" role="option"
          class="branch-option" :class="{ active: selectedIndex === index, chosen: modelValue === branch }"
          :aria-selected="modelValue === branch" :data-branch-index="index" @pointerenter="selectedIndex = index"
          @mousedown.prevent @click="pick(branch)">
          <span>{{ branch }}</span><span v-if="modelValue === branch" class="branch-check">✓</span>
        </button>
        <div class="branch-menu-footer">Not listed? Type your official branch name directly.</div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.degree-branch-input { width: 100%; min-width: 0; position: relative; }
.branch-input { display: block; width: 100%; min-width: 0; box-sizing: border-box; min-height: 49px; padding: 11px 14px 11px 43px; border: 1px solid #d7e4df; border-radius: 10px; background: #fff; color: #294540; font: inherit; font-size: .9rem; box-shadow: 0 1px 3px #123b2d08; }
.branch-input:focus { outline: 0; border-color: #199d74; box-shadow: 0 0 0 3px #17966e1f; }
.branch-input[aria-invalid='true'] { border-color: #d45555; }
.branch-input:disabled { color: #81938d; background: #f4f8f5; cursor: not-allowed; }
.branch-input::placeholder { color: #93a69e; }
.branch-search-icon { position: absolute; left: 13px; top: 50%; width: 20px; height: 20px; transform: translateY(-50%); color: #148b63; pointer-events: none; }
.degree-branch-menu { z-index: 10025; background: #fff; border: 1px solid #cae3d5; border-radius: 13px; box-sizing: border-box; padding: 7px; overflow: auto; overscroll-behavior: contain; box-shadow: 0 18px 48px #154a312a, 0 4px 14px #153b200d; }
.branch-menu-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin: 2px 7px 8px; color: #247453; font-size: .68rem; letter-spacing: .08em; }
.branch-menu-header span { font-size: .7rem; letter-spacing: normal; font-weight: 500; color: #718e82; }
.branch-option { display: flex; align-items: center; justify-content: space-between; width: 100%; min-height: 39px; padding: 9px 12px; border: 0; border-radius: 9px; color: #294d3e; background: transparent; font: inherit; font-size: .85rem; text-align: left; cursor: pointer; }
.branch-option.active { background: #edf8f1; color: #087b55; }
.branch-option.chosen { background: #e0f3e8; font-weight: 750; color: #087855; }
.branch-check { color: #0d825b; margin-left: 10px; }
.branch-empty { padding: 14px; font-size: .82rem; color: #718e82; }
.branch-menu-footer { border-top: 1px solid #ebf0ed; padding: 10px 7px 4px; font-size: .74rem; color: #789185; }
</style>
