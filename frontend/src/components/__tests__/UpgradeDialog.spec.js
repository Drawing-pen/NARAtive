import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'

const get = vi.fn()
vi.mock('@/lib/api', () => ({ default: { get: (...args) => get(...args) } }))

import UpgradeDialog from '@/components/UpgradeDialog.vue'
import { auth } from '@/lib/auth'
import { closeUpgrade, showUpgrade, upgrade } from '@/lib/upgrade'

const OVERVIEW = { upgrade_prices: { middle: 29000, high: 59000 }, period_days: 30 }
const stub = { template: '<div />' }
const mounted = []

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: stub },
      { path: '/berlangganan', name: 'plans', component: stub },
      { path: '/bayar', name: 'checkout', component: stub },
    ],
  })
}

async function open(options = { tier: 'middle', message: 'Fitur ini khusus pengguna Middle Tier.' }) {
  const router = makeRouter()
  router.push('/')
  await router.isReady()
  const w = mount(UpgradeDialog, { global: { plugins: [router], stubs: { Icon: true } } })
  mounted.push(w)
  if (options) showUpgrade(options)
  await flushPromises()
  return { w, router }
}

const card = (w, key) => w.find(`[data-test="plan-${key}"]`)

beforeEach(() => {
  mounted.splice(0).forEach((w) => w.unmount())
  closeUpgrade()
  get.mockReset()
  get.mockResolvedValue({ data: OVERVIEW })
  auth.token = 'token'
  auth.user = { tier: 'free' }
})

describe('UpgradeDialog', () => {
  it('tidak menampilkan apa pun saat tertutup', async () => {
    const { w } = await open(null)
    expect(w.find('[role="dialog"]').exists()).toBe(false)
  })

  it('menampilkan judul, alasan, dan dua kartu paket dengan harga', async () => {
    const { w } = await open()
    const dialog = w.find('[role="dialog"]')
    expect(dialog.text()).toContain('Tingkatkan paketmu')
    expect(dialog.text()).toContain('Fitur ini khusus pengguna Middle Tier.')
    expect(card(w, 'middle').text()).toContain('Rp 29.000')
    expect(card(w, 'high').text()).toContain('Rp 59.000')
    expect(w.find('[data-test="plan-standard"]').exists()).toBe(false)
  })

  it('menandai tier yang dibutuhkan', async () => {
    const { w } = await open({ tier: 'high', message: 'Fitur ini khusus pengguna High Tier.' })
    expect(card(w, 'high').text()).toContain('Dibutuhkan')
    expect(card(w, 'middle').text()).not.toContain('Dibutuhkan')
  })

  it('untuk batas paket pengguna Standard menyorot Middle', async () => {
    const { w } = await open({ tier: null, message: 'Kuota habis.', quota: true })
    expect(card(w, 'middle').text()).toContain('Dibutuhkan')
    expect(card(w, 'high').text()).not.toContain('Dibutuhkan')
  })

  it('untuk batas paket pengguna Middle menyorot High', async () => {
    auth.user = { tier: 'middle' }
    const { w } = await open({ tier: null, message: 'Kuota habis.', quota: true })
    expect(card(w, 'high').text()).toContain('Dibutuhkan')
  })

  it('paket yang sudah dimiliki ditandai dan tombolnya nonaktif', async () => {
    auth.user = { tier: 'middle' }
    const { w } = await open({ tier: 'high', message: 'x' })
    expect(card(w, 'middle').text()).toContain('Paketmu saat ini')
    expect(card(w, 'middle').find('button').attributes('disabled')).toBeDefined()
    expect(card(w, 'high').find('button').attributes('disabled')).toBeUndefined()
  })

  it('memilih paket menutup pop-up dan membuka halaman pembayaran', async () => {
    const { w, router } = await open({ tier: 'high', message: 'x' })
    await card(w, 'high').find('button').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.name).toBe('checkout')
    expect(router.currentRoute.value.query).toEqual({ paket: 'high' })
    expect(upgrade.open).toBe(false)
  })

  it('tautan beli analisis tambahan hanya muncul untuk batas paket', async () => {
    const quota = await open({ tier: null, message: 'Kuota habis.', quota: true })
    expect(quota.w.find('[data-test="buy-checks"]').exists()).toBe(true)
    closeUpgrade()
    const feature = await open({ tier: 'middle', message: 'Khusus Middle.' })
    expect(feature.w.find('[data-test="buy-checks"]').exists()).toBe(false)
  })

  it('tautan lihat semua paket menutup pop-up dan membuka halaman paket', async () => {
    const { w, router } = await open()
    await w.find('[data-test="all-plans"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.name).toBe('plans')
    expect(upgrade.open).toBe(false)
  })

  it('tombol tutup menutup pop-up', async () => {
    const { w } = await open()
    await w.find('[aria-label="Tutup"]').trigger('click')
    expect(upgrade.open).toBe(false)
  })

  it('Esc menutup pop-up', async () => {
    const { w } = await open()
    await w.find('[role="dialog"]').trigger('keydown', { key: 'Escape' })
    expect(upgrade.open).toBe(false)
  })

  it('klik latar menutup pop-up tetapi klik di dalam kotak tidak', async () => {
    const { w } = await open()
    await w.find('[role="dialog"]').trigger('click')
    expect(upgrade.open).toBe(true)
    await w.find('[data-test="backdrop"]').trigger('click')
    expect(upgrade.open).toBe(false)
  })

  it('harga disembunyikan bila daftar harga gagal dimuat tetapi pilihan tetap bisa dipakai', async () => {
    get.mockRejectedValue(new Error('mati'))
    const { w } = await open()
    expect(card(w, 'middle').text()).not.toContain('Rp')
    expect(card(w, 'middle').find('button').attributes('disabled')).toBeUndefined()
  })
})
