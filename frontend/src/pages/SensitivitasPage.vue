<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import api, { errorMessage } from '@/lib/api'
import { DIMENSIONS, STANDARD_SAFE_MODE, STANDARD_THRESHOLDS, num } from '@/lib/content'
import TierChip from '@/components/TierChip.vue'

const props = defineProps({ id: { type: String, required: true } })

const MIN = 0.1
const MAX = 0.95
const KEYS = Object.keys(DIMENSIONS)

const doc = ref(null)
const paragraphs = ref([])
const profile = ref(null)
const loading = ref(true)
const missing = ref(false)
const error = ref('')
const notice = ref('')
const saving = ref(false)

// draft per jenis konten: on = disamarkan, value = ambang (skor model minimal agar disamarkan)
const draft = reactive(Object.fromEntries(KEYS.map((k) => [k, { on: false, value: STANDARD_THRESHOLDS[k] }])))

function fill(thresholds) {
  for (const k of KEYS) {
    draft[k].on = thresholds[k] !== null && thresholds[k] !== undefined
    draft[k].value = thresholds[k] ?? STANDARD_THRESHOLDS[k]
  }
}

const round = (v) => Math.round(v * 100) / 100
const payload = () => Object.fromEntries(KEYS.map((k) => [k, draft[k].on ? round(draft[k].value) : null]))

const editable = computed(() => profile.value?.editable ?? false)
const standard = computed(() => profile.value?.standard ?? STANDARD_SAFE_MODE)
const dirty = computed(() => {
  if (!profile.value) return false
  const saved = profile.value.thresholds
  const now = payload()
  return KEYS.some((k) => (saved[k] ?? null) !== now[k])
})
const isStandard = computed(() => KEYS.every((k) => (standard.value[k] ?? null) === payload()[k]))

const ready = computed(() => doc.value?.status === 'done')
const hitCount = (k) => (draft[k].on ? paragraphs.value.filter((p) => p[k] !== null && p[k] >= round(draft[k].value)).length : 0)
const totalHidden = computed(() => {
  const now = payload()
  return paragraphs.value.filter((p) => KEYS.some((k) => now[k] !== null && p[k] !== null && p[k] >= now[k])).length
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [d, s] = await Promise.all([api.get(`/documents/${props.id}`), api.get('/sensitivity')])
    doc.value = d.data
    profile.value = s.data
    fill(s.data.thresholds)
    if (d.data.status === 'done') paragraphs.value = (await api.get(`/documents/${props.id}/paragraphs`)).data
  } catch (e) {
    if (e.response?.status === 404) missing.value = true
    else error.value = errorMessage(e, 'Gagal memuat profil sensitivitas.')
  } finally {
    loading.value = false
  }
}

async function request(call, done) {
  saving.value = true
  error.value = ''
  notice.value = ''
  try {
    profile.value = (await call()).data
    fill(profile.value.thresholds)
    notice.value = done
  } catch (e) {
    error.value = errorMessage(e, 'Gagal menyimpan pengaturan. Coba lagi.')
  } finally {
    saving.value = false
  }
}
const save = () => request(() => api.put('/sensitivity', payload()), 'Pengaturan tersimpan dan dipakai di Safe Mode.')
const reset = () => request(() => api.delete('/sensitivity'), 'Dikembalikan ke pengaturan standar.')

onMounted(load)
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

    <div v-else-if="!profile" class="card grid place-items-center gap-3 px-6 py-14 text-center">
      <Icon icon="lucide:circle-alert" class="size-10 text-danger" />
      <p class="text-sm text-muted">{{ error }}</p>
      <button class="btn btn-primary btn-sm" @click="load">
        <Icon icon="lucide:refresh-cw" class="size-4" />
        Coba lagi
      </button>
    </div>

    <template v-else>
      <section class="space-y-2">
        <div class="flex flex-wrap items-center gap-2">
          <p class="eyebrow">Profil sensitivitas</p>
          <TierChip tier="high" />
        </div>
        <h1 class="text-3xl leading-tight font-semibold sm:text-4xl">Atur kapan paragraf disamarkan</h1>
        <p class="max-w-2xl text-muted">
          Safe Mode menyamarkan paragraf yang skor deteksinya mencapai ambang batas. Makin kecil ambang, makin ketat:
          lebih banyak paragraf disamarkan. Pengaturan ini berlaku di semua buku dan sesi baca berikutnya.
        </p>
      </section>

      <section v-if="!editable" class="card flex flex-col gap-4 border-amber bg-amber/10 p-6 sm:flex-row sm:items-center sm:justify-between">
        <div class="flex items-start gap-3">
          <Icon icon="lucide:lock" class="mt-0.5 size-5 shrink-0 text-navy" />
          <div class="space-y-1">
            <p class="font-semibold text-navy">Khusus pengguna High Tier</p>
            <p class="text-sm text-muted">Akunmu memakai Safe Mode standar, yang hanya menyamarkan konten seksual. Naikkan ke High Tier untuk mengatur sendiri ambangnya.</p>
          </div>
        </div>
        <RouterLink :to="{ name: 'plans' }" class="btn btn-accent btn-sm shrink-0">Lihat paket</RouterLink>
      </section>

      <p v-if="error" role="alert" class="flex items-start gap-2 rounded-lg bg-danger/10 px-3 py-2.5 text-sm text-danger">
        <Icon icon="lucide:circle-alert" class="mt-0.5 size-4 shrink-0" />
        {{ error }}
      </p>
      <p v-else-if="notice" role="status" class="flex items-start gap-2 rounded-lg bg-lavender/20 px-3 py-2.5 text-sm text-navy">
        <Icon icon="lucide:circle-check" class="mt-0.5 size-4 shrink-0" />
        {{ notice }}
      </p>

      <section class="grid gap-5 lg:grid-cols-3" aria-label="Ambang batas per jenis konten">
        <article v-for="k in KEYS" :key="k" class="card flex flex-col gap-5 p-6" :class="{ 'opacity-70': !editable }">
          <div class="flex items-start justify-between gap-3">
            <div class="flex items-center gap-3">
              <span class="grid size-11 place-items-center rounded-xl bg-sand text-navy"><Icon :icon="DIMENSIONS[k].icon" class="size-6" /></span>
              <h2 class="text-lg font-semibold">{{ DIMENSIONS[k].label }}</h2>
            </div>
            <label class="inline-flex shrink-0 cursor-pointer items-center gap-2 text-sm font-semibold text-navy" :class="{ 'cursor-not-allowed': !editable }">
              <input v-model="draft[k].on" type="checkbox" class="size-4 accent-navy" :disabled="!editable" />
              Samarkan
            </label>
          </div>

          <div class="space-y-2" :class="{ 'opacity-40': !draft[k].on }">
            <div class="flex items-baseline justify-between">
              <span class="eyebrow">Ambang</span>
              <span class="font-display text-2xl font-semibold text-navy tabular-nums">{{ num(round(draft[k].value)) }}</span>
            </div>
            <input
              v-model.number="draft[k].value"
              type="range"
              :min="MIN"
              :max="MAX"
              step="0.05"
              class="w-full accent-navy"
              :disabled="!editable || !draft[k].on"
              :aria-label="`Ambang ${DIMENSIONS[k].label}`"
            />
            <div class="flex justify-between text-xs text-muted">
              <span>Lebih ketat</span>
              <span>Lebih longgar</span>
            </div>
          </div>

          <div class="mt-auto space-y-1 text-sm">
            <p class="text-muted">
              Standar:
              <span class="font-semibold text-navy">{{ standard[k] === null ? 'tidak disamarkan' : num(standard[k]) }}</span>
            </p>
            <p v-if="ready" class="text-muted">
              Di buku ini:
              <span class="font-semibold text-navy">{{ draft[k].on ? `${hitCount(k)} paragraf` : 'tidak ada' }}</span>
            </p>
          </div>
        </article>
      </section>

      <section class="card flex flex-col gap-4 p-6 sm:flex-row sm:items-center sm:justify-between">
        <p v-if="ready" class="text-sm text-muted">
          Dengan pengaturan ini, <span class="font-semibold text-navy">{{ totalHidden }} dari {{ paragraphs.length }} paragraf</span>
          di <span class="font-semibold text-navy">{{ doc.title }}</span> akan disamarkan.
        </p>
        <p v-else class="text-sm text-muted">Pratinjau jumlah paragraf tersedia setelah analisis buku ini selesai.</p>
        <div class="flex flex-wrap gap-2">
          <button class="btn btn-quiet btn-sm" :disabled="!editable || saving || (isStandard && !profile.personal)" @click="reset">
            <Icon icon="lucide:rotate-ccw" class="size-4" />
            Kembalikan ke standar
          </button>
          <button class="btn btn-primary btn-sm" :disabled="!editable || saving || !dirty" @click="save">
            <Icon :icon="saving ? 'lucide:loader-circle' : 'lucide:save'" class="size-4" :class="{ 'animate-spin': saving }" />
            Simpan pengaturan
          </button>
        </div>
      </section>

      <RouterLink :to="{ name: 'reader', params: { id } }" class="btn btn-outline btn-sm">
        <Icon icon="lucide:book-open" class="size-4" />
        Buka mode baca
      </RouterLink>
    </template>
  </div>
</template>
