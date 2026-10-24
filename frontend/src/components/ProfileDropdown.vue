<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

interface ProfileDropdownOption {
  value: string
  label: string
}

const props = withDefaults(defineProps<{
  id: string
  modelValue: string
  options: ProfileDropdownOption[]
  placeholder?: string
  invalid?: boolean
  disabled?: boolean
  ariaLabel?: string
}>(), {
  placeholder: 'Select an option',
  invalid: false,
  disabled: false,
})

const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
const trigger = ref<HTMLButtonElement | null>(null)
const menu = ref<HTMLUListElement | null>(null)
const isOpen = ref(false)
const activeIndex = ref(0)
const menuStyle = ref<Record<string, string>>({})
const listId = computed(() => `${props.id}-options`)
const selectedIndex = computed(() => props.options.findIndex((option) => option.value === props.modelValue))
const selectedOption = computed(() => props.options[selectedIndex.value])
const activeOptionId = computed(() => isOpen.value ? `${props.id}-option-${activeIndex.value}` : undefined)
let search = ''
let searchTimer: ReturnType<typeof setTimeout> | undefined

function updatePosition() {
  if (!isOpen.value || !trigger.value) return
  const rect = trigger.value.getBoundingClientRect()
  const below = window.innerHeight - rect.bottom - 14
  const above = rect.top - 14
  const up = below < 180 && above > below
  const room = up ? above : below
  const height = Math.max(60, Math.min(288, room - 8))
  const left = Math.max(10, Math.min(rect.left, window.innerWidth - rect.width - 10))
  menuStyle.value = {
    position: 'fixed',
    top: `${up ? rect.top - height - 8 : rect.bottom + 8}px`,
    left: `${left}px`,
    width: `${rect.width}px`,
    maxHeight: `${height}px`,
  }
}

async function scrollToActive() {
  await nextTick()
  const item = menu.value?.children.item(activeIndex.value)
  item?.scrollIntoView({ block: 'nearest' })
}

function openDropdown() {
  if (props.disabled || isOpen.value) return
  activeIndex.value = Math.max(0, selectedIndex.value)
  isOpen.value = true
  updatePosition()
  void scrollToActive()
}

function closeDropdown() {
  isOpen.value = false
  search = ''
}

function selectOption(index: number) {
  const option = props.options[index]
  if (!option) return
  emit('update:modelValue', option.value)
  closeDropdown()
  void nextTick(() => trigger.value?.focus())
}

function moveActive(direction: number) {
  if (!props.options.length) return
  activeIndex.value = (activeIndex.value + direction + props.options.length) % props.options.length
  void scrollToActive()
}

function onKeydown(event: KeyboardEvent) {
  if (props.disabled) return
  switch (event.key) {
    case 'ArrowDown':
    case 'ArrowUp':
      event.preventDefault()
      if (!isOpen.value) openDropdown()
      else moveActive(event.key === 'ArrowDown' ? 1 : -1)
      return
    case 'Home':
    case 'End':
      if (!isOpen.value) return
      event.preventDefault()
      activeIndex.value = event.key === 'Home' ? 0 : props.options.length - 1
      void scrollToActive()
      return
    case 'Enter':
    case ' ':
      event.preventDefault()
      if (!isOpen.value) openDropdown()
      else selectOption(activeIndex.value)
      return
    case 'Escape':
      if (isOpen.value) {
        event.preventDefault()
        closeDropdown()
      }
      return
    case 'Tab':
      closeDropdown()
      return
    default:
      // Type a few letters to jump to a matching option, like a native select.
      if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
        search += event.key.toLowerCase()
        if (searchTimer) clearTimeout(searchTimer)
        searchTimer = setTimeout(() => { search = '' }, 700)
        const match = props.options.findIndex((item) => item.label.toLowerCase().startsWith(search))
        if (match >= 0) {
          if (!isOpen.value) openDropdown()
          activeIndex.value = match
          void scrollToActive()
        }
      }
  }
}

function onPointerDown(event: PointerEvent) {
  const target = event.target
  if (!(target instanceof Node) || trigger.value?.contains(target) || menu.value?.contains(target)) return
  closeDropdown()
}

watch(() => props.disabled, (disabled) => { if (disabled) closeDropdown() })
onMounted(() => {
  document.addEventListener('pointerdown', onPointerDown)
  window.addEventListener('resize', updatePosition)
  window.addEventListener('scroll', updatePosition, true)
})
onUnmounted(() => {
  document.removeEventListener('pointerdown', onPointerDown)
  window.removeEventListener('resize', updatePosition)
  window.removeEventListener('scroll', updatePosition, true)
  if (searchTimer) clearTimeout(searchTimer)
})
</script>

<template>
  <div class="profile-dropdown" :class="{ 'is-open': isOpen, 'is-disabled': disabled }">
    <button
      :id="id"
      ref="trigger"
      class="dropdown-trigger"
      type="button"
      role="combobox"
      aria-haspopup="listbox"
      :aria-expanded="isOpen"
      :aria-controls="isOpen ? listId : undefined"
      :aria-activedescendant="activeOptionId"
      :aria-invalid="invalid ? 'true' : undefined"
      :aria-label="ariaLabel"
      :disabled="disabled"
      @click="isOpen ? closeDropdown() : openDropdown()"
      @keydown="onKeydown"
    >
      <span class="dropdown-value" :class="{ placeholder: !selectedOption }">{{ selectedOption?.label ?? placeholder }}</span>
      <svg class="dropdown-chevron" width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="m6 9 6 6 6-6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
    </button>
    <Teleport to="body">
      <Transition name="dropdown-pop">
        <ul
          v-if="isOpen"
          :id="listId"
          ref="menu"
          class="profile-dropdown-menu"
          role="listbox"
          :aria-label="ariaLabel || undefined"
          :style="menuStyle"
        >
          <li
            v-for="(option, index) in options"
            :id="`${id}-option-${index}`"
            :key="`${option.value}-${index}`"
            class="dropdown-option"
            :class="{ 'is-selected': option.value === modelValue, 'is-active': activeIndex === index }"
            role="option"
            :aria-selected="option.value === modelValue"
            @mouseenter="activeIndex = index"
            @mousedown.prevent
            @click="selectOption(index)"
          >
            <span class="option-label">{{ option.label }}</span>
            <svg v-if="option.value === modelValue" width="17" height="17" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="m5 12 4.5 4.5L19 7" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </li>
        </ul>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.profile-dropdown { width: 100%; min-width: 0; position: relative; }
.dropdown-trigger { width: 100%; min-width: 0; min-height: 49px; padding: 11px 13px 11px 15px; border-radius: 11px; border: 1px solid #d7e4df; background: #fff; box-shadow: 0 1px 3px rgba(10, 69, 47, .04); display: flex; align-items: center; justify-content: space-between; gap: 10px; font: inherit; color: #294540; font-size: .9rem; text-align: left; cursor: pointer; transition: border-color .18s, box-shadow .18s, background .18s; }
.dropdown-trigger:hover { border-color: #8fc6ad; background: #fafffc; }
.dropdown-trigger:focus-visible, .is-open .dropdown-trigger { outline: none; border-color: #13956d; box-shadow: 0 0 0 3px rgba(19, 149, 109, .14); }
.dropdown-trigger[aria-invalid='true'] { border-color: #d45555; }
.dropdown-trigger:disabled { cursor: not-allowed; background: #f5f8f7; opacity: .68; }
.dropdown-value { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dropdown-value.placeholder { color: #97aca4; }
.dropdown-chevron { flex: none; color: #44836e; transition: transform .18s ease; }
.is-open .dropdown-chevron { transform: rotate(180deg); }
.profile-dropdown-menu { z-index: 10000; margin: 0; padding: 7px; list-style: none; overflow: auto; overscroll-behavior: contain; background: #fff; border: 1px solid #cae2d5; box-shadow: 0 18px 48px rgba(15, 65, 49, .18), 0 4px 14px rgba(15, 65, 49, .06); border-radius: 14px; color: #264b40; box-sizing: border-box; }
.dropdown-option { padding: 10px 12px; min-height: 42px; display: flex; justify-content: space-between; align-items: center; gap: 12px; border-radius: 9px; font-size: .87rem; line-height: 1.45; cursor: pointer; overflow-wrap: anywhere; }
.dropdown-option.is-active { background: #edf8f1; color: #087b55; }
.dropdown-option.is-selected { background: #e1f4e9; color: #087855; font-weight: 750; }
.dropdown-option.is-selected.is-active { background: #d5efdf; }
.dropdown-option svg { flex: none; }
.dropdown-pop-enter-active, .dropdown-pop-leave-active { transition: opacity .15s ease, transform .15s ease; transform-origin: top center; }
.dropdown-pop-enter-from, .dropdown-pop-leave-to { opacity: 0; transform: translateY(-6px) scale(.985); }
@media (prefers-reduced-motion: reduce) { .dropdown-trigger, .dropdown-chevron, .dropdown-pop-enter-active, .dropdown-pop-leave-active { transition: none; } }
</style>
