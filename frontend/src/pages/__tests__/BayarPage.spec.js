import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'

const get = vi.fn()
const post = vi.fn()
const refreshUser = vi.fn()

vi.mock('@/lib/api', () => ({
  default: { get: (...args) => get(...args), post: (...args) => post(...args) },
  errorMessage: (e, fallback) => e?.response?.data?.detail ?? fallback,
}))
vi.mock('@/lib/auth', () => ({
  auth: { user: { name: 'Rana Dzikro', email: 'rana@example.com', tier: 'free' } },
  refreshUser: (...args) => refreshUser(...args),
}))

import BayarPage from '@/pages/BayarPage.vue'

const OVERVIEW = (o = {}) => ({
  upgrade_prices: { middle: 29000, high: 59000 },
  pay_per_check_price: 5000,
  period_days: 30,
  banks: ['bca', 'bni', 'bri', 'permata'],
  provider: 'simulated',
  ...o,
})
const TX = (o = {}) => ({
  order_id: 'NAR-1-abcdef', kind: 'upgrade', plan: 'middle', quantity: 1, amount: 29000, bank: 'bca', va_number: '3935812345678901',
  provider: 'simulated', status: 'pending', created_at: '2026-11-01T08:00:00', expires_at: '2026-11-01T09:02:03', ...o,
})

let overview
let txState
const stub = { template: '<div />' }

function serve({ over = OVERVIEW(), tx = TX() } = {}) {
  overview = over
  txState = tx
  get.mockImplementation(async (url) => {
    if (url === '/billing/overview') return { data: overview }
    if (url.startsWith('/billing/transactions/')) {
      if (txState instanceof Error) throw txState
      return { data: txState }
    }
    throw new Error(`url tak terduga: ${url}`)
  })
}

const mounted = []

async function visit(path) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/bayar', name: 'checkout', component: BayarPage },
      { path: '/bayar/:orderId', name: 'order', component: BayarPage, props: (r) => ({ orderId: r.params.orderId }) },
      { path: '/berlangganan', name: 'plans', component: stub },
      { path: '/koleksi', name: 'library', component: stub },
      { path: '/profil', name: 'profile', component: stub },
    ],
  })
  router.push(path)
  await router.isReady()
  const w = mount({ template: '<RouterView />' }, { global: { plugins: [router], stubs: { Icon: true, RouterLink: { props: ['to'], template: '<a><slot /></a>' } } } })
  mounted.push(w)
  await flushPromises()
  return { w, router }
}

const button = (w, text) => w.findAll('button').find((b) => b.text().includes(text))
const failure = (status, detail) => Object.assign(new Error('x'), { response: { status, data: { detail } } })

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-11-01T08:00:00Z'))
  mounted.splice(0).forEach((w) => w.unmount())
  get.mockReset()
  post.mockReset()
  refreshUser.mockReset()
  Object.assign(navigator, { clipboard: { writeText: vi.fn().mockResolvedValue() } })
  serve()
})
afterEach(() => vi.useRealTimers())

describe('pesanan baru: ringkasan dan pilihan bank', () => {
  it('menampilkan ringkasan paket, harga, masa berlaku, dan akun pembeli', async () => {
    const { w } = await visit('/bayar?paket=middle')
    const text = w.text()
    expect(text).toContain('Paket Middle (30 hari)')
    expect(text).toContain('Rp 29.000')
    expect(text).toContain('Rana Dzikro')
    expect(text).toContain('rana@example.com')
    expect(text).toContain('30 hari')
  })

  it('memakai harga paket High dari server', async () => {
    const { w } = await visit('/bayar?paket=high')
    expect(w.text()).toContain('Paket High (30 hari)')
    expect(w.text()).toContain('Rp 59.000')
  })

  it('analisis tambahan: jumlah, total, dan keterangan tidak hangus', async () => {
    const { w } = await visit('/bayar?jenis=analisis&jumlah=3')
    expect(w.text()).toContain('3 analisis tambahan')
    expect(w.text()).toContain('Rp 15.000')
    expect(w.text()).toContain('Tidak hangus')
  })

  it.each(['/bayar', '/bayar?paket=emas', '/bayar?jenis=analisis&jumlah=7', '/bayar?jenis=analisis', '/bayar?jenis=lain&jumlah=1'])(
    'query tidak sah %s dialihkan ke halaman paket',
    async (path) => {
      const { router } = await visit(path)
      expect(router.currentRoute.value.name).toBe('plans')
    },
  )

  it('menampilkan semua bank dari server dengan bank pertama terpilih', async () => {
    const { w } = await visit('/bayar?paket=middle')
    const radios = w.findAll('input[type="radio"]')
    expect(radios).toHaveLength(4)
    expect(radios[0].element.checked).toBe(true)
    for (const name of ['BCA', 'BNI', 'BRI', 'Permata']) expect(w.text()).toContain(name)
  })

  it('membuat pesanan upgrade lalu pindah ke alamat tetap pesanan', async () => {
    post.mockResolvedValue({ data: TX() })
    const { w, router } = await visit('/bayar?paket=middle')
    await button(w, 'Buat Virtual Account').trigger('click')
    await flushPromises()
    expect(post).toHaveBeenCalledWith('/billing/checkout', { kind: 'upgrade', bank: 'bca', plan: 'middle' })
    expect(router.currentRoute.value.name).toBe('order')
    expect(router.currentRoute.value.params.orderId).toBe('NAR-1-abcdef')
    expect(w.text()).toContain('3935 8123 4567 8901')
  })

  it('mengirim bank yang dipilih dan jumlah untuk analisis tambahan', async () => {
    post.mockResolvedValue({ data: TX({ kind: 'pay_per_check', plan: null, quantity: 3, amount: 15000, bank: 'bni' }) })
    const { w } = await visit('/bayar?jenis=analisis&jumlah=3')
    await w.findAll('input[type="radio"]')[1].setValue(true)
    await button(w, 'Buat Virtual Account').trigger('click')
    await flushPromises()
    expect(post).toHaveBeenCalledWith('/billing/checkout', { kind: 'pay_per_check', bank: 'bni', quantity: 3 })
  })

  it('menampilkan galat dari server dan tetap di halaman ini', async () => {
    post.mockRejectedValue(failure(400, 'Kamu sudah memakai paket yang lebih tinggi.'))
    const { w, router } = await visit('/bayar?paket=middle')
    await button(w, 'Buat Virtual Account').trigger('click')
    await flushPromises()
    expect(w.find('[role="alert"]').text()).toContain('Kamu sudah memakai paket yang lebih tinggi.')
    expect(router.currentRoute.value.name).toBe('checkout')
  })

  it('tombol dikunci selama permintaan berjalan sehingga tidak membuat dua pesanan', async () => {
    let resolve
    post.mockReturnValue(new Promise((r) => (resolve = r)))
    const { w } = await visit('/bayar?paket=middle')
    const create = button(w, 'Buat Virtual Account')
    await create.trigger('click')
    expect(create.attributes('disabled')).toBeDefined()
    await create.trigger('click')
    expect(post).toHaveBeenCalledTimes(1)
    resolve({ data: TX() })
    await flushPromises()
  })

  it('mode simulasi diberi catatan bahwa tidak ada uang sungguhan', async () => {
    const { w } = await visit('/bayar?paket=middle')
    expect(w.text()).toContain('Mode simulasi')
  })

  it('pembayaran tidak tersedia mengunci tombol dan memberi pesan', async () => {
    serve({ over: OVERVIEW({ provider: 'unavailable' }) })
    const { w } = await visit('/bayar?paket=middle')
    expect(w.text()).toContain('Pembayaran belum tersedia')
    expect(button(w, 'Buat Virtual Account').attributes('disabled')).toBeDefined()
  })

  it('gagal memuat data harga menampilkan pesan', async () => {
    get.mockRejectedValue(failure(500, 'Server error.'))
    const { w } = await visit('/bayar?paket=middle')
    expect(w.find('[role="alert"]').text()).toContain('Server error.')
  })
})

describe('pesanan menunggu pembayaran', () => {
  it('menampilkan nomor pesanan, status, VA, nominal, dan bank', async () => {
    const { w } = await visit('/bayar/NAR-1-abcdef')
    const text = w.text()
    expect(text).toContain('NAR-1-abcdef')
    expect(text).toContain('Menunggu pembayaran')
    expect(text).toContain('3935 8123 4567 8901')
    expect(text).toContain('Rp 29.000')
    expect(text).toContain('BCA')
    expect(text).toContain('Paket Middle (30 hari)')
  })

  it('menampilkan hitung mundur sampai batas waktu dan memperbaruinya tiap detik', async () => {
    const { w } = await visit('/bayar/NAR-1-abcdef')
    expect(w.find('[data-test="countdown"]').text()).toBe('01:02:03')
    await vi.advanceTimersByTimeAsync(1000)
    expect(w.find('[data-test="countdown"]').text()).toBe('01:02:02')
  })

  it('memuat panduan cara membayar untuk bank pesanan', async () => {
    const { w } = await visit('/bayar/NAR-1-abcdef')
    const how = w.find('[data-test="howto"]').text()
    expect(how).toContain('BCA')
    expect(how).toContain('Virtual Account')
  })

  it('menyalin nomor VA tanpa spasi dan nominal tanpa titik', async () => {
    const { w } = await visit('/bayar/NAR-1-abcdef')
    await w.find('[data-test="copy-va"]').trigger('click')
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('3935812345678901')
    await w.find('[data-test="copy-amount"]').trigger('click')
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('29000')
  })

  it('memeriksa status tiap 3 detik dan menampilkan hasil berhasil lalu berhenti', async () => {
    const { w } = await visit('/bayar/NAR-1-abcdef')
    const before = get.mock.calls.length
    txState = TX({ status: 'paid' })
    await vi.advanceTimersByTimeAsync(3000)
    expect(get.mock.calls.length).toBe(before + 1)
    expect(w.text()).toContain('Pembayaran berhasil')
    expect(refreshUser).toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(9000)
    expect(get.mock.calls.length).toBe(before + 1)
  })

  it('hitung mundur yang habis memicu pemeriksaan status segera', async () => {
    txState = TX({ expires_at: '2026-11-01T08:00:02' })
    const { w } = await visit('/bayar/NAR-1-abcdef')
    const before = get.mock.calls.length
    txState = TX({ status: 'expired', expires_at: '2026-11-01T08:00:02' })
    await vi.advanceTimersByTimeAsync(2000)
    expect(get.mock.calls.length).toBeGreaterThan(before)
    expect(w.text()).toContain('Virtual Account kedaluwarsa')
  })

  it('pembatalan meminta konfirmasi lebih dulu', async () => {
    const { w } = await visit('/bayar/NAR-1-abcdef')
    await button(w, 'Batalkan pembayaran').trigger('click')
    expect(post).not.toHaveBeenCalled()
    expect(w.find('[data-test="confirm-cancel"]').exists()).toBe(true)
    await button(w, 'Kembali').trigger('click')
    expect(w.find('[data-test="confirm-cancel"]').exists()).toBe(false)
  })

  it('konfirmasi pembatalan memanggil server dan menampilkan hasil dibatalkan', async () => {
    post.mockResolvedValue({ data: TX({ status: 'cancelled' }) })
    const { w } = await visit('/bayar/NAR-1-abcdef')
    await button(w, 'Batalkan pembayaran').trigger('click')
    await button(w, 'Ya, batalkan').trigger('click')
    await flushPromises()
    expect(post).toHaveBeenCalledWith('/billing/transactions/NAR-1-abcdef/cancel')
    expect(w.text()).toContain('Pembayaran dibatalkan')
  })

  it('simulasi pembayaran hanya untuk pesanan simulasi', async () => {
    post.mockResolvedValue({ data: TX({ status: 'paid' }) })
    const { w } = await visit('/bayar/NAR-1-abcdef')
    await button(w, 'Simulasikan pembayaran berhasil').trigger('click')
    await flushPromises()
    expect(post).toHaveBeenCalledWith('/billing/transactions/NAR-1-abcdef/simulate-pay')
    expect(w.text()).toContain('Pembayaran berhasil')
  })

  it('pesanan Midtrans tidak punya tombol simulasi', async () => {
    serve({ over: OVERVIEW({ provider: 'midtrans' }), tx: TX({ provider: 'midtrans' }) })
    const { w } = await visit('/bayar/NAR-1-abcdef')
    expect(button(w, 'Simulasikan')).toBeUndefined()
  })

  it('galat saat membatalkan ditampilkan', async () => {
    post.mockRejectedValue(failure(409, 'Hanya pembayaran yang masih menunggu yang bisa dibatalkan.'))
    const { w } = await visit('/bayar/NAR-1-abcdef')
    await button(w, 'Batalkan pembayaran').trigger('click')
    await button(w, 'Ya, batalkan').trigger('click')
    await flushPromises()
    expect(w.find('[role="alert"]').text()).toContain('Hanya pembayaran yang masih menunggu')
  })
})

describe('hasil pesanan', () => {
  it('pesanan yang sudah dibayar menampilkan keberhasilan tanpa memeriksa terus-menerus', async () => {
    serve({ tx: TX({ status: 'paid' }) })
    const { w } = await visit('/bayar/NAR-1-abcdef')
    expect(w.text()).toContain('Pembayaran berhasil')
    expect(w.text()).toContain('Invoice dikirim')
    const before = get.mock.calls.length
    await vi.advanceTimersByTimeAsync(9000)
    expect(get.mock.calls.length).toBe(before)
  })

  it.each([
    ['expired', 'Virtual Account kedaluwarsa'],
    ['cancelled', 'Pembayaran dibatalkan'],
    ['failed', 'Pembayaran gagal'],
  ])('status %s menampilkan %s dan menawarkan pembayaran baru', async (status, label) => {
    serve({ tx: TX({ status }) })
    const { w } = await visit('/bayar/NAR-1-abcdef')
    expect(w.text()).toContain(label)
    expect(w.text()).toContain('Belum ada uang yang terpotong')
    expect(w.text()).toContain('Buat pembayaran baru')
  })

  it('pesanan tidak dikenal tampil sebagai tidak ditemukan', async () => {
    serve({ tx: failure(404, 'Transaksi tidak ditemukan.') })
    const { w } = await visit('/bayar/NAR-9-zzzz')
    expect(w.text()).toContain('Pembayaran tidak ditemukan')
  })

  it('galat lain saat memuat pesanan ditampilkan sebagai peringatan', async () => {
    serve({ tx: failure(500, 'Server error.') })
    const { w } = await visit('/bayar/NAR-1-abcdef')
    expect(w.find('[role="alert"]').text()).toContain('Server error.')
  })
})
