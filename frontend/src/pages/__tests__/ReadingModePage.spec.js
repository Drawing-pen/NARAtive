import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const get = vi.fn()
vi.mock('@/lib/api', () => ({
  default: { get: (...args) => get(...args) },
  errorMessage: (e, fallback) => e?.response?.data?.detail ?? fallback,
}))

import ReadingModePage from '@/pages/ReadingModePage.vue'

const STANDARD = { profanity: null, sexual: 0.5, violence: null }

function para(idx, chapter_no, text, scores = {}) {
  return { idx, chapter_no, text, profanity: 0, sexual: 0, violence: 0, emotion: 'happy', ...scores }
}

const CHAPTERS = [
  { number: 1, title: 'Bab Satu' },
  { number: 2, title: 'Bab Dua' },
]

const PARAGRAPHS = [
  para(0, 1, 'Pembuka yang aman.'),
  para(1, 1, 'Adegan intim di sini.', { sexual: 0.9 }),
  para(2, 1, 'Perkelahian di gang.', { violence: 0.95, profanity: 0.8 }),
  para(3, 2, 'Bab dua yang aman.'),
  para(4, 2, 'Adegan intim bab dua.', { sexual: 0.7 }),
]

function serve({ doc = { id: 1, title: 'Buku Uji', status: 'done' }, paragraphs = PARAGRAPHS, sensitivity = { thresholds: STANDARD } } = {}) {
  get.mockImplementation(async (url) => {
    if (url === '/documents/1') return { data: doc }
    if (url === '/documents/1/chapters') return { data: CHAPTERS }
    if (url === '/documents/1/paragraphs') return { data: paragraphs }
    if (url === '/sensitivity') {
      if (sensitivity instanceof Error) throw sensitivity
      return { data: sensitivity }
    }
    throw new Error(`url tak terduga: ${url}`)
  })
}

async function open() {
  const wrapper = mount(ReadingModePage, {
    props: { id: '1' },
    global: { stubs: { Icon: true, RouterLink: { template: '<a><slot /></a>' } } },
  })
  await flushPromises()
  return wrapper
}

const hiddenButtons = (w) => w.findAll('button.para')
const buttonByText = (w, text) => w.findAll('button').find((b) => b.text().includes(text))
const bodyText = (w) => w.find('article').text()

beforeEach(() => {
  get.mockReset()
  localStorage.clear()
  window.scrollTo = vi.fn()
})

describe('Safe Mode standar', () => {
  it('menyamarkan hanya paragraf seksual dan membiarkan sisanya terbaca', async () => {
    serve()
    const w = await open()
    expect(hiddenButtons(w)).toHaveLength(1)
    expect(hiddenButtons(w)[0].attributes('aria-label')).toBe('Paragraf seksual disamarkan. Ketuk untuk menampilkan.')
    expect(hiddenButtons(w)[0].text()).toContain('Adegan seksual disamarkan')
    expect(w.text()).toContain('Pembuka yang aman.')
    expect(w.text()).toContain('Perkelahian di gang.')
  })

  it('menyebut jumlah paragraf yang disamarkan di bab itu', async () => {
    serve()
    const w = await open()
    expect(w.find('header').text()).toContain('1 paragraf disamarkan di bab ini')
  })

  it('menyebut bahwa tidak ada paragraf yang disamarkan', async () => {
    serve({ paragraphs: [para(0, 1, 'Semua aman.'), para(1, 2, 'Aman juga.')] })
    const w = await open()
    expect(hiddenButtons(w)).toHaveLength(0)
    expect(w.find('header').text()).toContain('Safe Mode aktif · tidak ada paragraf disamarkan di bab ini')
  })

  it('menyamarkan paragraf yang skornya tepat sama dengan ambang', async () => {
    serve({ paragraphs: [para(0, 1, 'Tepat di ambang.', { sexual: 0.5 }), para(1, 1, 'Sedikit di bawah.', { sexual: 0.49 })] })
    const w = await open()
    expect(hiddenButtons(w)).toHaveLength(1)
    expect(w.text()).toContain('Sedikit di bawah.')
  })

  it('tidak menyamarkan paragraf yang belum punya skor', async () => {
    serve({ paragraphs: [para(0, 1, 'Belum dinilai.', { sexual: null, violence: null, profanity: null })] })
    const w = await open()
    expect(hiddenButtons(w)).toHaveLength(0)
  })

  it('hanya menghitung paragraf pada bab yang sedang dibaca', async () => {
    serve()
    const w = await open()
    expect(bodyText(w)).not.toContain('Bab dua yang aman.')
    expect(w.find('header').text()).toContain('1 paragraf disamarkan')
  })
})

describe('membuka dan menyamarkan kembali', () => {
  it('mengetuk paragraf membukanya dan menyediakan tombol samarkan lagi', async () => {
    serve()
    const w = await open()
    await hiddenButtons(w)[0].trigger('click')
    expect(hiddenButtons(w)).toHaveLength(0)
    expect(w.text()).toContain('Adegan intim di sini.')
    expect(w.find('[aria-label="Samarkan kembali paragraf ini"]').exists()).toBe(true)
    expect(w.find('header').text()).toContain('tidak ada paragraf disamarkan')
  })

  it('tombol di tiap paragraf menyamarkannya kembali', async () => {
    serve()
    const w = await open()
    await hiddenButtons(w)[0].trigger('click')
    await w.find('[aria-label="Samarkan kembali paragraf ini"]').trigger('click')
    expect(hiddenButtons(w)).toHaveLength(1)
  })

  it('tombol di bilah atas menutup semua paragraf yang sudah dibuka di bab itu', async () => {
    serve({ paragraphs: [para(0, 1, 'Satu.', { sexual: 0.9 }), para(1, 1, 'Dua.', { sexual: 0.9 }), para(2, 2, 'Aman.')] })
    const w = await open()
    await hiddenButtons(w)[0].trigger('click')
    await hiddenButtons(w)[0].trigger('click')
    const closeAll = buttonByText(w, 'Samarkan lagi (2)')
    expect(closeAll).toBeTruthy()
    await closeAll.trigger('click')
    expect(hiddenButtons(w)).toHaveLength(2)
    expect(buttonByText(w, 'Samarkan lagi (')).toBeUndefined()
  })

  it('berganti bab menyamarkan ulang paragraf yang tadi dibuka', async () => {
    serve()
    const w = await open()
    await hiddenButtons(w)[0].trigger('click')
    expect(hiddenButtons(w)).toHaveLength(0)
    await buttonByText(w, 'Bab berikutnya').trigger('click')
    expect(bodyText(w)).toContain('Bab Dua')
    await buttonByText(w, 'Sebelumnya').trigger('click')
    expect(hiddenButtons(w)).toHaveLength(1)
  })
})

describe('tombol Safe Mode', () => {
  it('menonaktifkan penyamaran dan mengaktifkannya lagi', async () => {
    serve()
    const w = await open()
    const toggle = buttonByText(w, 'Safe Mode aktif')
    await toggle.trigger('click')
    expect(hiddenButtons(w)).toHaveLength(0)
    expect(w.find('header').text()).toContain('Safe Mode nonaktif')
    expect(w.text()).toContain('Adegan intim di sini.')
    await buttonByText(w, 'Safe Mode nonaktif').trigger('click')
    expect(hiddenButtons(w)).toHaveLength(1)
  })

  it('mengingat pilihan Safe Mode di penyimpanan browser', async () => {
    serve()
    const w = await open()
    await buttonByText(w, 'Safe Mode aktif').trigger('click')
    expect(JSON.parse(localStorage.getItem('narative_reader')).safeMode).toBe(false)
    w.unmount()
    const again = await open()
    expect(hiddenButtons(again)).toHaveLength(0)
  })

  it('tetap berfungsi bila penyimpanan browser tidak tersedia', async () => {
    serve()
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('diblokir')
    })
    const w = await open()
    await buttonByText(w, 'Safe Mode aktif').trigger('click')
    expect(hiddenButtons(w)).toHaveLength(0)
    vi.restoreAllMocks()
  })
})

describe('profil sensitivitas personal', () => {
  it('memakai ambang pengguna untuk kekerasan dan bahasa kasar', async () => {
    serve({ sensitivity: { thresholds: { profanity: 0.4, sexual: 0.3, violence: 0.7 } } })
    const w = await open()
    expect(hiddenButtons(w)).toHaveLength(2)
    const violent = hiddenButtons(w).find((b) => b.text().includes('Konten sensitif disamarkan'))
    expect(violent.attributes('aria-label')).toBe('Paragraf sensitif disamarkan. Ketuk untuk menampilkan.')
  })

  it('tidak menyamarkan jenis konten yang ambangnya null', async () => {
    serve({ sensitivity: { thresholds: { profanity: null, sexual: null, violence: null } } })
    const w = await open()
    expect(hiddenButtons(w)).toHaveLength(0)
  })

  it('kembali ke profil standar bila profil gagal dimuat', async () => {
    serve({ sensitivity: new Error('jaringan putus') })
    const w = await open()
    expect(hiddenButtons(w)).toHaveLength(1)
    expect(hiddenButtons(w)[0].text()).toContain('Adegan seksual disamarkan')
  })
})

describe('keadaan halaman', () => {
  it('menampilkan pesan bila analisis belum selesai', async () => {
    serve({ doc: { id: 1, title: 'Buku Uji', status: 'analyzing' } })
    const w = await open()
    expect(w.text()).toContain('E-book ini belum selesai dianalisis')
    expect(hiddenButtons(w)).toHaveLength(0)
  })

  it('menampilkan pesan dokumen tidak ditemukan dengan tombol coba lagi', async () => {
    get.mockImplementation(async () => {
      const err = new Error('404')
      err.response = { status: 404 }
      throw err
    })
    const w = await open()
    expect(w.text()).toContain('Dokumen tidak ditemukan.')
    expect(buttonByText(w, 'Coba lagi')).toBeTruthy()
  })

  it('menampilkan pesan galat umum bila server tidak terjangkau', async () => {
    get.mockImplementation(async () => {
      throw new Error('putus')
    })
    const w = await open()
    expect(w.text()).toContain('Gagal memuat teks e-book.')
  })

  it('menonaktifkan tombol bab sebelumnya di bab pertama dan berikutnya di bab terakhir', async () => {
    serve()
    const w = await open()
    expect(w.findAll('nav button')[0].attributes('disabled')).toBeDefined()
    expect(w.findAll('nav button')[1].attributes('disabled')).toBeUndefined()
    await buttonByText(w, 'Bab berikutnya').trigger('click')
    expect(w.findAll('nav button')[0].attributes('disabled')).toBeUndefined()
    expect(w.findAll('nav button').at(-1).attributes('disabled')).toBeDefined()
  })
})
