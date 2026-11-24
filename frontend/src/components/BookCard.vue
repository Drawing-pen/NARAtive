<script setup>
import { computed } from 'vue'
import { formatDate } from '@/lib/content'
import AuthImage from '@/components/AuthImage.vue'
import ProgressLoader from '@/components/ProgressLoader.vue'
import RatingBadge from '@/components/RatingBadge.vue'
import StatusChip from '@/components/StatusChip.vue'

const props = defineProps({
  doc: { type: Object, required: true },
  number: { type: Number, default: 0 },   
})
defineEmits(['delete'])

const stageTitle = computed(() => ({ reading: 'Progres membaca berkas', queued: 'Menunggu giliran', analyzing: 'Progres analisis' })[props.doc.status] ?? 'Progres')
const stageDetail = computed(() => {
  if (props.doc.status === 'reading') return `Membaca halaman ${props.doc.read_pages} dari ${props.doc.page_count}`
  return props.doc.status === 'queued' ? 'Menunggu giliran' : 'Menganalisis isi buku'
})
</script>

<template>
  <li class="card group relative flex flex-col overflow-hidden p-2.5 transition duration-200 hover:-translate-y-1 hover:border-lavender hover:shadow-lg has-[a:focus-visible]:ring-2 has-[a:focus-visible]:ring-lavender">
    <div class="relative grid aspect-[2/3] place-items-center overflow-hidden rounded-xl bg-navy transition duration-200 group-hover:brightness-110">
      <AuthImage :path="`/documents/${doc.id}/cover`" :active="doc.has_cover" :alt="`Cover ${doc.title}`">
        <div class="absolute inset-2.5 rounded-lg border border-amber/40" />
        <span class="font-display text-7xl font-semibold text-amber/90">{{ doc.title.trim().charAt(0).toUpperCase() }}</span>
        <span class="absolute inset-x-0 bottom-5 text-center text-[11px] tracking-widest text-lavender uppercase">{{ doc.page_count }} halaman</span>
      </AuthImage>
      <span v-if="number" class="chip absolute top-4 left-4 bg-amber text-navy">Buku {{ number }}</span>
    </div>

    <div class="flex flex-1 flex-col gap-3 px-1.5 pt-3 pb-1.5">
      <div class="space-y-1">
        <h3 class="line-clamp-2 text-base leading-snug font-semibold transition group-hover:underline decoration-amber decoration-2 underline-offset-4" :title="doc.title">
          <RouterLink :to="{ name: 'document', params: { id: doc.id } }" class="outline-none after:absolute after:inset-0 after:z-0">{{ doc.title }}</RouterLink>
        </h3>
        <p class="text-xs text-muted">Diunggah {{ formatDate(doc.created_at) }}</p>
      </div>

      <div class="flex flex-wrap items-center gap-2">
        <StatusChip :status="doc.status" />
        <RatingBadge :rating="doc.rating" />
      </div>

      <ProgressLoader v-if="['reading', 'queued', 'analyzing'].includes(doc.status)" compact :percent="doc.progress" :title="stageTitle" :detail="stageDetail" />

      <div class="relative z-10 mt-auto flex flex-wrap items-center gap-2 pt-1">
        <template v-if="doc.status === 'done'">
          <RouterLink :to="{ name: 'document', params: { id: doc.id } }" class="btn btn-quiet btn-sm">
            <Icon icon="lucide:chart-no-axes-column" class="size-4" />
            Hasil
          </RouterLink>
          <RouterLink :to="{ name: 'reader', params: { id: doc.id } }" class="btn btn-primary btn-sm">
            <Icon icon="lucide:book-open" class="size-4" />
            Baca
          </RouterLink>
        </template>
        <RouterLink v-else-if="['reading', 'queued', 'analyzing'].includes(doc.status)" :to="{ name: 'document', params: { id: doc.id } }" class="btn btn-quiet btn-sm">
          <Icon icon="lucide:hourglass" class="size-4" />
          Lihat progres
        </RouterLink>
        <RouterLink v-else-if="doc.status === 'not_novel'" :to="{ name: 'document', params: { id: doc.id } }" class="btn btn-quiet btn-sm">
          <Icon icon="lucide:file-text" class="size-4" />
          Lihat
        </RouterLink>
        <span v-else class="text-sm text-danger">{{ doc.failure_reason || 'Analisis gagal. Unggah ulang file ini.' }}</span>
        <button class="btn btn-quiet btn-sm ml-auto !px-2.5 hover:!bg-danger/10 hover:!text-danger" :aria-label="`Hapus ${doc.title}`" title="Hapus dari koleksi" @click="$emit('delete', doc)">
          <Icon icon="lucide:trash-2" class="size-4" />
        </button>
      </div>
    </div>
  </li>
</template>
