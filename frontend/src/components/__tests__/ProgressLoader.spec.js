import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ProgressLoader from '@/components/ProgressLoader.vue'

function loader(props = {}) {
  return mount(ProgressLoader, {
    props: { percent: 40, title: 'Membaca berkas', ...props },
    global: { stubs: { Icon: true } },
  })
}

beforeEach(() => vi.useFakeTimers())
afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('angka dan bilah', () => {
  it('menampilkan persen besar dan judul tahap', () => {
    const w = loader()
    expect(w.find('[data-test="percent"]').text()).toBe('40%')
    expect(w.text()).toContain('Membaca berkas')
  })

  it('bilah berperan sebagai progressbar 0 sampai 100', () => {
    const bar = loader({ percent: 40 }).find('[role="progressbar"]')
    expect(bar.attributes('aria-valuenow')).toBe('40')
    expect(bar.attributes('aria-valuemin')).toBe('0')
    expect(bar.attributes('aria-valuemax')).toBe('100')
    expect(bar.attributes('aria-label')).toBe('Membaca berkas')
  })

  it('lebar isian mengikuti persen', () => {
    expect(loader({ percent: 65 }).find('[data-test="fill"]').attributes('style')).toContain('width: 65%')
  })

  it('membulatkan angka pecahan', () => {
    expect(loader({ percent: 41.6 }).find('[data-test="percent"]').text()).toBe('42%')
  })

  it('tidak melewati 100 dan tidak di bawah 0', () => {
    expect(loader({ percent: 140 }).find('[data-test="percent"]').text()).toBe('100%')
    expect(loader({ percent: -5 }).find('[data-test="percent"]').text()).toBe('0%')
  })

  it('memuat keterangan bila ada', () => {
    expect(loader({ detail: 'Membaca halaman 12 dari 30' }).text()).toContain('Membaca halaman 12 dari 30')
  })
})

describe('tanpa angka', () => {
  it('menampilkan keadaan tak tentu: tanpa persen dan tanpa nilai', () => {
    const w = loader({ percent: null })
    expect(w.find('[data-test="percent"]').exists()).toBe(false)
    expect(w.find('[role="progressbar"]').attributes('aria-valuenow')).toBeUndefined()
    expect(w.find('[data-test="fill"]').classes()).toContain('is-indeterminate')
  })

  it('angka yang tidak terbaca dianggap tak tentu', () => {
    expect(loader({ percent: Number.NaN }).find('[data-test="fill"]').classes()).toContain('is-indeterminate')
  })

  it('bilah penuh bukan keadaan tak tentu', () => {
    expect(loader({ percent: 100 }).find('[data-test="fill"]').classes()).not.toContain('is-indeterminate')
  })
})

describe('animasi angka', () => {
  it('bergerak halus menuju angka baru, lalu tepat di angka itu', async () => {
    const w = loader({ percent: 40 })
    await w.setProps({ percent: 80 })
    vi.advanceTimersByTime(30)
    await w.vm.$nextTick()
    const mid = Number.parseInt(w.find('[data-test="percent"]').text(), 10)
    expect(mid).toBeGreaterThan(40)
    expect(mid).toBeLessThan(80)
    vi.advanceTimersByTime(1500)
    await w.vm.$nextTick()
    expect(w.find('[data-test="percent"]').text()).toBe('80%')
  })

  it('bilah langsung memakai angka baru agar transisi CSS yang menghaluskan', async () => {
    const w = loader({ percent: 10 })
    await w.setProps({ percent: 90 })
    expect(w.find('[data-test="fill"]').attributes('style')).toContain('width: 90%')
  })

  it('angka turun juga menuju nilai barunya', async () => {
    const w = loader({ percent: 90 })
    await w.setProps({ percent: 20 })
    vi.advanceTimersByTime(2000)
    await w.vm.$nextTick()
    expect(w.find('[data-test="percent"]').text()).toBe('20%')
  })

  it('langsung loncat bila pengguna meminta gerak dikurangi', async () => {
    vi.stubGlobal('matchMedia', () => ({ matches: true }))
    const w = loader({ percent: 10 })
    await w.setProps({ percent: 70 })
    expect(w.find('[data-test="percent"]').text()).toBe('70%')
  })

  it('tidak meninggalkan timer setelah dilepas', async () => {
    const w = loader({ percent: 10 })
    await w.setProps({ percent: 90 })
    w.unmount()
    expect(vi.getTimerCount()).toBe(0)
  })
})

describe('petunjuk bergantian', () => {
  it('tidak menampilkan apa pun tanpa petunjuk', () => {
    expect(loader().find('[data-test="tip"]').exists()).toBe(false)
  })

  it('menampilkan petunjuk pertama lalu bergantian tiap beberapa detik', async () => {
    const w = loader({ tips: ['Satu', 'Dua', 'Tiga'] })
    expect(w.find('[data-test="tip"]').text()).toBe('Satu')
    vi.advanceTimersByTime(4000)
    await w.vm.$nextTick()
    expect(w.find('[data-test="tip"]').text()).toBe('Dua')
    vi.advanceTimersByTime(8000)
    await w.vm.$nextTick()
    expect(w.find('[data-test="tip"]').text()).toBe('Satu')
  })

  it('satu petunjuk tidak memasang timer', () => {
    loader({ tips: ['Satu'] })
    expect(vi.getTimerCount()).toBe(0)
  })
})

describe('varian ringkas', () => {
  it('tetap punya bilah, angka kecil, dan keterangan', () => {
    const w = loader({ compact: true, percent: 30, detail: 'Membaca halaman 3 dari 10' })
    expect(w.classes()).toContain('is-compact')
    expect(w.find('[data-test="percent"]').text()).toBe('30%')
    expect(w.text()).toContain('Membaca halaman 3 dari 10')
    expect(w.find('[role="progressbar"]').exists()).toBe(true)
  })

  it('tidak menampilkan petunjuk', () => {
    expect(loader({ compact: true, tips: ['Satu', 'Dua'] }).find('[data-test="tip"]').exists()).toBe(false)
  })
})
