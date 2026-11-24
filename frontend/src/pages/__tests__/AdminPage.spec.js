import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const get = vi.fn()
const post = vi.fn()

vi.mock('@/lib/api', () => ({
  default: { get: (...args) => get(...args), post: (...args) => post(...args) },
  errorMessage: (e, fallback) => e?.response?.data?.detail ?? fallback,
}))

import AdminPage from '@/pages/AdminPage.vue'

function days(key, last) {
  return Array.from({ length: 30 }, (_, i) => ({ date: `2026-10-${String(i + 1).padStart(2, '0')}`, [key]: i === 29 ? last : 0 }))
}

const DATA = {
  users: { total: 42, inactive: 2, per_tier: { free: 30, middle: 8, high: 2 }, signups: days('count', 5) },
  revenue: {
    paid_total: 1_250_000,
    paid_this_month: 350_000,
    by_status: { pending: 1, paid: 9, failed: 2, expired: 3, cancelled: 0 },
    by_plan: { middle: { count: 6, amount: 174_000 }, high: { count: 3, amount: 177_000 }, pay_per_check: { count: 0, amount: 0 } },
    per_day: days('amount', 59_000),
  },
  documents: {
    total: 77,
    by_status: { uploaded: 0, queued: 1, analyzing: 2, done: 70, failed: 4 },
    uploads: days('count', 3),
    failure_reasons: [{ reason: 'PDF terenkripsi', count: 3 }, { reason: 'Teks tidak terbaca', count: 1 }],
    summary: { done: 20, partial: 2, failed: 1 },
    characters: { done: 15, partial: 1, failed: 0 },
  },
  quota: { at_limit: 7 },
  generated_at: '2026-11-16T03:00:00',
}

async function open() {
  const w = mount(AdminPage, { global: { stubs: { Icon: true } } })
  await flushPromises()
  return w
}

beforeEach(() => {
  get.mockReset()
  post.mockReset()
  get.mockResolvedValue({ data: DATA })
})

function monthDays(n, key, last) {
  return Array.from({ length: n }, (_, i) => ({ date: `2026-10-${String(i + 1).padStart(2, '0')}`, [key]: i === n - 1 ? last : 0 }))
}
function yearMonths(key, last) {
  return Array.from({ length: 12 }, (_, i) => ({ date: `2026-${String(i + 1).padStart(2, '0')}-01`, [key]: i === 11 ? last : 0 }))
}
const PERIOD = (o = {}) => ({ mode: 'last30', year: null, month: null, label: '30 hari terakhir', granularity: 'day', tables_label: 'Seluruh waktu', available_years: [2025, 2026], ...o })
const WITH_PERIOD = { ...DATA, period: PERIOD() }
const MONTH_DATA = {
  ...DATA,
  users: { ...DATA.users, registered: 4, signups: monthDays(31, 'count', 4) },
  revenue: { ...DATA.revenue, paid_in_period: 122_000, per_day: monthDays(31, 'amount', 59_000) },
  documents: { ...DATA.documents, total: 3, uploads: monthDays(31, 'count', 3) },
  period: PERIOD({ mode: 'month', year: 2026, month: 10, label: 'Oktober 2026', tables_label: 'Oktober 2026' }),
}
const YEAR_DATA = {
  ...DATA,
  users: { ...DATA.users, registered: 9, signups: yearMonths('count', 2) },
  revenue: { ...DATA.revenue, paid_in_period: 500_000, per_day: yearMonths('amount', 59_000) },
  documents: { ...DATA.documents, total: 20, uploads: yearMonths('count', 3) },
  quota: { at_limit: null },
  period: PERIOD({ mode: 'year', year: 2026, label: 'Tahun 2026', granularity: 'month', tables_label: 'Tahun 2026' }),
}

function serveByPeriod() {
  get.mockImplementation(async (url, config) => {
    const params = config?.params ?? {}
    if (params.month) return { data: MONTH_DATA }
    if (params.year) return { data: YEAR_DATA }
    return { data: WITH_PERIOD }
  })
}
const select = (w, id) => w.find(`#${id}`)

describe('filter bulan dan tahun', () => {
  beforeEach(serveByPeriod)

  it('tanpa pilihan memanggil endpoint tanpa parameter', async () => {
    await open()
    expect(get).toHaveBeenCalledTimes(1)
    expect(get).toHaveBeenCalledWith('/admin/overview')
  })

  it('menawarkan 30 hari terakhir dan tahun-tahun yang tersedia', async () => {
    const w = await open()
    const options = select(w, 'periode-tahun').findAll('option').map((o) => o.text())
    expect(options).toEqual(['30 hari terakhir', '2025', '2026'])
    expect(select(w, 'periode-tahun').element.value).toBe('')
  })

  it('pilihan bulan nonaktif sampai tahun dipilih dan memuat dua belas bulan', async () => {
    const w = await open()
    expect(select(w, 'periode-bulan').attributes('disabled')).toBeDefined()
    await select(w, 'periode-tahun').setValue('2026')
    await flushPromises()
    expect(select(w, 'periode-bulan').attributes('disabled')).toBeUndefined()
    const months = select(w, 'periode-bulan').findAll('option').map((o) => o.text())
    expect(months[0]).toBe('Semua bulan')
    expect(months).toHaveLength(13)
    expect(months[11]).toBe('November')
  })

  it('memilih tahun mengirim year saja', async () => {
    const w = await open()
    await select(w, 'periode-tahun').setValue('2026')
    await flushPromises()
    expect(get).toHaveBeenLastCalledWith('/admin/overview', { params: { year: 2026 } })
  })

  it('memilih bulan mengirim year dan month', async () => {
    const w = await open()
    await select(w, 'periode-tahun').setValue('2026')
    await flushPromises()
    await select(w, 'periode-bulan').setValue('10')
    await flushPromises()
    expect(get).toHaveBeenLastCalledWith('/admin/overview', { params: { year: 2026, month: 10 } })
  })

  it('kembali ke 30 hari terakhir menghapus bulan dan tidak mengirim parameter', async () => {
    const w = await open()
    await select(w, 'periode-tahun').setValue('2026')
    await flushPromises()
    await select(w, 'periode-bulan').setValue('10')
    await flushPromises()
    await select(w, 'periode-tahun').setValue('')
    await flushPromises()
    expect(get).toHaveBeenLastCalledWith('/admin/overview')
    expect(select(w, 'periode-bulan').element.value).toBe('')
    expect(select(w, 'periode-bulan').attributes('disabled')).toBeDefined()
  })

  it('mengganti tahun mengosongkan bulan yang terpilih', async () => {
    const w = await open()
    await select(w, 'periode-tahun').setValue('2026')
    await flushPromises()
    await select(w, 'periode-bulan').setValue('10')
    await flushPromises()
    await select(w, 'periode-tahun').setValue('2025')
    await flushPromises()
    expect(get).toHaveBeenLastCalledWith('/admin/overview', { params: { year: 2025 } })
  })

  it('mode bulan: label periode, tiga puluh satu batang, dan angka periode pada kartu', async () => {
    const w = await open()
    await select(w, 'periode-tahun').setValue('2026')
    await flushPromises()
    await select(w, 'periode-bulan').setValue('10')
    await flushPromises()
    const charts = w.findAll('[role="img"]')
    expect(charts[0].findAll('[data-test="bar"]')).toHaveLength(31)
    expect(charts[0].attributes('aria-label')).toContain('Oktober 2026')
    expect(w.text()).toContain('Pendapatan Oktober 2026')
    expect(w.text()).toContain('Rp 122.000')
    expect(w.text()).toContain('4 pendaftar')
  })

  it('mode tahun: dua belas batang berlabel bulan dan kartu kuota tanpa angka', async () => {
    const w = await open()
    await select(w, 'periode-tahun').setValue('2026')
    await flushPromises()
    const charts = w.findAll('[role="img"]')
    expect(charts[0].findAll('[data-test="bar"]')).toHaveLength(12)
    expect(charts[0].attributes('aria-label')).toContain('Tahun 2026')
    expect(w.text()).toContain('Pilih satu bulan')
    const quota = w.findAll('article').find((a) => a.text().includes('Mentok kuota'))
    expect(quota.text()).toContain('-')
    expect(w.text()).toContain('Jan 2026')
  })

  it('tabel menyebut periodenya', async () => {
    const w = await open()
    expect(w.text()).toContain('Periode: Seluruh waktu')
    await select(w, 'periode-tahun').setValue('2026')
    await flushPromises()
    await select(w, 'periode-bulan').setValue('10')
    await flushPromises()
    expect(w.text()).toContain('Periode: Oktober 2026')
  })

  it('gagal memuat periode menampilkan pesan dan tetap memperlihatkan data sebelumnya', async () => {
    const w = await open()
    get.mockRejectedValue(new Error('mati'))
    await select(w, 'periode-tahun').setValue('2026')
    await flushPromises()
    expect(w.find('[role="alert"]').text()).toContain('Gagal memuat periode')
    expect(w.text()).toContain('Total akun pengguna')
  })

  it('respons lama tanpa objek period tetap tampil sebagai 30 hari terakhir', async () => {
    get.mockResolvedValue({ data: DATA })
    const w = await open()
    expect(w.text()).toContain('Rp 350.000')
    expect(w.findAll('[role="img"]')[0].attributes('aria-label')).toContain('30 hari terakhir')
    expect(select(w, 'periode-tahun').findAll('option').map((o) => o.text())).toEqual(['30 hari terakhir'])
  })

  it('tidak menampilkan data pribadi pada mode apa pun', async () => {
    const w = await open()
    await select(w, 'periode-tahun').setValue('2026')
    await flushPromises()
    expect(w.html()).not.toMatch(/@|email|\.pdf/i)
  })
})

const CHECK = (o = {}) => ({
  order_id: 'NAR-1-abc', provider: 'midtrans', kind: 'upgrade', plan: 'middle', quantity: 1,
  local_status: 'expired', local_amount: 29_000, local_method: null,
  created_at: '2026-11-20T03:00:00', expires_at: '2026-11-21T03:00:00', paid_at: null,
  gateway: { checked: true, status: 'paid', raw_status: 'settlement', amount: 29_000, method: 'GoPay' },
  can_sync: true, applied: false, message: 'Midtrans mencatat pembayaran ini lunas, tetapi di NARAtive belum berhasil. Tekan Sinkronkan untuk mencatatnya.',
  ...o,
})

function serveChecks(inspect = CHECK(), synced = CHECK({ local_status: 'paid', can_sync: false, applied: true, message: 'Pembayaran dicatat berhasil; paket atau analisis pengguna sudah diterapkan dan invoice dikirim.' })) {
  get.mockImplementation(async (url) => {
    if (url.startsWith('/admin/payments/')) {
      if (inspect instanceof Error) throw inspect
      return { data: inspect }
    }
    return { data: DATA }
  })
  post.mockImplementation(async () => {
    if (synced instanceof Error) throw synced
    return { data: synced }
  })
}
const failure = (status) => Object.assign(new Error('x'), { response: { status } })

async function lookUp(w, id = 'NAR-1-abc') {
  await w.find('#cek-pesanan').setValue(id)
  await w.find('form').trigger('submit')
  await flushPromises()
}

describe('periksa pembayaran', () => {
  it('menampilkan kolom nomor pesanan dengan tombol yang terkunci sampai diisi', async () => {
    serveChecks()
    const w = await open()
    expect(w.text()).toContain('Periksa pembayaran')
    expect(w.find('form button').attributes('disabled')).toBeDefined()
    await w.find('#cek-pesanan').setValue('NAR-1-abc')
    expect(w.find('form button').attributes('disabled')).toBeUndefined()
  })

  it('memeriksa nomor pesanan tanpa spasi di tepi dan menampilkan dua sisi', async () => {
    serveChecks()
    const w = await open()
    await lookUp(w, '  NAR-1-abc  ')
    expect(get).toHaveBeenCalledWith('/admin/payments/NAR-1-abc')
    const local = w.find('[data-test="check-local"]').text()
    expect(local).toContain('Kedaluwarsa')
    expect(local).toContain('Rp 29.000')
    const gateway = w.find('[data-test="check-gateway"]').text()
    expect(gateway).toContain('Dibayar (settlement)')
    expect(gateway).toContain('Rp 29.000')
    expect(gateway).toContain('GoPay')
  })

  it('menampilkan pesan dan tombol Sinkronkan hanya bila bisa disinkronkan', async () => {
    serveChecks()
    const w = await open()
    await lookUp(w)
    expect(w.find('[data-test="check-message"]').text()).toContain('Tekan Sinkronkan')
    expect(w.find('[data-test="sync"]').exists()).toBe(true)
  })

  it('tanpa tombol Sinkronkan bila tidak bisa', async () => {
    serveChecks(CHECK({ can_sync: false, message: 'Midtrans belum mencatat pembayaran lunas untuk pesanan ini.' }))
    const w = await open()
    await lookUp(w)
    expect(w.find('[data-test="sync"]').exists()).toBe(false)
    expect(w.find('[data-test="check-message"]').text()).toContain('belum mencatat')
  })

  it('sisi Midtrans yang tidak diperiksa dinyatakan begitu', async () => {
    serveChecks(CHECK({ provider: 'simulated', can_sync: false, gateway: { checked: false, status: null, raw_status: null, amount: null, method: null }, message: 'Pesanan ini berasal dari mode simulasi; tidak ada data di Midtrans.' }))
    const w = await open()
    await lookUp(w)
    expect(w.find('[data-test="check-gateway"]').text()).toContain('Tidak diperiksa')
  })

  it('Sinkronkan memanggil endpoint sinkron lalu menampilkan hasil dan menyembunyikan tombolnya', async () => {
    serveChecks()
    const w = await open()
    await lookUp(w)
    await w.find('[data-test="sync"]').trigger('click')
    await flushPromises()
    expect(post).toHaveBeenCalledWith('/admin/payments/NAR-1-abc/sync')
    expect(w.find('[data-test="check-message"]').text()).toContain('Pembayaran dicatat berhasil')
    expect(w.find('[data-test="check-local"]').text()).toContain('Dibayar')
    expect(w.find('[data-test="sync"]').exists()).toBe(false)
  })

  it('nomor yang tidak ada menampilkan pesan dan tidak menyisakan hasil lama', async () => {
    serveChecks()
    const w = await open()
    await lookUp(w)
    serveChecks(failure(404))
    await lookUp(w, 'NAR-9-zzz')
    expect(w.find('[data-test="check-error"]').text()).toBe('Pesanan tidak ditemukan.')
    expect(w.find('[data-test="check-result"]').exists()).toBe(false)
  })

  it('galat lain menampilkan pesan umum', async () => {
    serveChecks(failure(500))
    const w = await open()
    await lookUp(w)
    expect(w.find('[data-test="check-error"]').text()).toBe('Gagal memeriksa pesanan.')
  })

  it('sinkron yang gagal menampilkan pesan, hasil periksa tetap ada, dan tombol bisa dipakai lagi', async () => {
    serveChecks(CHECK(), failure(500))
    const w = await open()
    await lookUp(w)
    await w.find('[data-test="sync"]').trigger('click')
    await flushPromises()
    expect(w.find('[data-test="check-error"]').text()).toBe('Gagal memeriksa pesanan.')
    expect(w.find('[data-test="check-result"]').exists()).toBe(true)
    expect(w.find('[data-test="sync"]').attributes('disabled')).toBeUndefined()
  })

  it('tidak menampilkan data pribadi', async () => {
    serveChecks()
    const w = await open()
    await lookUp(w)
    expect(w.html()).not.toMatch(/@|email|\.pdf/i)
  })
})

describe('AdminPage', () => {
  it('memuat dari endpoint admin', async () => {
    await open()
    expect(get).toHaveBeenCalledWith('/admin/overview')
  })

  it('menampilkan keadaan memuat', () => {
    get.mockReturnValue(new Promise(() => {}))
    const w = mount(AdminPage, { global: { stubs: { Icon: true } } })
    expect(w.text()).toContain('Memuat')
  })

  it('kartu ringkas memuat angka utama', async () => {
    const text = (await open()).text()
    expect(text).toContain('42')
    expect(text).toContain('Rp 350.000')
    expect(text).toContain('77')
    expect(text).toContain('7')
  })

  it('sebaran paket tampil', async () => {
    const text = (await open()).text()
    expect(text).toContain('Standard')
    expect(text).toContain('30')
    expect(text).toContain('Middle')
    expect(text).toContain('High')
  })

  it('tiga grafik batang 30 hari dengan label aksesibel', async () => {
    const w = await open()
    const charts = w.findAll('[role="img"]')
    expect(charts).toHaveLength(3)
    expect(charts[0].attributes('aria-label')).toContain('Pendaftar')
    expect(charts[0].attributes('aria-label')).toContain('5')
    expect(charts[1].attributes('aria-label')).toContain('Rp 59.000')
    expect(charts[2].attributes('aria-label')).toContain('Unggahan')
    expect(charts[0].findAll('[data-test="bar"]')).toHaveLength(30)
  })

  it('tabel status transaksi dan dokumen', async () => {
    const text = (await open()).text()
    expect(text).toContain('Dibayar')
    expect(text).toContain('Menunggu')
    expect(text).toContain('Selesai')
    expect(text).toContain('Gagal')
    expect(text).toContain('70')
  })

  it('alasan gagal teratas tampil dengan jumlahnya', async () => {
    const text = (await open()).text()
    expect(text).toContain('PDF terenkripsi')
    expect(text).toContain('Teks tidak terbaca')
  })

  it('tanpa alasan gagal menampilkan keterangan kosong', async () => {
    get.mockResolvedValue({ data: { ...DATA, documents: { ...DATA.documents, failure_reasons: [] } } })
    expect((await open()).text()).toContain('Belum ada e-book yang gagal.')
  })

  it('403 menampilkan pesan khusus admin', async () => {
    get.mockRejectedValue({ response: { status: 403, data: { detail: 'Fitur ini khusus admin.' } } })
    expect((await open()).text()).toContain('Halaman ini khusus admin.')
  })

  it('galat lain menampilkan pesan gagal', async () => {
    get.mockRejectedValue(new Error('mati'))
    expect((await open()).text()).toContain('Gagal mengambil data admin.')
  })

  it('tombol muat ulang mengambil data lagi', async () => {
    const w = await open()
    await w.findAll('button').find((b) => b.text().includes('Muat ulang')).trigger('click')
    await flushPromises()
    expect(get).toHaveBeenCalledTimes(2)
  })

  it('tidak menampilkan data pribadi', async () => {
    const w = await open()
    expect(w.html()).not.toMatch(/@|email|\.pdf/i)
  })
})
