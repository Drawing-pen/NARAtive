<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { errorMessage } from '@/lib/api'
import { login, resendCode, startRegistration, verifyRegistration } from '@/lib/auth'
import Logo from '@/components/Logo.vue'

const props = defineProps({ mode: { type: String, required: true } })

const route = useRoute()
const router = useRouter()

const isRegister = computed(() => props.mode === 'daftar')
const name = ref('')
const email = ref('')
const password = ref('')
const showPassword = ref(false)
const busy = ref(false)
const error = ref('')
const step = ref('form')
const code = ref('')
const cooldown = ref(0)
const info = ref('')
let timer = null

const inCodeStep = computed(() => isRegister.value && step.value === 'code')

function startCooldown(seconds) {
  clearInterval(timer)
  cooldown.value = seconds
  timer = setInterval(() => {
    cooldown.value -= 1
    if (cooldown.value <= 0) clearInterval(timer)
  }, 1000)
}
onBeforeUnmount(() => clearInterval(timer))

const notice = computed(() => (route.query.expired ? 'Sesimu berakhir. Silakan masuk lagi.' : ''))

function nextPath() {
  const next = route.query.next
  return typeof next === 'string' && next.startsWith('/') && !next.startsWith('//') ? next : '/koleksi'
}

function validate() {
  if (inCodeStep.value) return /^\d{6}$/.test(code.value) ? '' : 'Masukkan kode 6 angka dari emailmu.'
  if (isRegister.value && !name.value.trim()) return 'Nama wajib diisi.'
  if (!email.value.trim()) return 'Email wajib diisi.'
  if (isRegister.value && password.value.length < 8) return 'Kata sandi minimal 8 karakter.'
  if (!password.value) return 'Kata sandi wajib diisi.'
  return ''
}

async function submit() {
  error.value = validate()
  if (error.value) return
  busy.value = true
  try {
    if (inCodeStep.value) {
      await verifyRegistration(email.value.trim(), code.value)
      router.replace(nextPath())
    } else if (isRegister.value) {
      const started = await startRegistration(name.value.trim(), email.value.trim(), password.value)
      step.value = 'code'
      code.value = ''
      info.value = ''
      startCooldown(started.resend_after)
    } else {
      await login(email.value.trim(), password.value)
      router.replace(nextPath())
    }
  } catch (e) {
    error.value = errorMessage(e, isRegister.value ? 'Pendaftaran gagal. Coba lagi.' : 'Gagal masuk. Coba lagi.')
    if (inCodeStep.value && (e.response?.status === 404 || (e.response?.status === 429 && /Mulai pendaftaran lagi/.test(error.value)))) backToForm(error.value)
  } finally {
    busy.value = false
  }
}

async function resend() {
  error.value = ''
  info.value = ''
  busy.value = true
  try {
    const started = await resendCode(email.value.trim())
    code.value = ''
    info.value = 'Kode baru sudah dikirim.'
    startCooldown(started.resend_after)
  } catch (e) {
    error.value = errorMessage(e, 'Gagal mengirim ulang kode. Coba lagi.')
  } finally {
    busy.value = false
  }
}

function backToForm(message = '') {
  step.value = 'form'
  code.value = ''
  info.value = ''
  clearInterval(timer)
  cooldown.value = 0
  error.value = message
}

const otherRoute = computed(() => ({ name: isRegister.value ? 'login' : 'register', query: route.query }))
</script>

<template>
  <div class="grid min-h-screen place-items-center px-4 py-10">
    <div class="w-full max-w-md space-y-6">
      <RouterLink :to="{ name: 'home' }" aria-label="NARAtive, ke beranda" class="mx-auto block w-fit">
        <Logo />
      </RouterLink>

      <section class="card p-6 sm:p-8">
        <div class="space-y-1">
          <p class="eyebrow">{{ inCodeStep ? 'Verifikasi email' : isRegister ? 'Akun baru' : 'Selamat datang kembali' }}</p>
          <h1 class="text-3xl font-semibold">{{ inCodeStep ? 'Masukkan kode' : isRegister ? 'Daftar' : 'Masuk' }}</h1>
          <p v-if="inCodeStep" class="text-[15px] text-muted">
            Kami mengirim kode 6 angka ke <strong class="text-navy">{{ email.trim() }}</strong>. Kode berlaku 10 menit.
          </p>
          <p v-else class="text-[15px] text-muted">
            {{ isRegister ? 'Buat akun untuk menyimpan koleksi dan hasil analisis e-book-mu.' : 'Masuk untuk membuka koleksi dan hasil analisis e-book-mu.' }}
          </p>
        </div>

        <p v-if="notice" class="mt-4 rounded-lg bg-amber/25 px-3 py-2 text-sm text-navy" role="status">{{ notice }}</p>

        <form class="mt-6 space-y-4" novalidate @submit.prevent="submit">
          <div v-if="inCodeStep" class="space-y-1.5">
            <label for="kode" class="text-sm font-semibold text-navy">Kode verifikasi</label>
            <div class="relative">
              <Icon icon="lucide:shield-check" class="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted" />
              <input
                id="kode"
                v-model="code"
                class="input tracking-[0.4em]"
                type="text"
                inputmode="numeric"
                autocomplete="one-time-code"
                maxlength="6"
                placeholder="000000"
              />
            </div>
            <div class="flex flex-wrap items-center justify-between gap-2 text-sm">
              <button type="button" class="font-semibold text-navy underline decoration-amber decoration-2 underline-offset-4 disabled:cursor-not-allowed disabled:no-underline disabled:opacity-50" :disabled="busy || cooldown > 0" @click="resend">
                {{ cooldown > 0 ? `Kirim ulang kode (${cooldown} dtk)` : 'Kirim ulang kode' }}
              </button>
              <button type="button" class="text-muted hover:text-navy" :disabled="busy" @click="backToForm()">Ubah email atau data</button>
            </div>
          </div>

          <div v-if="isRegister && !inCodeStep" class="space-y-1.5">
            <label for="nama" class="text-sm font-semibold text-navy">Nama</label>
            <div class="relative">
              <Icon icon="lucide:user" class="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted" />
              <input id="nama" v-model="name" class="input" type="text" autocomplete="name" maxlength="100" placeholder="Nama lengkapmu" />
            </div>
          </div>

          <div v-if="!inCodeStep" class="space-y-1.5">
            <label for="email" class="text-sm font-semibold text-navy">Email</label>
            <div class="relative">
              <Icon icon="lucide:mail" class="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted" />
              <input id="email" v-model="email" class="input" type="email" autocomplete="email" inputmode="email" placeholder="kamu@contoh.com" />
            </div>
          </div>

          <div v-if="!inCodeStep" class="space-y-1.5">
            <label for="sandi" class="text-sm font-semibold text-navy">Kata sandi</label>
            <div class="relative">
              <Icon icon="lucide:lock" class="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted" />
              <input
                id="sandi"
                v-model="password"
                class="input !pr-11"
                :type="showPassword ? 'text' : 'password'"
                :autocomplete="isRegister ? 'new-password' : 'current-password'"
                maxlength="72"
                :placeholder="isRegister ? 'Minimal 8 karakter' : 'Kata sandimu'"
              />
              <button
                type="button"
                class="absolute top-1/2 right-2 grid size-8 -translate-y-1/2 place-items-center rounded-md text-muted hover:bg-sand hover:text-navy"
                :aria-label="showPassword ? 'Sembunyikan kata sandi' : 'Tampilkan kata sandi'"
                :aria-pressed="showPassword"
                @click="showPassword = !showPassword"
              >
                <Icon :icon="showPassword ? 'lucide:eye-off' : 'lucide:eye'" class="size-4" />
              </button>
            </div>
          </div>

          <p v-if="info" class="rounded-lg bg-lavender/20 px-3 py-2 text-sm text-navy" role="status">{{ info }}</p>

          <p v-if="error" class="flex items-start gap-2 rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger" role="alert">
            <Icon icon="lucide:circle-alert" class="mt-0.5 size-4 shrink-0" />
            <span>{{ error }}</span>
          </p>

          <button type="submit" class="btn btn-primary w-full" :disabled="busy">
            <Icon v-if="busy" icon="lucide:loader-circle" class="size-4 animate-spin" />
            {{ busy ? 'Memproses…' : inCodeStep ? 'Verifikasi dan daftar' : isRegister ? 'Kirim kode verifikasi' : 'Masuk' }}
          </button>
        </form>

        <p class="mt-6 text-center text-sm text-muted">
          {{ isRegister ? 'Sudah punya akun?' : 'Belum punya akun?' }}
          <RouterLink :to="otherRoute" class="font-semibold text-navy underline decoration-amber decoration-2 underline-offset-4">
            {{ isRegister ? 'Masuk' : 'Daftar' }}
          </RouterLink>
        </p>
      </section>

      <p class="text-center text-sm">
        <RouterLink :to="{ name: 'home' }" class="inline-flex items-center gap-1.5 text-muted hover:text-navy">
          <Icon icon="lucide:arrow-left" class="size-4" />
          Kembali ke beranda
        </RouterLink>
      </p>
    </div>
  </div>
</template>