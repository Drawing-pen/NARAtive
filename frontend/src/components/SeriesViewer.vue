<script setup>
import { onMounted, ref } from 'vue'
import BookCard from '@/components/BookCard.vue'

defineProps({
  group: { type: Object, required: true },    // { id, name, books: [dokumen berurutan] }
})
const emit = defineEmits(['close', 'edit', 'delete'])

const closeBtn = ref(null)
onMounted(() => closeBtn.value?.focus())
</script>

<template>
  <div class="fixed inset-0 z-40 grid place-items-center bg-navy-deep/50 px-4 py-6" @click.self="emit('close')" @keydown.esc="emit('close')">
    <div role="dialog" aria-modal="true" aria-labelledby="seri-isi-judul" class="card flex max-h-full w-full max-w-5xl flex-col gap-5 overflow-y-auto bg-paper p-5 shadow-xl sm:p-7">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="flex min-w-0 items-center gap-3">
          <span class="grid size-11 shrink-0 place-items-center rounded-xl bg-navy text-amber"><Icon icon="lucide:folder-open" class="size-5" /></span>
          <div class="min-w-0">
            <p class="eyebrow">Seri buku</p>
            <h2 id="seri-isi-judul" class="truncate text-2xl font-semibold" :title="group.name">{{ group.name }}</h2>
            <p class="text-xs text-muted">{{ group.books.length }} buku, urut dari Buku 1</p>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <button type="button" class="btn btn-outline btn-sm" @click="emit('edit', group)">
            <Icon icon="lucide:pencil" class="size-4" />
            Ubah seri
          </button>
          <button ref="closeBtn" type="button" class="btn btn-quiet btn-sm !px-2.5" aria-label="Tutup seri" @click="emit('close')">
            <Icon icon="lucide:x" class="size-5" />
          </button>
        </div>
      </div>

      <ul class="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
        <BookCard v-for="(doc, i) in group.books" :key="doc.id" :doc="doc" :number="i + 1" @delete="emit('delete', $event)" />
      </ul>
    </div>
  </div>
</template>
