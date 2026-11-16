import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import SeriesDialog from '@/components/SeriesDialog.vue'

const DOCS = [
  { id: 1, title: 'Bumi' },
  { id: 2, title: 'Bulan' },
  { id: 3, title: 'Matahari' },
  { id: 4, title: 'Bintang' },
]

function open(props = {}) {
  return mount(SeriesDialog, { props: { docs: DOCS, ...props }, global: { stubs: { Icon: true } } })
}

const button = (w, text) => w.findAll('button').find((b) => b.text().includes(text))
const byLabel = (w, label) => w.find(`[aria-label="${label}"]`)
const order = (w) => w.findAll('ol li span.truncate').map((s) => s.text())
const name = (w) => w.find('input[type="text"]')

describe('membuat seri baru', () => {
  it('berjudul Buat seri buku dan tanpa tombol bubarkan', () => {
    const w = open()
    expect(w.text()).toContain('Buat seri buku')
    expect(button(w, 'Bubarkan seri')).toBeUndefined()
  })

  it('menjelaskan bahwa tiap buku tetap dianalisis sendiri', () => {
    expect(open().text()).toContain('Tiap buku tetap dianalisis sendiri.')
  })

  it('mulai tanpa buku dan menawarkan semua buku untuk ditambahkan', () => {
    const w = open()
    expect(w.text()).toContain('Belum ada buku dipilih')
    expect(w.text()).toContain('0 buku, minimal 2')
    for (const d of DOCS) expect(byLabel(w, `Tambahkan ${d.title}`).exists()).toBe(true)
  })

  it('tombol simpan mati sampai ada nama dan dua buku', async () => {
    const w = open()
    expect(button(w, 'Simpan seri').attributes('disabled')).toBeDefined()
    await name(w).setValue('Trilogi Bumi')
    expect(button(w, 'Simpan seri').attributes('disabled')).toBeDefined()
    await byLabel(w, 'Tambahkan Bumi').trigger('click')
    expect(button(w, 'Simpan seri').attributes('disabled')).toBeDefined()
    await byLabel(w, 'Tambahkan Bulan').trigger('click')
    expect(button(w, 'Simpan seri').attributes('disabled')).toBeUndefined()
  })

  it('nama yang hanya spasi tidak cukup', async () => {
    const w = open({ preselected: [1, 2] })
    await name(w).setValue('    ')
    expect(button(w, 'Simpan seri').attributes('disabled')).toBeDefined()
  })

  it('buku yang sudah dipilih hilang dari daftar tambahan', async () => {
    const w = open()
    await byLabel(w, 'Tambahkan Bumi').trigger('click')
    expect(byLabel(w, 'Tambahkan Bumi').exists()).toBe(false)
    expect(order(w)).toEqual(['Bumi'])
  })

  it('mengirim nama yang dirapikan dan urutan id', async () => {
    const w = open()
    await name(w).setValue('  Trilogi Bumi  ')
    await byLabel(w, 'Tambahkan Bulan').trigger('click')
    await byLabel(w, 'Tambahkan Bumi').trigger('click')
    await button(w, 'Simpan seri').trigger('click')
    expect(w.emitted('save')).toEqual([[{ name: 'Trilogi Bumi', ids: [2, 1] }]])
  })

  it('tekan Enter di kolom nama juga menyimpan bila sudah sah', async () => {
    const w = open({ preselected: [1, 2] })
    await name(w).setValue('Seri Uji')
    await name(w).trigger('keydown.enter')
    expect(w.emitted('save')).toHaveLength(1)
  })

  it('Enter tidak menyimpan bila belum sah', async () => {
    const w = open({ preselected: [1] })
    await name(w).setValue('Seri Uji')
    await name(w).trigger('keydown.enter')
    expect(w.emitted('save')).toBeUndefined()
  })

  it('memakai pilihan awal sebagai urutan pertama', () => {
    expect(order(open({ preselected: [3, 1] }))).toEqual(['Matahari', 'Bumi'])
  })
})

describe('mengatur urutan', () => {
  const ready = () => open({ preselected: [1, 2, 3] })

  it('menaikkan dan menurunkan buku', async () => {
    const w = ready()
    await byLabel(w, 'Naikkan Bulan').trigger('click')
    expect(order(w)).toEqual(['Bulan', 'Bumi', 'Matahari'])
    await byLabel(w, 'Turunkan Bulan').trigger('click')
    expect(order(w)).toEqual(['Bumi', 'Bulan', 'Matahari'])
  })

  it('buku pertama tidak bisa dinaikkan dan yang terakhir tidak bisa diturunkan', () => {
    const w = ready()
    expect(byLabel(w, 'Naikkan Bumi').attributes('disabled')).toBeDefined()
    expect(byLabel(w, 'Turunkan Matahari').attributes('disabled')).toBeDefined()
    expect(byLabel(w, 'Naikkan Bulan').attributes('disabled')).toBeUndefined()
  })

  it('nomor urut mengikuti posisi', () => {
    expect(ready().findAll('ol li span.rounded-full').map((s) => s.text())).toEqual(['1', '2', '3'])
  })

  it('mengeluarkan buku mengembalikannya ke daftar tambahan', async () => {
    const w = ready()
    await byLabel(w, 'Keluarkan Bulan dari seri').trigger('click')
    expect(order(w)).toEqual(['Bumi', 'Matahari'])
    expect(byLabel(w, 'Tambahkan Bulan').exists()).toBe(true)
  })

  it('urutan baru ikut terkirim', async () => {
    const w = ready()
    await name(w).setValue('Seri')
    await byLabel(w, 'Turunkan Bumi').trigger('click')
    await button(w, 'Simpan seri').trigger('click')
    expect(w.emitted('save')[0][0].ids).toEqual([2, 1, 3])
  })

  it('daftar tambahan hilang bila semua buku sudah dipilih', () => {
    const w = open({ preselected: [1, 2, 3, 4] })
    expect(w.text()).not.toContain('Tambahkan buku')
  })
})

describe('mengubah seri yang ada', () => {
  const series = { id: 9, name: 'Trilogi Bumi', document_ids: [2, 1] }

  it('mengisi nama dan urutan dari seri', () => {
    const w = open({ series })
    expect(w.text()).toContain('Ubah seri')
    expect(name(w).element.value).toBe('Trilogi Bumi')
    expect(order(w)).toEqual(['Bulan', 'Bumi'])
  })

  it('seri menang atas pilihan awal', () => {
    expect(order(open({ series, preselected: [3, 4] }))).toEqual(['Bulan', 'Bumi'])
  })

  it('menawarkan membubarkan seri', async () => {
    const w = open({ series })
    await button(w, 'Bubarkan seri').trigger('click')
    expect(w.emitted('dissolve')).toHaveLength(1)
  })

  it('buku dari seri lain diberi catatan akan dipindah', () => {
    const w = open({ series, collections: [series, { id: 10, name: 'Seri Lain', document_ids: [3] }] })
    expect(w.text()).toContain('Akan dipindah dari seri "Seri Lain"')
    expect(w.text()).not.toContain('Akan dipindah dari seri "Trilogi Bumi"')
  })

  it('buku yang dikeluarkan dari seri ini sendiri tidak diberi catatan pindah', async () => {
    const w = open({ series, collections: [series] })
    await byLabel(w, 'Keluarkan Bulan dari seri').trigger('click')
    expect(byLabel(w, 'Tambahkan Bulan').exists()).toBe(true)
    expect(w.text()).not.toContain('Akan dipindah')
  })

  it('buku lepas tidak diberi catatan', () => {
    expect(open({ series, collections: [series] }).text()).not.toContain('Akan dipindah')
  })
})

describe('menyimpan dan menutup', () => {
  it('Batal menutup dialog', async () => {
    const w = open()
    await button(w, 'Batal').trigger('click')
    expect(w.emitted('close')).toHaveLength(1)
  })

  it('klik di luar kartu menutup dialog', async () => {
    const w = open()
    await w.find('.fixed').trigger('click')
    expect(w.emitted('close')).toHaveLength(1)
  })

  it('saat menyimpan, tombol terkunci dan tidak bisa ditutup', async () => {
    const w = open({ preselected: [1, 2], saving: true })
    await name(w).setValue('Seri')
    expect(button(w, 'Menyimpan…')).toBeTruthy()
    expect(button(w, 'Menyimpan…').attributes('disabled')).toBeDefined()
    expect(button(w, 'Batal').attributes('disabled')).toBeDefined()
    await w.find('.fixed').trigger('click')
    expect(w.emitted('close')).toBeUndefined()
  })

  it('menampilkan galat dari server', () => {
    const w = open({ error: 'Nama seri sudah dipakai.' })
    expect(w.find('[role="alert"]').text()).toBe('Nama seri sudah dipakai.')
  })

  it('tanpa galat tidak ada peringatan', () => {
    expect(open().find('[role="alert"]').exists()).toBe(false)
  })

  it('kolom nama dibatasi 150 karakter', () => {
    expect(name(open()).attributes('maxlength')).toBe('150')
  })
})
