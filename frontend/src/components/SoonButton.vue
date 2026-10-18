<script setup>
import { computed } from 'vue'
import { TIERS } from '@/lib/content'

const props = defineProps({
  icon: { type: String, default: '' },
  variant: { type: String, default: 'quiet' },   
  tier: { type: String, default: '' },           
  small: { type: Boolean, default: false },
  iconOnly: { type: Boolean, default: false },
  label: { type: String, default: '' },          
})

const hint = computed(() => `Segera hadir${props.tier ? ` · khusus ${TIERS[props.tier].label} User` : ''}`)
</script>

<template>
  <span class="inline-flex" :title="hint">
    <button
      type="button"
      disabled
      aria-disabled="true"
      :aria-label="iconOnly ? label : undefined"
      class="btn"
      :class="[`btn-${variant}`, small && 'btn-sm', iconOnly && '!px-2.5']"
    >
      <Icon v-if="icon" :icon="icon" class="size-4" />
      <span v-if="!iconOnly"><slot /></span>
    </button>
  </span>
</template>