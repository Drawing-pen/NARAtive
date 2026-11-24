import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const get = vi.fn()
const post = vi.fn()
const allowed = { middle: true }

vi.mock('@/lib/api', () => ({
  default: { get: (...args) => get(...args), post: (...args) => post(...args) },
  errorMessage: (e, fallback) => e?.response?.data?.detail ?? fallback,
}))
vi.mock('@/lib/auth', () => ({ hasTier: () => allowed.middle }))

import SummaryPage from '@/pages/SummaryPage.vue'

const DOC = { id: 1, title: 'Buku Uji', status: 'done' }

function summary(status, overrides = {}) {
  return {
    status,
    done_chapters: 3,
    total_chapters: 3,
    overall: 'Ringkasan seluruh buku.',
    chapters: [
      { number: 1, title: 'Bab Satu', summary: 'Dari AI.', summary_source: 'ai' },
      { number: 2, title: 'Bab Dua', summary: 'Versi sederhana.', summary_source: 'local' },
      { number: 3, title: 'Bab Tiga', summary: 'Data lama.', summary_source: null },
    ],
    ...overrides,
  }
}

function serve(sum, doc = DOC) {
  get.mockImplementation(async (url) => {
    if (url === '/documents/1') return { data: doc }
    if (url === '/documents/1/summary') return { data: sum }
    throw new Error(`url tak terduga: ${url}`)
  })
}

async function open() {
  const wrapper = mount(SummaryPage, {
    props: { id: '1' },
    global: { stubs: { Icon: true, RouterLink: { template: '<a><slot /></a>' } } },
  })
  await flushPromises()
  return wrapper
}

const buttonByText = (w, text) => w.findAll('button').find((b) => b.text().includes(text))

beforeEach(() => {
  get.mockReset()
  post.mockReset()
  allowed.middle = true
})

describe('rangkuman untuk dokumen yang bukan novel', () => {
  const OTHER = { id: 1, title: 'Makalah', status: 'not_novel' }

  it('terkunci dengan pesan bukan novel, bukan belum selesai dianalisis', async () => {
    serve(summary(null), OTHER)
    const w = await open()
    expect(w.text()).toContain('Dokumen ini bukan novel')
    expect(w.text()).not.toContain('setelah analisis buku ini selesai')
    expect(buttonByText(w, 'Buat rangkuman')).toBeUndefined()
  })

  it('pesan ini lebih diutamakan daripada kunci tingkatan', async () => {
    allowed.middle = false
    serve(summary(null), OTHER)
    const w = await open()
    expect(w.text()).toContain('Dokumen ini bukan novel')
    expect(w.text()).not.toContain('Fitur khusus Middle Tier')
  })
})

describe('rangkuman yang sedang dibuat', () => {
  it('menampilkan persen dari server dan jumlah bab selesai', async () => {
    serve(summary('running', { progress: 67, done_chapters: 2, total_chapters: 3, overall: null }))
    const w = await open()
    expect(w.text()).toContain('Sedang membuat rangkuman')
    expect(w.text()).toContain('2 dari 3 bab selesai')
    expect(w.find('[data-test="percent"]').text()).toBe('67%')
    expect(w.find('[role="progressbar"]').attributes('aria-valuenow')).toBe('67')
  })

  it('tanpa angka dari server tampil sebagai keadaan tak tentu', async () => {
    serve(summary('running', { progress: null, done_chapters: 0, total_chapters: 0, overall: null }))
    const w = await open()
    expect(w.find('[data-test="fill"]').classes()).toContain('is-indeterminate')
  })
})

describe('rangkuman sebagian (partial)', () => {
  it('menampilkan hasil tanpa catatan apa pun', async () => {
    serve(summary('partial'))
    const w = await open()
    expect(w.text()).toContain('Ringkasan seluruh buku.')
    expect(w.text()).not.toContain('dirangkum sederhana')
    expect(w.find('[role="status"]').exists()).toBe(false)
  })

  it('memberi label hanya pada bab bersumber lokal', async () => {
    serve(summary('partial'))
    const w = await open()
    const articles = w.findAll('article')
    expect(articles).toHaveLength(3)
    expect(articles[0].text()).not.toContain('Ringkasan sederhana (tanpa AI)')
    expect(articles[1].text()).toContain('Ringkasan sederhana (tanpa AI)')
    expect(articles[2].text()).not.toContain('Ringkasan sederhana (tanpa AI)')
  })

  it('tidak menampilkan tombol Lanjutkan dengan AI', async () => {
    serve(summary('partial'))
    const w = await open()
    expect(buttonByText(w, 'Lanjutkan dengan AI')).toBeUndefined()
    expect(buttonByText(w, 'Buat ulang')).toBeTruthy()
  })
})

describe('keadaan lain tidak berubah', () => {
  it('rangkuman selesai tidak menampilkan catatan atau tombol lanjutkan', async () => {
    serve(summary('done', { chapters: [{ number: 1, title: 'Bab Satu', summary: 'Dari AI.', summary_source: 'ai' }] }))
    const w = await open()
    expect(w.text()).not.toContain('dirangkum sederhana')
    expect(buttonByText(w, 'Lanjutkan dengan AI')).toBeUndefined()
    expect(buttonByText(w, 'Buat ulang')).toBeTruthy()
  })

  it('rangkuman gagal masih menawarkan coba lagi', async () => {
    serve(summary('failed', { overall: null }))
    const w = await open()
    expect(w.text()).toContain('Rangkuman gagal dibuat')
    expect(buttonByText(w, 'Coba lagi')).toBeTruthy()
  })
})
