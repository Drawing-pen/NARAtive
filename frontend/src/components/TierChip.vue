<script setup>
import { TIERS } from '@/lib/content'

defineProps({ tier: { type: String, required: true } })
</script>

<template>
  <span class="chip" :class="TIERS[tier]?.cls">
    <Icon :icon="TIERS[tier]?.icon" class="size-3" />
    {{ TIERS[tier]?.label }}
  </span>
</template>