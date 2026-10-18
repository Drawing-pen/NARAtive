<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import api, { errorMessage } from '@/lib/api'
import { RATINGS, UPCOMING, formatDate, num } from '@/lib/content'
import RatingBadge from '@/components/RatingBadge.vue'
import SoonButton from '@/components/SoonButton.vue'
import StatusChip from '@/components/StatusChip.vue'
import TierChip from '@/components/TierChip.vue'

const props = defineProps({ id: { type: String, required: true } })

const doc = ref(null)
const loading = ref(true)
const missing = ref(false)
const error = ref('')
let timer = null

async function load(silent = false) {
  try {
    const { data } = await api.get(`/documents/${props.id}`)
    doc.value = data
    error.value = ''
  } catch (e) {
    if (e.response?.status === 404) missing.value = true
    else if (!silent) error.value = errorMessage(e, 'Gagal mengambil hasil analisis.')
  } finally {
    loading.value = false
  }
}

const exporting = ref(false)
const exportError = ref('')
async function downloadPdf() {
  exporting.value = true
  exportError.value = ''
  try {
    const res = await api.get(`/documents/${props.id}/export`, { responseType: 'blob' })
    const url = URL.createObjectURL(res.data)
    const a = document.createElement('a')
    a.href = url
    a.download = `NARAtive - ${doc.value.title}.pdf`
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 10000)
  } catch (e) {
    let msg = 'Gagal menyusun PDF. Coba lagi.'
    if (!e.response) msg = errorMessage(e)
    else if (e.response.data instanceof Blob) {
      try { msg = JSON.parse(await e.response.data.text()).detail || msg } catch { /* pakai pesan bawaan */ }
    }
    exportError.value = msg
  } finally {
    exporting.value = false
  }
}

const editing = ref(false)
const draft = ref('')
const saving = ref(false)
const renameError = ref('')
const titleInput = ref(null)

function startRename() {
  draft.value = doc.value.title
  renameError.value = ''
  editing.value = true
  nextTick(() => titleInput.value?.select())
}
function cancelRename() {
  if (!saving.value) editing.value = false
}
async function saveRename() {
  const title = draft.value.trim()
  if (!title) { renameError.value = 'Judul tidak boleh kosong.'; return }
  if (title === doc.value.title) { editing.value = false; return }
  saving.value = true
  renameError.value = ''
  try {
    const { data } = await api.patch(`/documents/${props.id}`, { title })
    doc.value = { ...doc.value, title: data.title }
    editing.value = false
  } catch (e) {
    renameError.value = errorMessage(e, 'Gagal menyimpan judul.')
  } finally {
    saving.value = false
  }
}

function estimate(seconds) {
  if (!seconds) return 'beberapa saat lagi'
  return seconds < 90 ? `sekitar ${seconds} detik` : `sekitar ${Math.round(seconds / 60)} menit`
}

onMounted(() => {
  load()
  timer = setInterval(() => {
    if (['queued', 'analyzing'].includes(doc.value?.status)) load(true)
  }, 3000)
})
onBeforeUnmount(() => clearInterval(timer))
</script>

<template>
  <div class="container-page space-y-8 py-10">
    <div v-if="loading" class="flex items-center justify-center gap-2 py-24 text-muted">
      <Icon icon="lucide:loader-circle" class="size-5 animate-spin" />
      Memuat…
    </div>

    <div v-else-if="missing" class="card grid place-items-center gap-3 px-6 py-16 text-center">
      <Icon icon="lucide:file-x" class="size-10 text-lavender" />
      <p class="font-display text-lg text-navy">Dokumen tidak ditemukan</p>
      <RouterLink :to="{ name: 'library' }" class="btn btn-primary btn-sm">Ke koleksi</RouterLink>
    </div>

    <div v-else-if="error && !doc" class="card grid place-items-center gap-3 px-6 py-16 text-center">
      <Icon icon="lucide:circle-alert" class="size-10 text-danger" />
      <p class="max-w-sm text-sm text-muted">{{ error }} Muat ulang halaman untuk mencoba lagi.</p>
      <button class="btn btn-primary btn-sm" @click="load()">
        <Icon icon="lucide:refresh-cw" class="size-4" />
        Muat ulang
      </button>
    </div>

    <template v-else-if="doc">
      <!-- Kepala dokumen -->
      <section class="card flex flex-col gap-6 p-6 sm:p-8 lg:flex-row lg:items-center lg:justify-between">
        <div class="min-w-0 space-y-3">
          <p class="eyebrow">Hasil analisis konten</p>
          <div v-if="!editing" class="flex items-start gap-2">
            <h1 class="text-3xl leading-tight font-semibold break-words sm:text-4xl">{{ doc.title }}</h1>
            <button class="btn btn-quiet btn-sm mt-1 shrink-0 !px-2.5" title="Ubah judul" aria-label="Ubah judul e-book" @click="startRename">
              <Icon icon="lucide:pencil" class="size-4" />
            </button>
          </div>
          <form v-else class="space-y-2" @submit.prevent="saveRename">
            <div class="flex flex-wrap items-center gap-2">
              <input
                ref="titleInput"
                v-model="draft"
                maxlength="255"
                class="min-w-0 flex-1 rounded-xl border border-navy/20 bg-white px-4 py-2.5 text-xl font-semibold text-navy outline-none focus:border-lavender focus:ring-2 focus:ring-lavender/30"
                aria-label="Judul e-book"
                :disabled="saving"
                @keydown.esc="cancelRename"
              />
              <button type="submit" class="btn btn-primary btn-sm" :disabled="saving">
                <Icon :icon="saving ? 'lucide:loader-circle' : 'lucide:check'" class="size-4" :class="{ 'animate-spin': saving }" />
                Simpan
              </button>
              <button type="button" class="btn btn-quiet btn-sm" :disabled="saving" @click="cancelRename">Batal</button>
            </div>
            <p v-if="renameError" class="text-sm text-danger">{{ renameError }}</p>
          </form>
          <div class="flex flex-wrap items-center gap-2">
            <StatusChip :status="doc.status" />
            <span class="chip bg-sand text-navy"><Icon icon="lucide:file-text" class="size-3.5" />{{ doc.page_count }} halaman</span>
            <span class="chip bg-sand text-navy"><Icon icon="lucide:calendar" class="size-3.5" />{{ formatDate(doc.created_at) }}</span>
          </div>
        </div>
        <div v-if="doc.status === 'done'" class="flex shrink-0 flex-col items-start gap-2 lg:items-end">
         <div class="flex flex-wrap gap-3">
          <RouterLink :to="{ name: 'reader', params: { id: doc.id } }" class="btn btn-primary">
            <Icon icon="lucide:book-open" class="size-4.5" />
            Baca dengan Safe Mode
          </RouterLink>
          <RouterLink :to="{ name: 'summary', params: { id: doc.id } }" class="btn btn-outline">
            <Icon icon="lucide:scroll-text" class="size-4.5" />
            Rangkuman
          </RouterLink>
          <SoonButton variant="outline" tier="high" icon="lucide:image-up">Ganti cover</SoonButton>
          <button class="btn btn-outline" :disabled="exporting" @click="downloadPdf">
            <Icon :icon="exporting ? 'lucide:loader-circle' : 'lucide:download'" class="size-4" :class="{ 'animate-spin': exporting }" />
            {{ exporting ? 'Menyusun PDF…' : 'Unduh hasil (PDF)' }}
          </button>
         </div>
         <p v-if="exportError" class="text-sm text-danger">{{ exportError }}</p>
        </div>
      </section>

      <!-- Sedang diproses -->
      <section v-if="doc.status === 'queued' || doc.status === 'analyzing'" class="card grid place-items-center gap-4 px-6 py-16 text-center">
        <Icon icon="lucide:loader-circle" class="size-12 animate-spin text-navy" />
        <div class="space-y-1">
          <h2 class="text-2xl font-semibold">{{ doc.status === 'queued' ? 'Menunggu giliran' : 'Sedang diproses' }}</h2>
          <p class="max-w-md text-sm text-muted">
            Perkiraan selesai {{ estimate(doc.estimated_seconds) }}. Halaman ini memperbarui diri otomatis, jadi kamu boleh menunggu di sini.
          </p>
        </div>
      </section>

      <!-- Gagal -->
      <section v-else-if="doc.status === 'failed'" class="card grid place-items-center gap-4 px-6 py-14 text-center">
        <Icon icon="lucide:circle-x" class="size-12 text-danger" />
        <div class="space-y-1">
          <h2 class="text-2xl font-semibold">Analisis gagal</h2>
          <p class="max-w-md text-sm text-muted">Sistem tidak berhasil memproses naskah ini. Unggah ulang file-nya dari halaman koleksi.</p>
        </div>
        <RouterLink :to="{ name: 'library' }" class="btn btn-primary btn-sm">Ke koleksi</RouterLink>
      </section>

      <!-- Selesai -->
      <template v-else>
        <section class="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          <article class="card space-y-3 p-6">
            <p class="eyebrow">Rating konten</p>
            <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
              <span class="font-display text-4xl font-semibold text-navy">{{ doc.rating }}</span>
              <RatingBadge :rating="doc.rating" />
            </div>
            <p class="text-sm text-muted">{{ RATINGS[doc.rating]?.note }}</p>
          </article>

          <article class="card space-y-3 p-6">
            <p class="eyebrow">Rentang usia</p>
            <div class="flex items-center gap-3">
              <span class="grid size-11 place-items-center rounded-xl bg-sand text-navy"><Icon icon="lucide:users" class="size-6" /></span>
              <span class="font-display text-4xl font-semibold text-navy">{{ doc.age_range }}</span>
            </div>
            <p class="text-sm text-muted">Usia pembaca yang disarankan berdasarkan kategori rating.</p>
          </article>

          <article class="card space-y-3 p-6">
            <p class="eyebrow">Konten dewasa</p>
            <div class="flex items-center gap-3">
              <span class="grid size-11 place-items-center rounded-xl bg-sand text-navy"><Icon icon="lucide:shield-alert" class="size-6" /></span>
              <span class="font-display text-4xl font-semibold text-navy tabular-nums">{{ num(doc.pct_adult) }}%</span>
            </div>
            <p class="text-sm text-muted">Paragraf yang terdeteksi memuat konten seksual atau kekerasan (bahasa kasar tidak dihitung).</p>
          </article>

          <article class="card space-y-3 p-6">
            <p class="eyebrow">Bobot cerita</p>
            <div class="flex items-center gap-3">
              <span class="grid size-11 place-items-center rounded-xl bg-sand text-navy"><Icon icon="lucide:weight" class="size-6" /></span>
              <span class="font-display text-4xl font-semibold text-navy tabular-nums">{{ num(doc.heaviness) }}</span>
            </div>
            <p class="text-sm text-muted">Skor 0 sampai 100: porsi paragraf beremosi sedih, marah, atau takut.</p>
          </article>
        </section>

        <!-- Rincian per dimensi + alasan rating -->
        <section class="card space-y-5 p-6 sm:p-8" aria-labelledby="rincian">
          <div class="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p class="eyebrow">Rincian rating</p>
              <h2 id="rincian" class="text-xl font-semibold">Persentase per dimensi dan alasan rating</h2>
            </div>
            <TierChip tier="middle" />
          </div>
          <div class="grid gap-4 sm:grid-cols-3">
            <div v-for="d in ['Kekerasan', 'Konten seksual', 'Bahasa kasar']" :key="d" class="space-y-2 rounded-xl bg-paper p-4">
              <div class="flex items-center justify-between text-sm font-semibold text-navy">
                <span>{{ d }}</span>
                <span class="text-muted">– %</span>
              </div>
              <div class="h-2 rounded-full bg-sand" />
            </div>
          </div>
          <p class="flex items-center gap-2 rounded-xl bg-paper p-4 text-sm text-muted">
            <Icon icon="lucide:lock" class="size-4 shrink-0 text-lavender" />
            Penjelasan kenapa buku ini mendapat rating tersebut akan muncul di sini.
          </p>
        </section>

        <!-- Fitur lanjutan -->
        <section class="space-y-4" aria-labelledby="lanjutan">
          <div>
            <p class="eyebrow">Fitur lanjutan</p>
            <h2 id="lanjutan" class="text-xl font-semibold">Kenali ceritanya lebih dalam</h2>
          </div>
          <div class="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            <article v-for="f in UPCOMING" :key="f.uc" class="card flex flex-col gap-4 p-5">
              <div class="flex items-center justify-between gap-2">
                <span class="grid size-11 place-items-center rounded-xl bg-sand text-navy"><Icon :icon="f.icon" class="size-6" /></span>
                <TierChip :tier="f.tier" />
              </div>
              <div class="space-y-1.5">
                <h3 class="text-lg font-semibold">{{ f.title }}</h3>
                <p class="text-sm text-muted">{{ f.desc }}</p>
              </div>
              <SoonButton class="mt-auto self-start" variant="quiet" small :tier="f.tier">{{ f.action }}</SoonButton>
            </article>
          </div>
        </section>

        <p class="flex items-start gap-2 text-xs text-muted">
          <Icon icon="lucide:info" class="mt-0.5 size-3.5 shrink-0" />
          Rating bersifat prediksi sistem berbasis model bahasa dan dipakai sebagai panduan awal, bukan keputusan akhir.
        </p>

        <section class="flex flex-col gap-4 rounded-2xl bg-navy p-6 sm:flex-row sm:items-center sm:justify-between sm:p-8">
          <div>
            <h2 class="text-2xl font-semibold text-white">Siap membaca?</h2>
            <p class="mt-1 text-sm text-white/70">Safe Mode menyamarkan adegan seksual. Ketuk paragraf yang ingin kamu tampilkan.</p>
          </div>
          <RouterLink :to="{ name: 'reader', params: { id: doc.id } }" class="btn btn-accent shrink-0">
            <Icon icon="lucide:shield-check" class="size-4.5" />
            Masuk mode baca
          </RouterLink>
        </section>
      </template>
    </template>
  </div>
</template>