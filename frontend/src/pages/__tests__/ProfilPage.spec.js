import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const get = vi.fn()
const renameAccount = vi.fn()
const changePassword = vi.fn()
const deleteAccount = vi.fn()
const refreshUser = vi.fn()
const replace = vi.fn()
const route = { hash: '' }
const USER = { name: 'Rana', email: 'rana@example.com', created_at: '2026-10-01T08:00:00', tier: 'free' }

vi.mock('@/lib/api', () => ({
  default: { get: (...args) => get(...args) },
  errorMessage: (e, fallback) => e?.response?.data?.detail ?? fallback,
}))
vi.mock('@/lib/auth', async () => {
  const { reactive } = await import('vue')
  return {
  auth: reactive({ user: null }),
  renameAccount: (...args) => renameAccount(...args),
  changePassword: (...args) => changePassword(...args),
  deleteAccount: (...args) => deleteAccount(...args),
  refreshUser: (...args) => refreshUser(...args),
  }
})
vi.mock('vue-router', () => ({ useRoute: () => route, useRouter: () => ({ replace }) }))

import { auth } from '@/lib/auth'
import ProfilPage from '@/pages/ProfilPage.vue'

const OVERVIEW = {
  tier: 'free',
  paid_tier: 'free',
  tier_expires_at: null,
  usage: { used: 2, monthly_limit: 3, extra_checks: 4, active_books: 1, max_active: 3, max_pages: 50, resets_at: '2026-11-01T00:00:00' },
  banks: ['bca'],
  provider: 'simulated',
}
const TX = (o = {}) => ({
  order_id: 'NAR-1-aaaa', kind: 'upgrade', plan: 'middle', quantity: 1, amount: 29000, bank: 'bca',
  status: 'paid', created_at: '2026-10-20T10:00:00', ...o,
})

function serve(overview = OVERVIEW, transactions = []) {
  get.mockImplementation(async (url) => {
    if (url === '/billing/overview') return { data: overview }
    if (url === '/billing/transactions') return { data: transactions }
    throw new Error(`url tak terduga: ${url}`)
  })
}

async function open() {
  const wrapper = mount(ProfilPage, {
    global: {
      stubs: {
        Icon: true,
        RouterLink: { template: '<a><slot /></a>' },
        CheckoutDialog: { props: ['resume'], template: '<div data-test="dialog">{{ resume?.order_id }}</div>' },
      },
    },
  })
  await flushPromises()
  return wrapper
}

const button = (w, text) => w.findAll('button').find((b) => b.text().includes(text))

beforeEach(() => {
  for (const fn of [get, renameAccount, changePassword, deleteAccount, refreshUser, replace]) fn.mockReset()
  route.hash = ''
  auth.user = { ...USER }
  serve()
})

describe('account information', () => {
  it('shows the name, email, and join date', async () => {
    const w = await open()
    expect(w.find('[data-test=name]').text()).toBe('Rana')
    expect(w.find('[data-test=email]').text()).toBe('rana@example.com')
    expect(w.text()).toContain('2026')
  })

  it('refreshes the saved user so older sessions get the join date', async () => {
    await open()
    expect(refreshUser).toHaveBeenCalled()
  })

  it('shows the plan and when it ends', async () => {
    serve({ ...OVERVIEW, tier: 'middle', paid_tier: 'middle', tier_expires_at: '2026-11-20T00:00:00' })
    const w = await open()
    expect(w.find('[data-test=plan-ends]').text()).toContain('Aktif sampai')
    serve()
    expect((await open()).find('[data-test=plan-ends]').text()).toBe('Gratis, tanpa masa berlaku')
  })

  it('shows an error when the data cannot be loaded', async () => {
    get.mockRejectedValue({ response: { data: { detail: 'Server error.' } } })
    const w = await open()
    expect(w.find('[role=alert]').text()).toContain('Server error.')
  })
})

describe('usage', () => {
  it('shows the remaining numbers', async () => {
    const w = await open()
    const text = w.find('[data-test=usage]').text()
    expect(text).toContain('2 / 3')
    expect(w.find('[data-test=extra]').text()).toBe('4')
    expect(w.find('[data-test=books]').text()).toBe('1 / 3')
    expect(text).toContain('50 halaman')
  })

  it('shows unlimited for High', async () => {
    serve({ ...OVERVIEW, paid_tier: 'high', usage: { ...OVERVIEW.usage, monthly_limit: null, max_active: null, max_pages: null } })
    const w = await open()
    expect(w.find('[data-test=usage]').text()).toContain('tanpa batas')
    expect(w.find('[data-test=books]').text()).toBe('1')
    expect(w.find('[data-test=usage]').text()).toContain('Tanpa batas')
  })
})

describe('payment history', () => {
  it('says so when there are no transactions', async () => {
    const w = await open()
    expect(w.find('[data-test=no-history]').exists()).toBe(true)
  })

  it('lists transactions with their status', async () => {
    serve(OVERVIEW, [TX(), TX({ order_id: 'NAR-1-bbbb', kind: 'pay_per_check', plan: null, quantity: 3, amount: 15000, status: 'expired' })])
    const w = await open()
    const rows = w.findAll('[data-test=transaction]')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('Paket Middle')
    expect(rows[0].text()).toContain('Berhasil')
    expect(rows[1].text()).toContain('3 analisis tambahan')
    expect(rows[1].text()).toContain('Kedaluwarsa')
  })

  it('offers to continue only pending payments and opens the dialog', async () => {
    serve(OVERVIEW, [TX(), TX({ order_id: 'NAR-1-wait', status: 'pending' })])
    const w = await open()
    expect(w.findAll('button').filter((b) => b.text().includes('Lanjutkan bayar'))).toHaveLength(1)
    expect(w.text()).toContain('1 menunggu')
    await button(w, 'Lanjutkan bayar').trigger('click')
    expect(w.find('[data-test=dialog]').text()).toBe('NAR-1-wait')
  })
})

describe('rename', () => {
  async function startEditing() {
    const w = await open()
    await w.find('[aria-label="Ubah nama"]').trigger('click')
    return w
  }

  it('saves the new name', async () => {
    renameAccount.mockResolvedValue()
    const w = await startEditing()
    await w.find('input[aria-label=Nama]').setValue('  Rana Baru ')
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(renameAccount).toHaveBeenCalledWith('Rana Baru')
    expect(w.find('input[aria-label=Nama]').exists()).toBe(false)
  })

  it('refuses an empty name without calling the server', async () => {
    const w = await startEditing()
    await w.find('input[aria-label=Nama]').setValue('   ')
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(renameAccount).not.toHaveBeenCalled()
    expect(w.text()).toContain('Nama tidak boleh kosong.')
  })

  it('shows the server message and stays in edit mode on failure', async () => {
    renameAccount.mockRejectedValue({ response: { data: { detail: 'Nama tidak valid.' } } })
    const w = await startEditing()
    await w.find('input[aria-label=Nama]').setValue('Baru')
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(w.text()).toContain('Nama tidak valid.')
    expect(w.find('input[aria-label=Nama]').exists()).toBe(true)
  })

  it('cancels without saving', async () => {
    const w = await startEditing()
    await button(w, 'Batal').trigger('click')
    expect(renameAccount).not.toHaveBeenCalled()
    expect(w.find('[data-test=name]').text()).toBe('Rana')
  })
})

describe('change password', () => {
  async function fill(w, current, next, again) {
    await w.find('#sandi-lama').setValue(current)
    await w.find('#sandi-baru').setValue(next)
    await w.find('#sandi-ulang').setValue(again)
    await w.find('#sandi-lama').element.form.dispatchEvent(new Event('submit'))
    await flushPromises()
  }

  it('sends the passwords and clears the fields', async () => {
    changePassword.mockResolvedValue()
    const w = await open()
    await fill(w, 'lama-12345', 'baru-123456', 'baru-123456')
    expect(changePassword).toHaveBeenCalledWith('lama-12345', 'baru-123456')
    expect(w.find('[role=status]').text()).toContain('berhasil')
    expect(w.find('#sandi-lama').element.value).toBe('')
  })

  it('refuses a short new password', async () => {
    const w = await open()
    await fill(w, 'lama-12345', 'pendek', 'pendek')
    expect(changePassword).not.toHaveBeenCalled()
    expect(w.text()).toContain('minimal 8 karakter')
  })

  it('refuses when the confirmation differs', async () => {
    const w = await open()
    await fill(w, 'lama-12345', 'baru-123456', 'baru-654321')
    expect(changePassword).not.toHaveBeenCalled()
    expect(w.text()).toContain('Konfirmasi kata sandi baru tidak sama.')
  })

  it('shows the server message when the current password is wrong', async () => {
    changePassword.mockRejectedValue({ response: { data: { detail: 'Kata sandi lama salah.' } } })
    const w = await open()
    await fill(w, 'salah-12345', 'baru-123456', 'baru-123456')
    expect(w.text()).toContain('Kata sandi lama salah.')
    expect(w.find('[role=status]').exists()).toBe(false)
  })
})

describe('delete account', () => {
  it('asks for the password before deleting anything', async () => {
    const w = await open()
    expect(w.find('#sandi-hapus').exists()).toBe(false)
    await button(w, 'Hapus akun saya').trigger('click')
    expect(w.find('#sandi-hapus').exists()).toBe(true)
    expect(button(w, 'Hapus permanen').element.disabled).toBe(true)
    expect(deleteAccount).not.toHaveBeenCalled()
  })

  it('deletes and goes to the home page', async () => {
    deleteAccount.mockResolvedValue()
    const w = await open()
    await button(w, 'Hapus akun saya').trigger('click')
    await w.find('#sandi-hapus').setValue('sandi-uji-123')
    await w.find('#sandi-hapus').element.form.dispatchEvent(new Event('submit'))
    await flushPromises()
    expect(deleteAccount).toHaveBeenCalledWith('sandi-uji-123')
    expect(replace).toHaveBeenCalledWith({ name: 'home' })
  })

  it('stays on the page and shows the message when the password is wrong', async () => {
    deleteAccount.mockRejectedValue({ response: { data: { detail: 'Kata sandi salah.' } } })
    const w = await open()
    await button(w, 'Hapus akun saya').trigger('click')
    await w.find('#sandi-hapus').setValue('salah')
    await w.find('#sandi-hapus').element.form.dispatchEvent(new Event('submit'))
    await flushPromises()
    expect(w.text()).toContain('Kata sandi salah.')
    expect(replace).not.toHaveBeenCalled()
  })

  it('can be cancelled', async () => {
    const w = await open()
    await button(w, 'Hapus akun saya').trigger('click')
    await w.find('#sandi-hapus').setValue('abc')
    await button(w, 'Batal').trigger('click')
    expect(w.find('#sandi-hapus').exists()).toBe(false)
    expect(deleteAccount).not.toHaveBeenCalled()
  })
})
