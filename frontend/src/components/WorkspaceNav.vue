<script setup>
import { RATINGS, UPCOMING } from '@/lib/content'
import BrandMark from '@/components/BrandMark.vue'
import RatingBadge from '@/components/RatingBadge.vue'
import TierChip from '@/components/TierChip.vue'

defineProps({ id: { type: String, required: true }, doc: { type: Object, default: null } })
defineEmits(['navigate'])

const soon = [...UPCOMING,
  { uc: 'UC-17', icon: 'lucide:image-up', title: 'Ganti cover', tier: 'high' },
]

const itemCls =
  'flex items-center gap-3 rounded-lg px-3 py-2.5 text-[15px] font-semibold text-navy transition hover:bg-sand aria-[current=page]:bg-navy aria-[current=page]:text-white aria-[current=page]:hover:bg-navy'
</script>

<template>
  <div class="flex h-full flex-col gap-6 overflow-y-auto p-4">
    <RouterLink :to="{ name: 'library' }" class="btn btn-outline btn-sm w-full justify-start" @click="$emit('navigate')">
      <Icon icon="lucide:arrow-left" class="size-4" />
      Kembali ke website
    </RouterLink>

    <div class="space-y-3 rounded-xl bg-paper p-4">
      <p class="eyebrow">Sedang dibuka</p>
      <template v-if="doc">
        <p class="line-clamp-3 font-display text-lg leading-snug font-semibold text-navy" :title="doc.title">{{ doc.title }}</p>
        <div class="flex flex-wrap items-center gap-2 text-xs text-muted">
          <RatingBadge :rating="doc.rating" />
          <span>{{ doc.page_count }} halaman</span>
        </div>
      </template>
      <div v-else class="space-y-2" aria-hidden="true">
        <div class="h-4 w-4/5 rounded bg-sand" />
        <div class="h-3 w-2/5 rounded bg-sand" />
      </div>
    </div>

    <nav class="space-y-1" aria-label="Menu buku">
      <p class="eyebrow px-3 pb-1">Utama</p>
      <RouterLink :to="{ name: 'document', params: { id } }" :class="itemCls" @click="$emit('navigate')">
        <Icon icon="lucide:chart-no-axes-column" class="size-5" />
        Hasil analisis
      </RouterLink>
      <RouterLink :to="{ name: 'reader', params: { id } }" :class="itemCls" @click="$emit('navigate')">
        <Icon icon="lucide:book-open" class="size-5" />
        Mode baca
      </RouterLink>
      <RouterLink :to="{ name: 'summary', params: { id } }" :class="itemCls" @click="$emit('navigate')">
        <Icon icon="lucide:scroll-text" class="size-5" />
        Rangkuman
      </RouterLink>
    </nav>

    <nav class="space-y-1" aria-label="Fitur lanjutan">
      <p class="eyebrow px-3 pb-1">Fitur lanjutan</p>
      <span
        v-for="f in soon"
        :key="f.uc"
        class="flex cursor-not-allowed items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-semibold text-muted/70"
        :title="`Segera hadir · khusus ${f.tier === 'high' ? 'High' : 'Middle'} User`"
        aria-disabled="true"
      >
        <Icon :icon="f.icon" class="size-5 shrink-0" />
        <span class="min-w-0 flex-1 truncate">{{ f.title }}</span>
        <TierChip :tier="f.tier" />
      </span>
    </nav>

    <div class="mt-auto"><BrandMark class="scale-90 origin-left" /></div>
  </div>
</template>