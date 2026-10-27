<script setup>
import { computed } from 'vue'

const props = defineProps({
  group: { type: Object, required: true },    // { id, name, books: [dokumen berurutan] }
})
defineEmits(['open', 'edit'])

const pages = computed(() => props.group.books.reduce((sum, d) => sum + d.page_count, 0))
const busy = computed(() => props.group.books.filter((d) => d.status === 'queued' || d.status === 'analyzing').length)
const failed = computed(() => props.group.books.filter((d) => d.status === 'failed').length)
</script>

<template>
  <!-- dua lapis di belakang kartu depan memberi kesan tumpukan buku -->
  <li class="group relative pr-3 pb-3">
    <div class="card absolute top-3 right-0 bottom-0 left-3 bg-sand transition-transform duration-200 group-hover:translate-x-0.5 group-hover:translate-y-0.5" aria-hidden="true" />
    <div class="card absolute top-1.5 right-1.5 bottom-1.5 left-1.5 transition-transform duration-200 group-hover:translate-x-0.5 group-hover:translate-y-0.5" aria-hidden="true" />

    <div class="card relative flex h-full flex-col overflow-hidden p-2.5 transition duration-200 group-hover:-translate-y-1 group-hover:border-lavender group-hover:shadow-lg has-[button:focus-visible]:ring-2 has-[button:focus-visible]:ring-lavender">
      <div class="relative grid aspect-[2/3] place-items-center overflow-hidden rounded-xl bg-navy transition duration-200 group-hover:brightness-110">
        <div class="absolute inset-2.5 rounded-lg border border-amber/40" />
        <span class="chip absolute top-4 left-4 bg-amber text-navy">Seri</span>
        <Icon icon="lucide:layers" class="size-16 text-amber/90" />
        <span class="absolute inset-x-0 bottom-5 text-center text-[11px] tracking-widest text-lavender uppercase">{{ group.books.length }} buku · {{ pages }} halaman</span>
      </div>

      <div class="flex flex-1 flex-col gap-3 px-1.5 pt-3 pb-1.5">
        <div class="space-y-1">
          <h3 class="line-clamp-2 text-base leading-snug font-semibold transition group-hover:underline decoration-amber decoration-2 underline-offset-4" :title="group.name">
            <!-- tombol "membentang": seluruh kartu bisa diklik untuk membuka seri -->
            <button type="button" class="text-left outline-none after:absolute after:inset-0 after:z-0" :aria-label="`Buka seri ${group.name}, ${group.books.length} buku`" @click="$emit('open', group)">{{ group.name }}</button>
          </h3>
          <p class="text-xs text-muted">
            <template v-if="busy">{{ busy }} buku sedang dianalisis</template>
            <template v-else-if="failed">{{ failed }} buku gagal dianalisis</template>
            <template v-else>Semua buku selesai dianalisis</template>
          </p>
        </div>

        <div class="relative z-10 mt-auto flex items-center gap-2 pt-1">
          <button type="button" class="btn btn-primary btn-sm" @click="$emit('open', group)">
            <Icon icon="lucide:folder-open" class="size-4" />
            Buka seri
          </button>
          <button type="button" class="btn btn-quiet btn-sm ml-auto !px-2.5" :aria-label="`Ubah seri ${group.name}`" title="Ubah seri" @click="$emit('edit', group)">
            <Icon icon="lucide:pencil" class="size-4" />
          </button>
        </div>
      </div>
    </div>
  </li>
</template>
