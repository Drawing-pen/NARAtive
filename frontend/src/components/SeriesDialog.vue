<script setup>
import { computed, onMounted, ref } from 'vue'

const props = defineProps({
  docs: { type: Array, required: true },                       // semua e-book milik pengguna
  collections: { type: Array, default: () => [] },
  series: { type: Object, default: null },                     // seri yang sedang diubah; null = membuat baru
  preselected: { type: Array, default: () => [] },             // id e-book yang sudah dipilih di awal (urut)
  saving: { type: Boolean, default: false },
  error: { type: String, default: '' },
})
const emit = defineEmits(['save', 'dissolve', 'close'])

const MIN_BOOKS = 2
const name = ref(props.series?.name ?? '')
const ids = ref([...(props.series?.document_ids ?? props.preselected)])
const nameInput = ref(null)

const byId = computed(() => new Map(props.docs.map((d) => [d.id, d])))
const chosen = computed(() => ids.value.map((id) => byId.value.get(id)).filter(Boolean))
const available = computed(() => props.docs.filter((d) => !ids.value.includes(d.id)))
const canSave = computed(() => name.value.trim() && chosen.value.length >= MIN_BOOKS)

// buku yang sudah berada di seri lain akan dipindahkan ke sini
const seriesOf = (doc) => props.collections.find((c) => c.id !== props.series?.id && c.document_ids.includes(doc.id))?.name

function move(i, delta) {
  const j = i + delta
  if (j < 0 || j >= ids.value.length) return
  const next = [...ids.value]
  ;[next[i], next[j]] = [next[j], next[i]]
  ids.value = next
}
const remove = (id) => (ids.value = ids.value.filter((i) => i !== id))
const add = (id) => ids.value.push(id)
const submit = () => canSave.value && emit('save', { name: name.value.trim(), ids: chosen.value.map((d) => d.id) })

onMounted(() => nameInput.value?.focus())
</script>

<template>
  <div class="fixed inset-0 z-50 grid place-items-center bg-navy-deep/50 px-4 py-6" @click.self="!saving && emit('close')" @keydown.esc="!saving && emit('close')">
    <div role="dialog" aria-modal="true" aria-labelledby="seri-judul" class="card flex max-h-full w-full max-w-xl flex-col gap-4 overflow-y-auto p-6 shadow-xl">
      <div class="flex items-start gap-3">
        <span class="grid size-10 shrink-0 place-items-center rounded-xl bg-sand text-navy"><Icon icon="lucide:layers" class="size-5" /></span>
        <div class="space-y-1">
          <h2 id="seri-judul" class="text-xl font-semibold">{{ series ? 'Ubah seri' : 'Buat seri buku' }}</h2>
          <p class="text-sm text-muted">Kelompokkan buku yang saling bersambung agar koleksimu lebih rapi. Tiap buku tetap dianalisis sendiri.</p>
        </div>
      </div>

      <label class="block space-y-1.5">
        <span class="eyebrow">Nama seri</span>
        <input
          ref="nameInput"
          v-model="name"
          type="text"
          maxlength="150"
          placeholder="mis. Trilogi Bumi"
          class="w-full rounded-lg border border-line bg-paper px-3 py-2 text-sm text-navy focus:border-lavender focus:outline-none"
          @keydown.enter.prevent="submit"
        />
      </label>

      <div class="space-y-2">
        <p class="eyebrow">Urutan baca ({{ chosen.length }} buku, minimal {{ MIN_BOOKS }})</p>
        <ol v-if="chosen.length" class="space-y-1.5">
          <li v-for="(d, i) in chosen" :key="d.id" class="flex items-center gap-2 rounded-lg bg-paper px-3 py-2">
            <span class="grid size-6 shrink-0 place-items-center rounded-full bg-navy text-xs font-semibold text-white">{{ i + 1 }}</span>
            <span class="min-w-0 flex-1 truncate text-sm font-semibold text-navy" :title="d.title">{{ d.title }}</span>
            <button type="button" class="btn btn-quiet btn-sm !px-2" :disabled="i === 0" :aria-label="`Naikkan ${d.title}`" @click="move(i, -1)">
              <Icon icon="lucide:chevron-up" class="size-4" />
            </button>
            <button type="button" class="btn btn-quiet btn-sm !px-2" :disabled="i === chosen.length - 1" :aria-label="`Turunkan ${d.title}`" @click="move(i, 1)">
              <Icon icon="lucide:chevron-down" class="size-4" />
            </button>
            <button type="button" class="btn btn-quiet btn-sm !px-2 hover:!bg-danger/10 hover:!text-danger" :aria-label="`Keluarkan ${d.title} dari seri`" @click="remove(d.id)">
              <Icon icon="lucide:x" class="size-4" />
            </button>
          </li>
        </ol>
        <p v-else class="rounded-lg border border-dashed border-line px-3 py-4 text-center text-sm text-muted">Belum ada buku dipilih. Tambahkan dari daftar di bawah.</p>
      </div>

      <div v-if="available.length" class="space-y-2">
        <p class="eyebrow">Tambahkan buku</p>
        <ul class="max-h-48 space-y-1.5 overflow-y-auto">
          <li v-for="d in available" :key="d.id" class="flex items-center gap-2 rounded-lg border border-line px-3 py-2">
            <span class="min-w-0 flex-1">
              <span class="block truncate text-sm text-navy" :title="d.title">{{ d.title }}</span>
              <span v-if="seriesOf(d)" class="block truncate text-xs text-muted">Akan dipindah dari seri "{{ seriesOf(d) }}"</span>
            </span>
            <button type="button" class="btn btn-quiet btn-sm" :aria-label="`Tambahkan ${d.title}`" @click="add(d.id)">
              <Icon icon="lucide:plus" class="size-4" />
              Tambah
            </button>
          </li>
        </ul>
      </div>

      <p v-if="error" role="alert" class="rounded-lg bg-danger/10 px-3 py-2.5 text-sm text-danger">{{ error }}</p>

      <div class="flex flex-wrap items-center justify-between gap-2">
        <button v-if="series" type="button" class="btn btn-quiet btn-sm hover:!bg-danger/10 hover:!text-danger" :disabled="saving" title="E-book di dalamnya tidak ikut terhapus" @click="emit('dissolve')">
          <Icon icon="lucide:ungroup" class="size-4" />
          Bubarkan seri
        </button>
        <span v-else />
        <div class="flex gap-2">
          <button type="button" class="btn btn-quiet btn-sm" :disabled="saving" @click="emit('close')">Batal</button>
          <button type="button" class="btn btn-primary btn-sm" :disabled="saving || !canSave" @click="submit">
            <Icon :icon="saving ? 'lucide:loader-circle' : 'lucide:save'" class="size-4" :class="{ 'animate-spin': saving }" />
            {{ saving ? 'Menyimpan…' : 'Simpan seri' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
