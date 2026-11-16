import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const get = vi.fn()
const push = vi.fn()

vi.mock('@/lib/api', () => ({
  default: { get: (...args) => get(...args) },
  errorMessage: (e, fallback) => e?.response?.data?.detail ?? fallback,
}))
vi.mock('@/lib/auth', () => ({ isLoggedIn: () => true }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push }) }))

import BerlanggananPage from '@/pages/BerlanggananPage.vue'

const OVERVIEW = (o = {}) => ({
  tier: 'free', paid_tier: 'free', tier_expires_at: null,
  usage: { used: 1, monthly_limit: 3, extra_checks: 0, active_books: 1, max_active: 3, max_pages: 50, resets_at: '2026-12-01T00:00:00' },
  upgrade_prices: { middle: 29000, high: 59000 }, period_days: 30, pay_per_check_price: 5000, pay_per_check_max: 10,
  banks: ['bca'], provider: 'simulated', ...o,
})

async function open(overview = OVERVIEW()) {
  get.mockImplementation(async (url) => ({ data: url === '/billing/overview' ? overview : [] }))
  const w = mount(BerlanggananPage, { global: { stubs: { Icon: true, RouterLink: { template: '<a><slot /></a>' }, TierChip: true } } })
  await flushPromises()
  return w
}

const button = (w, text) => w.findAll('button').find((b) => b.text().includes(text))

beforeEach(() => {
  get.mockReset()
  push.mockReset()
})

describe('BerlanggananPage membuka halaman pembayaran', () => {
  it('memilih Middle membuka /bayar dengan paket middle', async () => {
    const w = await open()
    await button(w, 'Pilih paket Middle').trigger('click')
    expect(push).toHaveBeenCalledWith({ name: 'checkout', query: { paket: 'middle' } })
  })

  it('memilih High membuka /bayar dengan paket high', async () => {
    const w = await open()
    await button(w, 'Pilih paket High').trigger('click')
    expect(push).toHaveBeenCalledWith({ name: 'checkout', query: { paket: 'high' } })
  })

  it('perpanjang paket yang sama tetap menuju /bayar', async () => {
    const w = await open(OVERVIEW({ paid_tier: 'middle', tier: 'middle' }))
    await button(w, 'Perpanjang Middle').trigger('click')
    expect(push).toHaveBeenCalledWith({ name: 'checkout', query: { paket: 'middle' } })
  })

  it('analisis tambahan membawa jumlah yang dipilih', async () => {
    const w = await open()
    await w.findAll('[role="radio"]')[1].trigger('click')
    await button(w, 'Beli analisis tambahan').trigger('click')
    expect(push).toHaveBeenCalledWith({ name: 'checkout', query: { jenis: 'analisis', jumlah: 3 } })
  })

  it('tidak lagi memuat dialog pembayaran di halaman ini', async () => {
    const w = await open()
    expect(w.find('[role="dialog"]').exists()).toBe(false)
  })
})
