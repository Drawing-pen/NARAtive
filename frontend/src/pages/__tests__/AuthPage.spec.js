import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const login = vi.fn()
const startRegistration = vi.fn()
const resendCode = vi.fn()
const verifyRegistration = vi.fn()
const requestPasswordReset = vi.fn()
const resetPassword = vi.fn()
const replace = vi.fn()
const route = { query: {} }

vi.mock('@/lib/api', () => ({
  errorMessage: (e, fallback) => e?.response?.data?.detail ?? fallback,
}))
vi.mock('@/lib/auth', () => ({
  login: (...args) => login(...args),
  startRegistration: (...args) => startRegistration(...args),
  resendCode: (...args) => resendCode(...args),
  verifyRegistration: (...args) => verifyRegistration(...args),
  requestPasswordReset: (...args) => requestPasswordReset(...args),
  resetPassword: (...args) => resetPassword(...args),
}))
vi.mock('vue-router', () => ({ useRoute: () => route, useRouter: () => ({ replace }) }))

import AuthPage from '@/pages/AuthPage.vue'

const STARTED = { email: 'rana@example.com', expires_in: 600, resend_after: 60 }

function open(mode) {
  return mount(AuthPage, {
    props: { mode },
    global: {
      stubs: {
        Icon: true,
        RouterLink: { props: ['to'], template: '<a :data-to="JSON.stringify(to)"><slot /></a>' },
        Logo: { props: { mark: Boolean }, template: '<i data-test="logo" :data-mark="String(mark)" />' },
      },
    },
  })
}

const button = (w, text) => w.findAll('button').find((b) => b.text().includes(text))

async function ask(w, email = ' rana@example.com ') {
  await w.find('#email').setValue(email)
  await w.find('form').trigger('submit')
  await flushPromises()
}

beforeEach(() => {
  vi.clearAllMocks()
  route.query = {}
  requestPasswordReset.mockResolvedValue(STARTED)
  resetPassword.mockResolvedValue()
})

describe('logo', () => {
  it.each(['masuk', 'daftar', 'lupa'])('halaman %s memakai logo tanpa tulisan', (mode) => {
    expect(open(mode).find('[data-test="logo"]').attributes('data-mark')).toBe('true')
  })
})

describe('tautan lupa kata sandi', () => {
  it('muncul di halaman masuk dan menuju rute forgot', () => {
    const link = open('masuk').findAll('a').find((a) => a.text() === 'Lupa kata sandi?')
    expect(JSON.parse(link.attributes('data-to')).name).toBe('forgot')
  })

  it('tidak muncul di halaman daftar', () => {
    expect(open('daftar').text()).not.toContain('Lupa kata sandi?')
  })

  it('membawa tujuan setelah masuk ke halaman lupa kata sandi', () => {
    route.query = { next: '/buku/3' }
    const link = open('masuk').findAll('a').find((a) => a.text() === 'Lupa kata sandi?')
    expect(JSON.parse(link.attributes('data-to')).query).toEqual({ next: '/buku/3' })
  })
})

describe('lupa kata sandi, langkah email', () => {
  it('hanya meminta email', () => {
    const w = open('lupa')
    expect(w.text()).toContain('Atur ulang kata sandi')
    expect(w.find('#email').exists()).toBe(true)
    expect(w.find('#sandi').exists()).toBe(false)
    expect(w.find('#nama').exists()).toBe(false)
    expect(button(w, 'Kirim kode')).toBeTruthy()
  })

  it('menolak email kosong tanpa memanggil server', async () => {
    const w = open('lupa')
    await ask(w, '  ')
    expect(w.text()).toContain('Email wajib diisi.')
    expect(requestPasswordReset).not.toHaveBeenCalled()
  })

  it('meminta kode dengan email yang dirapikan lalu pindah ke langkah kode', async () => {
    const w = open('lupa')
    await ask(w)
    expect(requestPasswordReset).toHaveBeenCalledWith('rana@example.com')
    expect(w.text()).toContain('Jika email terdaftar, kode 6 angka sudah dikirim ke rana@example.com')
    expect(w.text()).toContain('Kode berlaku 10 menit.')
    expect(w.find('#kode').exists()).toBe(true)
    expect(w.find('#sandi').attributes('autocomplete')).toBe('new-password')
  })

  it('menampilkan galat server apa adanya', async () => {
    requestPasswordReset.mockRejectedValue({ response: { status: 422, data: { detail: 'Email tidak valid.' } } })
    const w = open('lupa')
    await ask(w)
    expect(w.text()).toContain('Email tidak valid.')
    expect(w.find('#kode').exists()).toBe(false)
  })

  it('punya tautan kembali ke halaman masuk', () => {
    const w = open('lupa')
    expect(w.findAll('a').some((a) => JSON.parse(a.attributes('data-to') ?? '{}').name === 'login')).toBe(true)
  })
})

describe('lupa kata sandi, langkah kode', () => {
  async function atCodeStep() {
    const w = open('lupa')
    await ask(w)
    return w
  }

  async function fill(w, code, password) {
    await w.find('#kode').setValue(code)
    await w.find('#sandi').setValue(password)
    await w.find('form').trigger('submit')
    await flushPromises()
  }

  it('menolak kode yang bukan 6 angka', async () => {
    const w = await atCodeStep()
    await fill(w, '12345', 'sandi-baru-456')
    expect(w.text()).toContain('Masukkan kode 6 angka dari emailmu.')
    expect(resetPassword).not.toHaveBeenCalled()
  })

  it('menolak kata sandi di bawah 8 karakter', async () => {
    const w = await atCodeStep()
    await fill(w, '123456', 'pendek')
    expect(w.text()).toContain('Kata sandi minimal 8 karakter.')
    expect(resetPassword).not.toHaveBeenCalled()
  })

  it('mengatur ulang kata sandi lalu masuk ke koleksi', async () => {
    const w = await atCodeStep()
    await fill(w, '123456', 'sandi-baru-456')
    expect(resetPassword).toHaveBeenCalledWith('rana@example.com', '123456', 'sandi-baru-456')
    expect(replace).toHaveBeenCalledWith('/koleksi')
  })

  it('menuju halaman tujuan bila ada', async () => {
    route.query = { next: '/buku/3' }
    const w = await atCodeStep()
    await fill(w, '123456', 'sandi-baru-456')
    expect(replace).toHaveBeenCalledWith('/buku/3')
  })

  it('menampilkan galat kode salah dan tetap di langkah kode', async () => {
    resetPassword.mockRejectedValue({ response: { status: 400, data: { detail: 'Kode salah atau sudah kedaluwarsa. Minta kode baru.' } } })
    const w = await atCodeStep()
    await fill(w, '123456', 'sandi-baru-456')
    expect(w.text()).toContain('Kode salah atau sudah kedaluwarsa. Minta kode baru.')
    expect(w.find('#kode').exists()).toBe(true)
    expect(replace).not.toHaveBeenCalled()
  })

  it('tombol kirim ulang menghitung mundur dari 60 detik', async () => {
    const w = await atCodeStep()
    expect(button(w, 'Kirim ulang kode').text()).toContain('(60 dtk)')
    expect(button(w, 'Kirim ulang kode').attributes('disabled')).toBeDefined()
  })

  it('mengirim ulang kode setelah hitung mundur selesai', async () => {
    requestPasswordReset.mockResolvedValue({ ...STARTED, resend_after: 0 })
    const w = await atCodeStep()
    await button(w, 'Kirim ulang kode').trigger('click')
    await flushPromises()
    expect(requestPasswordReset).toHaveBeenCalledTimes(2)
    expect(w.text()).toContain('Kode baru sudah dikirim.')
  })

  it('ubah email kembali ke langkah email', async () => {
    const w = await atCodeStep()
    await button(w, 'Ubah email').trigger('click')
    expect(w.find('#kode').exists()).toBe(false)
    expect(w.find('#email').element.value).toBe('rana@example.com')
  })
})

describe('masuk dan daftar tetap seperti semula', () => {
  it('masuk memanggil login', async () => {
    login.mockResolvedValue()
    const w = open('masuk')
    await w.find('#email').setValue('rana@example.com')
    await w.find('#sandi').setValue('sandi-uji-123')
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(login).toHaveBeenCalledWith('rana@example.com', 'sandi-uji-123')
    expect(replace).toHaveBeenCalledWith('/koleksi')
  })

  it('daftar meminta nama, email, dan kata sandi', async () => {
    startRegistration.mockResolvedValue(STARTED)
    const w = open('daftar')
    await w.find('#nama').setValue('Rana')
    await w.find('#email').setValue('rana@example.com')
    await w.find('#sandi').setValue('sandi-uji-123')
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(startRegistration).toHaveBeenCalledWith('Rana', 'rana@example.com', 'sandi-uji-123')
    expect(w.text()).toContain('Kami mengirim kode 6 angka')
  })
})
