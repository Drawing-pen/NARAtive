<script setup>
import { computed } from 'vue'

const props = defineProps({
  label: { type: String, required: true },
  icon: { type: String, required: true },
  value: { type: Number, required: true },
  max: { type: Number, default: null },
})

const percent = computed(() => (props.max ? Math.min(100, (props.value / props.max) * 100) : 0))
const full = computed(() => props.max !== null && props.value >= props.max)
</script>

<template>
  <div class="space-y-2">
    <div class="flex items-center justify-between text-sm">
      <span class="flex items-center gap-2 font-semibold text-navy">
        <Icon :icon="icon" class="size-4 text-lavender" />
        {{ label }}
      </span>
      <span class="tabular-nums text-muted">
        <strong class="text-navy">{{ value }}</strong>
        <template v-if="max !== null"> / {{ max }}</template>
        <template v-else> · tanpa batas</template>
      </span>
    </div>
    <div class="h-2 overflow-hidden rounded-full bg-sand" role="progressbar" :aria-valuenow="value" :aria-valuemax="max ?? undefined">
      <div class="h-full rounded-full transition-all duration-500" :class="full ? 'bg-amber' : 'bg-navy'" :style="{ width: max === null ? '100%' : percent + '%', opacity: max === null ? 0.25 : 1 }" />
    </div>
  </div>
</template>