<script setup>
import { RATINGS } from '@/lib/content'

defineProps({ rating: { type: String, default: null } })
</script>

<template>
  <span v-if="rating && RATINGS[rating]" class="chip" :class="RATINGS[rating].cls">
    <Icon :icon="RATINGS[rating].icon" class="size-3.5" />
    {{ RATINGS[rating].label }}
  </span>
</template>