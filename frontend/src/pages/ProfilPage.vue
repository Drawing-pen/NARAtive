<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api, { errorMessage } from '@/lib/api'
import { auth, changePassword, deleteAccount, refreshUser, renameAccount } from '@/lib/auth'
import { TX_STATUS, formatDate, rupiah, txItem } from '@/lib/content'
import CheckoutDialog from '@/components/CheckoutDialog.vue'
import TierChip from '@/components/TierChip.vue'
import UserAvatar from '@/components/UserAvatar.vue'

const route = useRoute()
const router = useRouter()

const overview = ref(null)
const transactions = ref([])
const loading = ref(true)
const error = ref('')
const checkout = ref(null)

const paid = computed(() => overview.value?.paid_tier ?? 'free')
const usage = computed(() => overview.value?.usage)
const quotaPct = computed(() => (usage.value?.monthly_limit ? Math.min(100, (usage.value.used / usage.value.monthly_limit) * 100) : 0))
const pendingCount = computed(() => transactions.value.filter((t) => t.status === 'pending').length)
const planEnds = computed(() => {
  if (paid.value === 'free') return 'Gratis, tanpa masa berlaku'
  return overview.value?.tier_expires_at ? `Aktif sampai ${formatDate(overview.value.tier_expires_at)}` : 'Tanpa batas waktu'
})

async function load() {
  try {
    const [o, t] = await Promise.all([api.get('/billing/overview'), api.get('/billing/transactions')])
    overview.value = o.data
    transactions.value = t.data
    error.value = ''
  } catch (e) {
    error.value = errorMessage(e, 'Gagal memuat profil. Muat ulang halaman.')
  } finally {
    loading.value = false
  }
}

async function onChanged() {
  await Promise.all([load(), refreshUser()])
}

const editingName = ref(false)
const nameDraft = ref('')
const nameBusy = ref(false)
const nameError = ref('')

function startRename() {
  nameDraft.value = auth.user?.name ?? ''
  nameError.value = ''
  editingName.value = true
}

async function saveName() {
  const name = nameDraft.value.trim()
  if (!name) {
    nameError.value = 'Nama tidak boleh kosong.'
    return
  }
  nameBusy.value = true
  nameError.value = ''
  try {
    await renameAccount(name)
    editingName.value = false
  } catch (e) {
    nameError.value = errorMessage(e, 'Gagal menyimpan nama. Coba lagi.')
  } finally {
    nameBusy.value = false
  }
}

const current = ref('')
const next = ref('')
const again = ref('')
const passwordBusy = ref(false)
const passwordError = ref('')
const passwordDone = ref(false)

async function savePassword() {
  passwordDone.value = false
  if (next.value.length < 8) {
    passwordError.value = 'Kata sandi baru minimal 8 karakter.'
    return
  }
  if (next.value !== again.value) {
    passwordError.value = 'Konfirmasi kata sandi baru tidak sama.'
    return
  }
  passwordBusy.value = true
  passwordError.value = ''
  try {
    await changePassword(current.value, next.value)
    current.value = next.value = again.value = ''
    passwordDone.value = true
  } catch (e) {
    passwordError.value = errorMessage(e, 'Gagal mengganti kata sandi. Coba lagi.')
  } finally {
    passwordBusy.value = false
  }
}

const confirmingDelete = ref(false)
const deletePassword = ref('')
const deleteBusy = ref(false)
const deleteError = ref('')

async function removeAccount() {
  deleteBusy.value = true
  deleteError.value = ''
  try {
    await deleteAccount(deletePassword.value)
    router.replace({ name: 'home' })
  } catch (e) {
    deleteError.value = errorMessage(e, 'Gagal menghapus akun. Coba lagi.')
  } finally {
    deleteBusy.value = false
  }
}

onMounted(async () => {
  await Promise.all([load(), refreshUser()])
  if (route.hash === '#riwayat') {
    await nextTick()
    document.getElementById('riwayat')?.scrollIntoView({ behavior: 'smooth' })
  }
})
</script>

<template>
  <div class="container-page space-y-8 py-12">
    <header class="flex items-center gap-4">
      <UserAvatar :name="auth.user?.name" size="lg" />
      <div class="min-w-0 space-y-1">
        <p class="eyebrow">Profil</p>
        <h1 class="truncate text-4xl font-semibold sm:text-5xl">{{ auth.user?.name || 'Akunmu' }}</h1>
      </div>
    </header>

    <p v-if="error" role="alert" class="rounded-lg bg-danger/10 px-3 py-2.5 text-sm text-danger">{{ error }}</p>

    <div v-if="loading" class="flex items-center justify-center gap-2 py-16 text-muted">
      <Icon icon="lucide:loader-circle" class="size-5 animate-spin" />
      Memuat…
    </div>

    <template v-else>
      <section class="grid gap-6 lg:grid-cols-2" aria-label="Akun dan pemakaian">
        <article class="card space-y-5 p-7">
          <h2 class="text-xl font-semibold">Informasi akun</h2>
          <dl class="space-y-4 text-sm">
            <div class="space-y-1.5">
              <dt class="eyebrow">Nama</dt>
              <dd v-if="!editingName" class="flex items-center gap-2">
                <span class="min-w-0 truncate text-base font-semibold text-navy" data-test="name">{{ auth.user?.name }}</span>
                <button type="button" class="btn btn-quiet btn-sm !px-2.5" title="Ubah nama" aria-label="Ubah nama" @click="startRename">
                  <Icon icon="lucide:pencil" class="size-4" />
                </button>
              </dd>
              <dd v-else class="space-y-2">
                <form class="flex flex-wrap gap-2" @submit.prevent="saveName">
                  <input v-model="nameDraft" class="input min-w-0 flex-1" type="text" maxlength="100" aria-label="Nama" autocomplete="name" />
                  <button type="submit" class="btn btn-primary btn-sm" :disabled="nameBusy">Simpan</button>
                  <button type="button" class="btn btn-quiet btn-sm" :disabled="nameBusy" @click="editingName = false">Batal</button>
                </form>
                <p v-if="nameError" role="alert" class="text-xs text-danger">{{ nameError }}</p>
              </dd>
            </div>
            <div class="space-y-1.5">
              <dt class="eyebrow">Email</dt>
              <dd class="text-base text-navy" data-test="email">{{ auth.user?.email }}</dd>
            </div>
            <div class="space-y-1.5">
              <dt class="eyebrow">Bergabung sejak</dt>
              <dd class="text-base text-navy">{{ auth.user?.created_at ? formatDate(auth.user.created_at) : '-' }}</dd>
            </div>
            <div class="space-y-1.5">
              <dt class="eyebrow">Paket</dt>
              <dd class="flex flex-wrap items-center gap-2">
                <TierChip :tier="paid === 'free' ? 'standard' : paid" />
                <span class="text-muted" data-test="plan-ends">{{ planEnds }}</span>
                <RouterLink :to="{ name: 'plans' }" class="text-sm font-semibold text-navy underline decoration-amber decoration-2 underline-offset-4">Ubah paket</RouterLink>
              </dd>
            </div>
          </dl>
        </article>

        <article v-if="usage" class="card space-y-5 p-7" data-test="usage">
          <h2 class="text-xl font-semibold">Pemakaian</h2>
          <div class="space-y-2">
            <div class="flex items-baseline justify-between gap-3">
              <p class="eyebrow">Analisis bulan ini</p>
              <p class="text-sm font-semibold text-navy tabular-nums">
                {{ usage.used }}<template v-if="usage.monthly_limit !== null"> / {{ usage.monthly_limit }}</template><template v-else> (tanpa batas)</template>
              </p>
            </div>
            <div v-if="usage.monthly_limit !== null" class="h-2 overflow-hidden rounded-full bg-sand" role="progressbar" :aria-valuenow="usage.used" aria-valuemin="0" :aria-valuemax="usage.monthly_limit">
              <div class="h-full rounded-full bg-navy" :style="{ width: `${quotaPct}%` }" />
            </div>
            <p v-if="usage.monthly_limit !== null" class="text-xs text-muted">Direset {{ formatDate(usage.resets_at) }}</p>
          </div>
          <dl class="grid grid-cols-2 gap-4 text-sm">
            <div class="space-y-1">
              <dt class="eyebrow">Analisis tambahan</dt>
              <dd class="text-base font-semibold text-navy tabular-nums" data-test="extra">{{ usage.extra_checks }}</dd>
            </div>
            <div class="space-y-1">
              <dt class="eyebrow">E-book aktif</dt>
              <dd class="text-base font-semibold text-navy tabular-nums" data-test="books">{{ usage.active_books }}<template v-if="usage.max_active !== null"> / {{ usage.max_active }}</template></dd>
            </div>
            <div class="col-span-2 space-y-1">
              <dt class="eyebrow">Batas halaman per unggahan</dt>
              <dd class="text-base text-navy">{{ usage.max_pages !== null ? `${usage.max_pages} halaman` : 'Tanpa batas' }}</dd>
            </div>
          </dl>
        </article>
      </section>

      <article id="riwayat" class="card space-y-4 p-7">
        <div class="flex items-center justify-between gap-3">
          <div class="flex items-center gap-3">
            <span class="grid size-11 place-items-center rounded-xl bg-sand text-navy"><Icon icon="lucide:receipt" class="size-6" /></span>
            <h2 class="text-xl font-semibold">Riwayat pembayaran</h2>
          </div>
          <span v-if="pendingCount" class="chip bg-amber/35 text-navy">{{ pendingCount }} menunggu</span>
        </div>

        <div v-if="!transactions.length" class="grid place-items-center gap-2 rounded-xl border border-dashed border-line px-4 py-6 text-center" data-test="no-history">
          <Icon icon="lucide:inbox" class="size-7 text-lavender" />
          <p class="text-sm text-muted">Belum ada riwayat pembayaran. Riwayat upgrade dan pembelian analisis akan tampil di sini.</p>
        </div>
        <ul v-else class="divide-y divide-line">
          <li v-for="t in transactions" :key="t.order_id" class="flex flex-wrap items-center gap-x-4 gap-y-2 py-3" data-test="transaction">
            <div class="min-w-0 flex-1">
              <p class="truncate text-sm font-semibold text-navy">{{ txItem(t) }}</p>
              <p class="text-xs text-muted">{{ formatDate(t.created_at) }} · {{ t.order_id }}</p>
            </div>
            <span class="text-sm font-semibold text-navy tabular-nums">{{ rupiah(t.amount) }}</span>
            <span class="chip" :class="TX_STATUS[t.status].cls"><Icon :icon="TX_STATUS[t.status].icon" class="size-3" />{{ TX_STATUS[t.status].label }}</span>
            <button v-if="t.status === 'pending'" type="button" class="btn btn-accent btn-sm" @click="checkout = { resume: t }">Lanjutkan bayar</button>
          </li>
        </ul>
      </article>

      <section class="grid gap-6 lg:grid-cols-2" aria-label="Keamanan">
        <form class="card space-y-4 p-7" novalidate @submit.prevent="savePassword">
          <h2 class="text-xl font-semibold">Ganti kata sandi</h2>
          <div class="space-y-1.5">
            <label for="sandi-lama" class="text-sm font-semibold text-navy">Kata sandi saat ini</label>
            <input id="sandi-lama" v-model="current" class="input" type="password" autocomplete="current-password" maxlength="72" />
          </div>
          <div class="space-y-1.5">
            <label for="sandi-baru" class="text-sm font-semibold text-navy">Kata sandi baru</label>
            <input id="sandi-baru" v-model="next" class="input" type="password" autocomplete="new-password" maxlength="72" />
          </div>
          <div class="space-y-1.5">
            <label for="sandi-ulang" class="text-sm font-semibold text-navy">Ulangi kata sandi baru</label>
            <input id="sandi-ulang" v-model="again" class="input" type="password" autocomplete="new-password" maxlength="72" />
          </div>
          <p v-if="passwordError" role="alert" class="rounded-lg bg-danger/10 px-3 py-2.5 text-sm text-danger">{{ passwordError }}</p>
          <p v-if="passwordDone" role="status" class="rounded-lg bg-lavender/20 px-3 py-2.5 text-sm text-navy">Kata sandi berhasil diganti.</p>
          <button type="submit" class="btn btn-primary" :disabled="passwordBusy || !current || !next || !again">
            <Icon v-if="passwordBusy" icon="lucide:loader-circle" class="size-4 animate-spin" />
            Simpan kata sandi
          </button>
        </form>

        <article class="card space-y-4 border-danger/40 p-7">
          <h2 class="text-xl font-semibold text-danger">Hapus akun</h2>
          <p class="text-sm text-muted">
            Akun, semua e-book beserta hasil analisisnya, koleksi, dan riwayat pembayaran dihapus permanen dan tidak bisa dikembalikan.
            Paket berbayar yang masih berlaku ikut hangus tanpa pengembalian dana.
          </p>
          <button v-if="!confirmingDelete" type="button" class="btn btn-outline btn-sm !border-danger !text-danger" @click="confirmingDelete = true">
            <Icon icon="lucide:trash-2" class="size-4" />
            Hapus akun saya
          </button>
          <form v-else class="space-y-3" @submit.prevent="removeAccount">
            <div class="space-y-1.5">
              <label for="sandi-hapus" class="text-sm font-semibold text-navy">Masukkan kata sandi untuk konfirmasi</label>
              <input id="sandi-hapus" v-model="deletePassword" class="input" type="password" autocomplete="current-password" maxlength="72" />
            </div>
            <p v-if="deleteError" role="alert" class="rounded-lg bg-danger/10 px-3 py-2.5 text-sm text-danger">{{ deleteError }}</p>
            <div class="flex flex-wrap gap-2">
              <button type="submit" class="btn btn-primary btn-sm !bg-danger" :disabled="deleteBusy || !deletePassword">Hapus permanen</button>
              <button type="button" class="btn btn-quiet btn-sm" :disabled="deleteBusy" @click="confirmingDelete = false; deletePassword = ''; deleteError = ''">Batal</button>
            </div>
          </form>
        </article>
      </section>
    </template>

    <CheckoutDialog
      v-if="checkout && overview"
      :request="null"
      :resume="checkout.resume"
      :banks="overview.banks"
      :provider="overview.provider"
      @close="checkout = null"
      @changed="onChanged"
    />
  </div>
</template>
