<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import api, { errorMessage } from '@/lib/api'
import { tierKey } from '@/lib/auth'
import BookCard from '@/components/BookCard.vue'
import SeriesCard from '@/components/SeriesCard.vue'
import SeriesDialog from '@/components/SeriesDialog.vue'
import SeriesViewer from '@/components/SeriesViewer.vue'
import TierChip from '@/components/TierChip.vue'

const docs = ref([])
const collections = ref([])
const loading = ref(true)
const loadError = ref('')
const uploading = ref(false)
const uploadError = ref('')
const limitHit = ref(false)    // unggahan ditolak karena batas paket (402): tawarkan halaman paket
const dragging = ref(false)
const fileInput = ref(null)
let timer = null

async function load(silent = false) {
  try {
    const [d, c] = await Promise.all([api.get('/documents'), api.get('/collections')])
    docs.value = d.data
    collections.value = c.data
    loadError.value = ''
  } catch (e) {
    if (!silent) loadError.value = errorMessage(e, 'Gagal memuat koleksi. Muat ulang halaman.')
  } finally {
    loading.value = false
  }
}

const toDelete = ref(null)
const cancelBtn = ref(null)
watch(toDelete, (v) => { if (v) setTimeout(() => cancelBtn.value?.focus(), 0) })
const onKey = (e) => { if (e.key === 'Escape') cancelDelete() }
onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
const deleting = ref(false)
const deleteError = ref('')

function askDelete(doc) {
  deleteError.value = ''
  toDelete.value = doc
}
function cancelDelete() {
  if (!deleting.value) toDelete.value = null
}
async function confirmDelete() {
  deleting.value = true
  deleteError.value = ''
  try {
    await api.delete(`/documents/${toDelete.value.id}`)
    docs.value = docs.value.filter((d) => d.id !== toDelete.value.id)
    toDelete.value = null
  } catch (e) {
    if (e.response?.status === 404) {  
      docs.value = docs.value.filter((d) => d.id !== toDelete.value.id)
      toDelete.value = null
    } else {
      deleteError.value = errorMessage(e, 'Gagal menghapus e-book. Coba lagi.')
    }
  } finally {
    deleting.value = false
  }
}

// Satu per satu agar batas halaman dan kuota diperiksa per file (UC-02); file yang gagal tidak menggagalkan yang lain.
async function uploadFiles(files) {
  uploadError.value = ''
  limitHit.value = false
  const list = [...files]
  if (!list.length) return
  const label = (file, text) => (list.length > 1 ? `${file.name}: ${text}` : text)
  const created = []
  const errors = []
  uploading.value = true
  try {
    for (const file of list) {
      if (!/\.(pdf|epub)$/i.test(file.name)) {
        errors.push(label(file, 'Format file tidak didukung. Unggah file berformat PDF atau EPUB.'))
        continue
      }
      const body = new FormData()
      body.append('file', file)
      try {
        created.push((await api.post('/documents', body)).data.id)
      } catch (e) {
        if (e.response?.status === 402) limitHit.value = true
        errors.push(label(file, errorMessage(e, 'Gagal menyimpan dokumen. Coba unggah lagi.')))
      }
    }
    await load(true)
  } finally {
    uploading.value = false
    if (fileInput.value) fileInput.value.value = ''
  }
  uploadError.value = errors.join(' ')
  if (created.length >= 2) openSeries(null, created)    // beberapa file sekaligus: tawarkan langsung jadi seri
}

function onDrop(event) {
  dragging.value = false
  uploadFiles(event.dataTransfer.files)
}

// Seri buku (UC-02): kelompok e-book yang saling bersambung
const seriesDialog = ref(null)    // { series, preselected } saat terbuka
const savingSeries = ref(false)
const seriesError = ref('')

const docById = computed(() => new Map(docs.value.map((d) => [d.id, d])))
const groups = computed(() =>
  collections.value
    .map((c) => ({ ...c, books: c.document_ids.map((id) => docById.value.get(id)).filter(Boolean) }))
    .filter((g) => g.books.length),
)
const looseDocs = computed(() => {
  const grouped = new Set(collections.value.flatMap((c) => c.document_ids))
  return docs.value.filter((d) => !grouped.has(d.id))
})

const openGroupId = ref(null)
const openGroup = computed(() => groups.value.find((g) => g.id === openGroupId.value) ?? null)
function editFromList(group) {
  openGroupId.value = null
  openSeries(group)
}

function openSeries(series = null, preselected = []) {
  seriesError.value = ''
  seriesDialog.value = { series, preselected }
}
function closeSeries() {
  if (!savingSeries.value) seriesDialog.value = null
}
async function runSeries(call) {
  savingSeries.value = true
  seriesError.value = ''
  try {
    await call()
    await load(true)
    seriesDialog.value = null
  } catch (e) {
    seriesError.value = errorMessage(e, 'Gagal menyimpan seri. Coba lagi.')
  } finally {
    savingSeries.value = false
  }
}
const saveSeries = ({ name, ids }) => {
  const series = seriesDialog.value.series
  return runSeries(() => (series ? api.put(`/collections/${series.id}`, { name, document_ids: ids }) : api.post('/collections', { name, document_ids: ids })))
}
const dissolveSeries = () => runSeries(() => api.delete(`/collections/${seriesDialog.value.series.id}`))

onMounted(() => {
  load()
  timer = setInterval(() => {
    if (docs.value.some((d) => d.status === 'queued' || d.status === 'analyzing')) load(true)
  }, 3000)
})
onBeforeUnmount(() => clearInterval(timer))
</script>

<template>
  <div class="container-page space-y-10 py-10">
    <!-- Sambutan -->
    <section class="card relative overflow-hidden p-6 sm:p-8">
      <div class="pointer-events-none absolute -top-16 -right-16 size-56 rounded-full bg-amber/20 blur-3xl" />
      <div class="relative grid gap-6 lg:grid-cols-[1.4fr_1fr] lg:items-center">
        <div class="space-y-2">
          <p class="eyebrow">Analisis konten e-book</p>
          <h1 class="text-3xl font-semibold sm:text-4xl">Unggah naskah, lihat ratingnya</h1>
          <p class="max-w-md text-[15px] text-muted">
            Unggah naskah PDF atau EPUB untuk dinilai kontennya, lalu baca dengan Safe Mode yang menyamarkan adegan dewasa.
          </p>
        </div>
        <div class="space-y-3 rounded-xl bg-paper p-5">
          <div class="flex items-center justify-between gap-3">
            <p class="eyebrow">Akunmu</p>
            <TierChip :tier="tierKey()" />
          </div>
          <p class="text-sm text-muted">Butuh rincian per dimensi, rangkuman, tokoh, atau unduhan hasil? Itu tersedia di paket yang lebih tinggi.</p>
          <div class="flex flex-wrap gap-2">
            <RouterLink :to="{ name: 'plans' }" class="btn btn-accent btn-sm">
              <Icon icon="lucide:gem" class="size-4" />
              Lihat paket
            </RouterLink>
            <RouterLink :to="{ name: 'plans', hash: '#riwayat' }" class="btn btn-outline btn-sm">
              <Icon icon="lucide:receipt" class="size-4" />
              Riwayat pembayaran
            </RouterLink>
          </div>
        </div>
      </div>
    </section>

    <!-- Unggah -->
    <section>
      <div
        class="card flex flex-col items-center gap-4 border-2 border-dashed p-8 text-center transition sm:p-10"
        :class="dragging ? 'border-amber bg-amber/10' : 'border-line'"
        @dragover.prevent="dragging = true"
        @dragleave.prevent="dragging = false"
        @drop.prevent="onDrop"
      >
        <span class="grid size-14 place-items-center rounded-2xl bg-sand text-navy">
          <Icon :icon="uploading ? 'lucide:loader-circle' : 'lucide:file-up'" class="size-7" :class="{ 'animate-spin': uploading }" />
        </span>
        <div class="space-y-1">
          <h2 class="text-xl font-semibold">{{ uploading ? 'Mengunggah dan memeriksa naskah…' : 'Unggah naskah PDF atau EPUB' }}</h2>
          <p class="text-sm text-muted">Tarik berkas ke sini atau pilih dari perangkat. Bisa lebih dari satu sekaligus untuk dijadikan seri. Analisis dimulai otomatis setelah unggahan.</p>
        </div>
        <input ref="fileInput" type="file" multiple accept="application/pdf,application/epub+zip,.pdf,.epub" class="sr-only" @change="uploadFiles($event.target.files)" />
        <button class="btn btn-primary" :disabled="uploading" @click="fileInput.click()">
          <Icon icon="lucide:folder-open" class="size-4.5" />
          Pilih file PDF / EPUB
        </button>
        <p v-if="uploadError" role="alert" class="flex items-start gap-2 rounded-lg bg-danger/10 px-3 py-2.5 text-left text-sm text-danger">
          <Icon icon="lucide:circle-alert" class="mt-0.5 size-4 shrink-0" />
          <span>
            {{ uploadError }}
            <RouterLink v-if="limitHit" :to="{ name: 'plans' }" class="font-semibold underline">Lihat paket</RouterLink>
          </span>
        </p>
      </div>
    </section>

    <!-- Koleksi -->
    <section class="space-y-5">
      <div class="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p class="eyebrow">Perpustakaan</p>
          <h2 class="text-2xl font-semibold">Koleksi e-book</h2>
        </div>
        <button class="btn btn-outline btn-sm" :disabled="docs.length < 2" :title="docs.length < 2 ? 'Butuh minimal dua e-book' : ''" @click="openSeries()">
          <Icon icon="lucide:layers" class="size-4" />
          Buat seri dari beberapa e-book
        </button>
      </div>

      <p v-if="loadError" role="alert" class="rounded-lg bg-danger/10 px-3 py-2.5 text-sm text-danger">{{ loadError }}</p>

      <div v-if="loading" class="flex items-center justify-center gap-2 py-16 text-muted">
        <Icon icon="lucide:loader-circle" class="size-5 animate-spin" />
        Memuat koleksi…
      </div>

      <div v-else-if="!docs.length && !loadError" class="card grid place-items-center gap-3 px-6 py-14 text-center">
        <Icon icon="lucide:library-big" class="size-10 text-lavender" />
        <p class="font-display text-lg text-navy">Koleksimu masih kosong</p>
        <p class="max-w-xs text-sm text-muted">Unggah e-book pertamamu di atas, nanti muncul di sini lengkap dengan statusnya.</p>
      </div>

      <ul v-else class="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-4">
        <SeriesCard v-for="g in groups" :key="`seri-${g.id}`" :group="g" @open="openGroupId = $event.id" @edit="editFromList" />
        <BookCard v-for="doc in looseDocs" :key="doc.id" :doc="doc" @delete="askDelete" />
      </ul>
    </section>

    <SeriesDialog
      v-if="seriesDialog"
      :docs="docs"
      :collections="collections"
      :series="seriesDialog.series"
      :preselected="seriesDialog.preselected"
      :saving="savingSeries"
      :error="seriesError"
      @save="saveSeries"
      @dissolve="dissolveSeries"
      @close="closeSeries"
    />

    <SeriesViewer v-if="openGroup" :group="openGroup" @close="openGroupId = null" @edit="editFromList" @delete="askDelete" />

    <!-- Konfirmasi hapus -->
    <div v-if="toDelete" class="fixed inset-0 z-50 grid place-items-center bg-navy-deep/50 px-4" @click.self="cancelDelete" @keydown.esc="cancelDelete">
      <div role="alertdialog" aria-modal="true" aria-labelledby="hapus-judul" class="card w-full max-w-md space-y-4 p-6 shadow-xl">
        <div class="flex items-start gap-3">
          <span class="grid size-10 shrink-0 place-items-center rounded-xl bg-danger/10 text-danger"><Icon icon="lucide:trash-2" class="size-5" /></span>
          <div class="space-y-1.5">
            <h2 id="hapus-judul" class="text-xl font-semibold">Hapus e-book ini?</h2>
            <p class="text-sm text-muted">
              <strong class="text-navy">{{ toDelete.title }}</strong> beserta seluruh hasil analisisnya akan dihapus permanen dan tidak bisa dikembalikan.
            </p>
          </div>
        </div>
        <p v-if="deleteError" role="alert" class="rounded-lg bg-danger/10 px-3 py-2.5 text-sm text-danger">{{ deleteError }}</p>
        <div class="flex justify-end gap-2">
          <button ref="cancelBtn" class="btn btn-quiet btn-sm" :disabled="deleting" @click="cancelDelete">Batal</button>
          <button class="btn btn-sm bg-danger text-white hover:brightness-110" :disabled="deleting" @click="confirmDelete">
            <Icon :icon="deleting ? 'lucide:loader-circle' : 'lucide:trash-2'" class="size-4" :class="{ 'animate-spin': deleting }" />
            {{ deleting ? 'Menghapus…' : 'Ya, hapus' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>