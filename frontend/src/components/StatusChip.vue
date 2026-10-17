<script setup>
import { STATUS } from '@/lib/content'

defineProps({ status: { type: String, required: true } })
</script>

<template>
  <span class="chip" :class="STATUS[status]?.cls">
    <Icon :icon="STATUS[status]?.icon" class="size-3.5" :class="{ 'animate-spin': STATUS[status]?.spin }" />
    {{ STATUS[status]?.label }}
  </span>
</template>