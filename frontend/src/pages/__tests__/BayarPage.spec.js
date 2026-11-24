import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'

const get = vi.fn()
const post = vi.fn()
const refreshUser = vi.fn()
const loadSnap = vi.fn()
const embed = vi.fn()

vi.mock('@/lib/snap', () => ({ loadSnap: (...args) => loadSnap(...args) }))
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
  snap_client_key: null,
  snap_script_url: null,
  ...o,
})
const SNAP = (o = {}) => TX({ bank: null, va_number: null, snap_token: 'SIM-abc', payment_method: null, ...o })
const MIDTRANS = (o = {}) => OVERVIEW({ provider: 'midtrans', snap_client_key: 'KUNCI-KLIEN', snap_script_url: 'https://snap.test/snap.js', ...o })
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
  loadSnap.mockReset()
  loadSnap.mockResolvedValue({ embed })
  embed.mockReset()
  Object.assign(navigator, { clipboard: { writeText: vi.fn().mockResolvedValue() } })
  serve()
})
afterEach(() => vi.useRealTimers())

describe('pesanan baru: pembayaran langsung disiapkan', () => {
  beforeEach(() => {
    serve({ tx: SNAP() })
    post.mockResolvedValue({ data: SNAP() })
  })

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
    serve({ tx: SNAP({ plan: 'high', amount: 59000 }) })
    post.mockResolvedValue({ data: SNAP({ plan: 'high', amount: 59000 }) })
    const { w } = await visit('/bayar?paket=high')
    expect(w.text()).toContain('Paket High (30 hari)')
    expect(w.text()).toContain('Rp 59.000')
  })

  it('analisis tambahan: jumlah, total, dan keterangan tidak hangus', async () => {
    const three = SNAP({ kind: 'pay_per_check', plan: null, quantity: 3, amount: 15000 })
    serve({ tx: three })
    post.mockResolvedValue({ data: three })
    const { w } = await visit('/bayar?jenis=analisis&jumlah=3')
    expect(w.text()).toContain('3 analisis tambahan')
    expect(w.text()).toContain('Rp 15.000')
    expect(w.text()).toContain('Tidak hangus')
  })

  it.each(['/bayar', '/bayar?paket=emas', '/bayar?jenis=analisis&jumlah=7', '/bayar?jenis=analisis', '/bayar?jenis=lain&jumlah=1'])(
    'query tidak sah %s dialihkan ke halaman paket tanpa membuat pesanan',
    async (path) => {
      const { router } = await visit(path)
      expect(router.currentRoute.value.name).toBe('plans')
      expect(post).not.toHaveBeenCalled()
    },
  )

  it('langsung membuat pesanan tanpa tombol lanjut dan tanpa pilihan bank', async () => {
    const { w, router } = await visit('/bayar?paket=middle')
    expect(w.text()).not.toContain('Lanjut ke pembayaran')
    expect(w.text()).not.toContain('Pilih bank')
    expect(post).toHaveBeenCalledTimes(1)
    expect(post).toHaveBeenCalledWith('/billing/checkout', { kind: 'upgrade', plan: 'middle' })
    expect(router.currentRoute.value.name).toBe('order')
    expect(router.currentRoute.value.params.orderId).toBe('NAR-1-abcdef')
    expect(w.text()).toContain('Pilih metode pembayaran')
    expect(w.text()).toContain('Simulasi Midtrans')
  })

  it('mengirim jumlah untuk analisis tambahan tanpa bank', async () => {
    post.mockResolvedValue({ data: SNAP({ kind: 'pay_per_check', plan: null, quantity: 3, amount: 15000 }) })
    await visit('/bayar?jenis=analisis&jumlah=3')
    expect(post).toHaveBeenCalledWith('/billing/checkout', { kind: 'pay_per_check', quantity: 3 })
  })

  it('menampilkan keadaan menyiapkan selama permintaan berjalan dan tidak membuat dua pesanan', async () => {
    let resolve
    post.mockReturnValue(new Promise((r) => (resolve = r)))
    const { w } = await visit('/bayar?paket=middle')
    expect(w.text()).toContain('Menyiapkan pembayaran')
    await vi.advanceTimersByTimeAsync(5000)
    expect(post).toHaveBeenCalledTimes(1)
    resolve({ data: SNAP() })
    await flushPromises()
  })

  it('galat dari server ditampilkan, tetap di halaman ini, dan Coba lagi membuat ulang', async () => {
    post.mockRejectedValueOnce(failure(400, 'Kamu sudah memakai paket yang lebih tinggi.'))
    const { w, router } = await visit('/bayar?paket=middle')
    expect(w.find('[role="alert"]').text()).toContain('Kamu sudah memakai paket yang lebih tinggi.')
    expect(router.currentRoute.value.name).toBe('checkout')
    await button(w, 'Coba lagi').trigger('click')
    await flushPromises()
    expect(post).toHaveBeenCalledTimes(2)
    expect(router.currentRoute.value.name).toBe('order')
  })

  it('mode simulasi diberi catatan bahwa tidak ada uang sungguhan', async () => {
    const { w } = await visit('/bayar?paket=middle')
    expect(w.text()).toContain('Mode simulasi')
  })

  it('pembayaran tidak tersedia memberi pesan dan tidak membuat pesanan', async () => {
    serve({ over: OVERVIEW({ provider: 'unavailable' }) })
    const { w } = await visit('/bayar?paket=middle')
    expect(w.text()).toContain('Pembayaran belum tersedia')
    expect(post).not.toHaveBeenCalled()
    expect(w.text()).not.toContain('Menyiapkan pembayaran')
    expect(w.find('[data-test="preparing"]').exists()).toBe(false)
  })

  it('gagal memuat data harga menampilkan pesan dan tidak membuat pesanan', async () => {
    get.mockRejectedValue(failure(500, 'Server error.'))
    const { w } = await visit('/bayar?paket=middle')
    expect(w.find('[role="alert"]').text()).toContain('Server error.')
    expect(post).not.toHaveBeenCalled()
  })
})

describe('tata letak halaman bayar', () => {
  const stepNames = (w) => w.findAll('[data-test="steps"] [data-test="step-label"]').map((l) => l.text())

  beforeEach(() => {
    serve({ tx: SNAP() })
    post.mockResolvedValue({ data: SNAP() })
  })

  it('menampilkan penunjuk tiga langkah dengan langkah bayar sebagai langkah sekarang', async () => {
    const { w } = await visit('/bayar/NAR-1-abcdef')
    expect(stepNames(w)).toEqual(['Pilih paket', 'Bayar', 'Selesai'])
    expect(w.find('[data-test="steps"] [aria-current="step"]').text()).toBe('Bayar')
  })

  it('setelah berhasil langkah selesai menjadi langkah sekarang', async () => {
    serve({ tx: SNAP({ status: 'paid' }) })
    const { w } = await visit('/bayar/NAR-1-abcdef')
    expect(w.find('[data-test="steps"] [aria-current="step"]').text()).toBe('Selesai')
  })

  it('pesanan yang gagal atau kedaluwarsa tetap berada di langkah bayar', async () => {
    serve({ tx: SNAP({ status: 'expired' }) })
    const { w } = await visit('/bayar/NAR-1-abcdef')
    expect(w.find('[data-test="steps"] [aria-current="step"]').text()).toBe('Bayar')
  })

  it('kartu manfaat paket Middle memuat batas dan fitur paketnya', async () => {
    const { w } = await visit('/bayar/NAR-1-abcdef')
    const text = w.find('[data-test="benefits"]').text()
    expect(text).toContain('Yang kamu dapatkan')
    for (const part of ['300 halaman per unggahan', '15 analisis per bulan', 'Rangkuman cerita per bab', 'Relasi antar tokoh']) expect(text).toContain(part)
    expect(text).not.toContain('Profil sensitivitas personal')
  })

  it('kartu manfaat paket High memuat fitur khususnya', async () => {
    serve({ tx: SNAP({ plan: 'high', amount: 59000 }) })
    const { w } = await visit('/bayar/NAR-1-abcdef')
    const text = w.find('[data-test="benefits"]').text()
    expect(text).toContain('Tanpa batas analisis')
    expect(text).toContain('Profil sensitivitas personal')
  })

  it('kartu manfaat analisis tambahan menyebut jumlah dan aturan pemakaiannya', async () => {
    serve({ tx: SNAP({ kind: 'pay_per_check', plan: null, quantity: 3, amount: 15000 }) })
    const { w } = await visit('/bayar/NAR-1-abcdef')
    const text = w.find('[data-test="benefits"]').text()
    expect(text).toContain('3 analisis tambahan')
    expect(text).toContain('Tidak hangus saat bulan berganti')
    expect(text).toContain('Dipakai setelah kuota bulananmu habis')
  })

  it('kartu manfaat sudah tampil sejak pesanan disiapkan', async () => {
    let resolve
    post.mockReturnValue(new Promise((r) => (resolve = r)))
    const { w } = await visit('/bayar?paket=high')
    expect(w.find('[data-test="benefits"]').text()).toContain('Profil sensitivitas personal')
    resolve({ data: SNAP({ plan: 'high', amount: 59000 }) })
    await flushPromises()
  })

  it('kartu pembayaran aman memuat jaminan dan petunjuk bila uang sudah terpotong', async () => {
    const { w } = await visit('/bayar/NAR-1-abcdef')
    const text = w.find('[data-test="trust"]').text()
    expect(text).toContain('Pembayaran aman')
    expect(text).toContain('Midtrans')
    expect(text).toContain('tidak menyimpan data kartu atau rekening')
    expect(text).toContain('Invoice')
    expect(text).toContain('Periksa status')
    expect(text).toContain('nomor pesanan')
  })

  it('tidak menyebut OCR, scan, atau gambar', async () => {
    const { w } = await visit('/bayar/NAR-1-abcdef')
    const text = w.text().toLowerCase()
    for (const word of ['ocr', 'scan', 'gambar']) expect(text).not.toContain(word)
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

describe('pesanan Midtrans: metode pembayaran di dalam halaman', () => {
  const open = async (over = MIDTRANS(), tx = SNAP({ provider: 'midtrans', snap_token: 'tok-1' })) => {
    serve({ over, tx })
    return visit('/bayar/NAR-1-abcdef')
  }

  it('memuat skrip Snap dengan kunci klien lalu menanam metode pembayaran di wadahnya', async () => {
    const { w } = await open()
    expect(loadSnap).toHaveBeenCalledWith('https://snap.test/snap.js', 'KUNCI-KLIEN')
    expect(w.find('#snap-embed').exists()).toBe(true)
    expect(embed).toHaveBeenCalledTimes(1)
    expect(embed.mock.calls[0][0]).toBe('tok-1')
    expect(embed.mock.calls[0][1].embedId).toBe('snap-embed')
  })

  it('menampilkan judul pilihan metode, nominal, batas waktu, dan tombol batal', async () => {
    const { w } = await open()
    expect(w.text()).toContain('Pilih metode pembayaran')
    expect(w.text()).toContain('Rp 29.000')
    expect(w.find('[data-test="countdown"]').text()).toBe('01:02:03')
    expect(button(w, 'Batalkan pembayaran')).toBeDefined()
  })

  it('menampilkan penampung selama metode pembayaran dimuat lalu menghilangkannya', async () => {
    let resolve
    loadSnap.mockReturnValue(new Promise((r) => (resolve = r)))
    const { w } = await open()
    expect(w.find('[data-test="embed-placeholder"]').exists()).toBe(true)
    resolve({ embed })
    await flushPromises()
    expect(w.find('[data-test="embed-placeholder"]').exists()).toBe(false)
  })

  it('penampung hilang saat gagal memuat dan diganti pesan', async () => {
    loadSnap.mockRejectedValueOnce(new Error('gagal'))
    const { w } = await open()
    expect(w.find('[data-test="embed-placeholder"]').exists()).toBe(false)
    expect(w.find('[role="alert"]').text()).toContain('Metode pembayaran gagal dimuat')
  })

  it('tidak menampilkan nomor Virtual Account atau panduan transfer', async () => {
    const { w } = await open()
    expect(w.find('[data-test="howto"]').exists()).toBe(false)
    expect(w.find('[data-test="copy-va"]').exists()).toBe(false)
  })

  it('tidak menanam ulang saat status diperiksa dan masih menunggu', async () => {
    await open()
    await vi.advanceTimersByTimeAsync(7000)
    expect(embed).toHaveBeenCalledTimes(1)
  })

  it('berhasil dari jendela pembayaran langsung memeriksa status tanpa menunggu 3 detik', async () => {
    const { w } = await open()
    txState = SNAP({ provider: 'midtrans', snap_token: 'tok-1', status: 'paid', payment_method: 'QRIS' })
    await embed.mock.calls[0][1].onSuccess({ transaction_status: 'settlement' })
    await flushPromises()
    expect(w.text()).toContain('Pembayaran berhasil')
    expect(refreshUser).toHaveBeenCalled()
  })

  it('menunggu pembayaran (pending) juga memeriksa status', async () => {
    await open()
    const before = get.mock.calls.length
    await embed.mock.calls[0][1].onPending({})
    await flushPromises()
    expect(get.mock.calls.length).toBe(before + 1)
  })

  it('galat dari jendela pembayaran menampilkan pesan', async () => {
    const { w } = await open()
    embed.mock.calls[0][1].onError({})
    await flushPromises()
    expect(w.find('[role="alert"]').text()).toContain('Pembayaran tidak dapat diproses')
  })

  it('gagal memuat metode pembayaran menampilkan pesan dan coba lagi yang memuat ulang', async () => {
    loadSnap.mockRejectedValueOnce(new Error('gagal'))
    const { w } = await open()
    expect(w.find('[role="alert"]').text()).toContain('Metode pembayaran gagal dimuat')
    expect(embed).not.toHaveBeenCalled()
    await button(w, 'Coba lagi').trigger('click')
    await flushPromises()
    expect(loadSnap).toHaveBeenCalledTimes(2)
    expect(embed).toHaveBeenCalledTimes(1)
  })

  it('tanpa kunci klien dari server tidak memuat apa pun dan memberi pesan', async () => {
    const { w } = await open(MIDTRANS({ snap_client_key: null, snap_script_url: null }))
    expect(loadSnap).not.toHaveBeenCalled()
    expect(w.text()).toContain('Pembayaran belum tersedia')
  })

  it('transaksi lama dengan Virtual Account tidak memakai Snap', async () => {
    serve({ over: MIDTRANS(), tx: TX({ provider: 'midtrans' }) })
    const { w } = await visit('/bayar/NAR-1-abcdef')
    expect(loadSnap).not.toHaveBeenCalled()
    expect(w.text()).toContain('3935 8123 4567 8901')
  })

  it('pesanan yang sudah selesai tidak memuat Snap', async () => {
    serve({ over: MIDTRANS(), tx: SNAP({ provider: 'midtrans', status: 'paid' }) })
    await visit('/bayar/NAR-1-abcdef')
    expect(loadSnap).not.toHaveBeenCalled()
  })

  it('tidak menyebut OCR, scan, atau gambar', async () => {
    const { w } = await open()
    const text = w.text().toLowerCase()
    for (const word of ['ocr', 'scan', 'gambar']) expect(text).not.toContain(word)
  })
})

describe('pesanan simulasi: panel di tempat metode pembayaran', () => {
  const open = async () => {
    serve({ tx: SNAP() })
    return visit('/bayar/NAR-1-abcdef')
  }

  it('menampilkan panel simulasi dengan enam metode dan tidak memuat Snap', async () => {
    const { w } = await open()
    expect(w.text()).toContain('Simulasi Midtrans')
    expect(w.findAll('[data-test="sim-method"] input[type="radio"]')).toHaveLength(6)
    for (const label of ['Virtual Account BCA', 'Virtual Account BNI', 'Virtual Account BRI', 'Virtual Account PERMATA', 'QRIS', 'GoPay']) expect(w.text()).toContain(label)
    expect(loadSnap).not.toHaveBeenCalled()
  })

  it('memilih metode pertama secara bawaan dan mengirimnya saat disimulasikan', async () => {
    const { w } = await open()
    post.mockResolvedValue({ data: SNAP({ status: 'paid', payment_method: 'Virtual Account BCA' }) })
    await button(w, 'Simulasikan pembayaran berhasil').trigger('click')
    await flushPromises()
    expect(post).toHaveBeenCalledWith('/billing/transactions/NAR-1-abcdef/simulate-pay', { method: 'bca' })
    expect(w.text()).toContain('Pembayaran berhasil')
  })

  it('mengirim metode yang dipilih', async () => {
    const { w } = await open()
    post.mockResolvedValue({ data: SNAP({ status: 'paid', payment_method: 'QRIS' }) })
    await w.findAll('[data-test="sim-method"] input[type="radio"]')[4].setValue(true)
    await button(w, 'Simulasikan pembayaran berhasil').trigger('click')
    await flushPromises()
    expect(post).toHaveBeenCalledWith('/billing/transactions/NAR-1-abcdef/simulate-pay', { method: 'qris' })
  })

  it('transaksi lama dengan Virtual Account tetap memakai tombol simulasi lama tanpa badan', async () => {
    serve({ tx: TX() })
    const { w } = await visit('/bayar/NAR-1-abcdef')
    post.mockResolvedValue({ data: TX({ status: 'paid' }) })
    await button(w, 'Simulasikan pembayaran berhasil').trigger('click')
    await flushPromises()
    expect(post).toHaveBeenCalledWith('/billing/transactions/NAR-1-abcdef/simulate-pay')
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

  it('pesanan yang sudah dibayar menawarkan melihat invoice', async () => {
    serve({ tx: TX({ status: 'paid' }) })
    const { w } = await visit('/bayar/NAR-1-abcdef')
    expect(w.text()).toContain('Lihat invoice')
  })

  it('pesanan yang belum berhasil tidak menawarkan invoice', async () => {
    serve({ tx: TX({ status: 'expired' }) })
    const { w } = await visit('/bayar/NAR-1-abcdef')
    expect(w.text()).not.toContain('Lihat invoice')
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
