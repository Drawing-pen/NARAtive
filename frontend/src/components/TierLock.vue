<script setup>
import TierChip from '@/components/TierChip.vue'

defineProps({
  tier: { type: String, default: 'middle' },
  title: { type: String, required: true },
  text: { type: String, default: '' },
})
</script>

<template>
  <section class="card grid place-items-center gap-4 border-amber bg-amber/10 px-6 py-14 text-center">
    <Icon icon="lucide:lock" class="size-12 text-navy" />
    <div class="space-y-2">
      <TierChip :tier="tier" />
      <h2 class="text-2xl font-semibold">{{ title }}</h2>
      <p v-if="text" class="max-w-md text-sm text-muted">{{ text }}</p>
    </div>
    <RouterLink :to="{ name: 'plans' }" class="btn btn-accent btn-sm">Lihat paket</RouterLink>
  </section>
</template>
