<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import api, { errorMessage } from '@/lib/api'
import { formatDate } from '@/lib/content'
import RatingBadge from '@/components/RatingBadge.vue'
import SoonButton from '@/components/SoonButton.vue'
import StatusChip from '@/components/StatusChip.vue'
import TierChip from '@/components/TierChip.vue'

const docs = ref([])
const loading = ref(true)
const loadError = ref('')
const uploading = ref(false)
const uploadError = ref('')
const dragging = ref(false)
const fileInput = ref(null)
let timer = null

async function load(silent = false) {
  try {
    const { data } = await api.get('/documents')
    docs.value = data
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

async function upload(file) {
  uploadError.value = ''
  if (!file) return
  if (!/\.(pdf|epub)$/i.test(file.name)) {
    uploadError.value = 'Format file tidak didukung. Unggah file berformat PDF atau EPUB.'
    return
  }
  const body = new FormData()
  body.append('file', file)
  uploading.value = true
  try {
    await api.post('/documents', body)
    await load(true)
  } catch (e) {
    uploadError.value = errorMessage(e, 'Gagal menyimpan dokumen. Coba unggah lagi.')
  } finally {
    uploading.value = false
    if (fileInput.value) fileInput.value.value = ''
  }
}

function onDrop(event) {
  dragging.value = false
  upload(event.dataTransfer.files[0])
}

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
            <TierChip tier="standard" />
          </div>
          <p class="text-sm text-muted">Butuh rincian per dimensi, rangkuman, tokoh, atau unduhan hasil? Itu tersedia di paket yang lebih tinggi.</p>
          <div class="flex flex-wrap gap-2">
            <RouterLink :to="{ name: 'plans' }" class="btn btn-accent btn-sm">
              <Icon icon="lucide:gem" class="size-4" />
              Lihat paket
            </RouterLink>
            <SoonButton variant="outline" small icon="lucide:receipt">Riwayat pembayaran</SoonButton>
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
          <p class="text-sm text-muted">Tarik berkas ke sini atau pilih dari perangkat. Analisis dimulai otomatis setelah unggahan.</p>
        </div>
        <input ref="fileInput" type="file" accept="application/pdf,application/epub+zip,.pdf,.epub" class="sr-only" @change="upload($event.target.files[0])" />
        <button class="btn btn-primary" :disabled="uploading" @click="fileInput.click()">
          <Icon icon="lucide:folder-open" class="size-4.5" />
          Pilih file PDF / EPUB
        </button>
        <p v-if="uploadError" role="alert" class="flex items-start gap-2 rounded-lg bg-danger/10 px-3 py-2.5 text-left text-sm text-danger">
          <Icon icon="lucide:circle-alert" class="mt-0.5 size-4 shrink-0" />
          {{ uploadError }}
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
        <SoonButton variant="outline" small icon="lucide:layers">Buat koleksi dari beberapa e-book</SoonButton>
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
        <li v-for="doc in docs" :key="doc.id" class="card group relative flex flex-col overflow-hidden p-2.5 transition duration-200 hover:-translate-y-1 hover:border-lavender hover:shadow-lg has-[a:focus-visible]:ring-2 has-[a:focus-visible]:ring-lavender">
          <div class="relative grid aspect-[2/3] place-items-center overflow-hidden rounded-xl bg-navy transition duration-200 group-hover:brightness-110">
            <div class="absolute inset-2.5 rounded-lg border border-amber/40" />
            <span class="font-display text-7xl font-semibold text-amber/90">{{ doc.title.trim().charAt(0).toUpperCase() }}</span>
            <span class="absolute inset-x-0 bottom-5 text-center text-[11px] tracking-widest text-lavender uppercase">{{ doc.page_count }} halaman</span>
          </div>

          <div class="flex flex-1 flex-col gap-3 px-1.5 pt-3 pb-1.5">
            <div class="space-y-1">
              <h3 class="line-clamp-2 text-base leading-snug font-semibold transition group-hover:underline decoration-amber decoration-2 underline-offset-4" :title="doc.title">
                <!-- tautan "membentang": area klik seluruh kartu; tombol di bawah tetap bisa diklik sendiri (z-10) -->
                <RouterLink :to="{ name: 'document', params: { id: doc.id } }" class="outline-none after:absolute after:inset-0 after:z-0">{{ doc.title }}</RouterLink>
              </h3>
              <p class="text-xs text-muted">Diunggah {{ formatDate(doc.created_at) }}</p>
            </div>

            <div class="flex flex-wrap items-center gap-2">
              <StatusChip :status="doc.status" />
              <RatingBadge :rating="doc.rating" />
            </div>

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
              <RouterLink v-else-if="doc.status === 'queued' || doc.status === 'analyzing'" :to="{ name: 'document', params: { id: doc.id } }" class="btn btn-quiet btn-sm">
                <Icon icon="lucide:hourglass" class="size-4" />
                Lihat progres
              </RouterLink>
              <span v-else class="text-sm text-danger">Analisis gagal. Unggah ulang file ini.</span>
              <button class="btn btn-quiet btn-sm ml-auto !px-2.5 hover:!bg-danger/10 hover:!text-danger" :aria-label="`Hapus ${doc.title}`" title="Hapus dari koleksi" @click="askDelete(doc)">
                <Icon icon="lucide:trash-2" class="size-4" />
              </button>
            </div>
          </div>
        </li>
      </ul>
    </section>

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