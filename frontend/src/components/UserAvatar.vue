<script setup>
import { computed } from 'vue'

const props = defineProps({
  name: { type: String, default: '' },
  size: { type: String, default: 'md' },
})

const initials = computed(() =>
  props.name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0].toUpperCase())
    .join(''),
)

const SIZES = { sm: 'size-8 text-xs', md: 'size-10 text-sm', lg: 'size-16 text-xl' }
</script>

<template>
  <span class="grid shrink-0 place-items-center rounded-full bg-navy font-display font-semibold text-amber" :class="SIZES[size] ?? SIZES.md" aria-hidden="true">
    <template v-if="initials">{{ initials }}</template>
    <Icon v-else icon="lucide:user" class="size-1/2" />
  </span>
</template>
