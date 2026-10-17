<script setup>
// Tombol untuk fitur yang belum dibangun: tampil lengkap tetapi tidak bisa ditekan.
import { computed } from 'vue'
import { TIERS } from '@/lib/content'

const props = defineProps({
  icon: { type: String, default: '' },
  variant: { type: String, default: 'quiet' },   // primary | accent | quiet | outline
  tier: { type: String, default: '' },           // middle | high
  small: { type: Boolean, default: false },
  iconOnly: { type: Boolean, default: false },
  label: { type: String, default: '' },          // wajib untuk tombol ikon saja (aria-label)
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