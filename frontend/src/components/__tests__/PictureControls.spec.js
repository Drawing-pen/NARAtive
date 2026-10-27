import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const put = vi.fn()
const del = vi.fn()
const state = { high: true }

vi.mock('@/lib/api', () => ({
  default: { put: (...args) => put(...args), delete: (...args) => del(...args) },
  errorMessage: (e, fallback) => e?.response?.data?.detail ?? fallback,
}))
vi.mock('@/lib/auth', () => ({ hasTier: () => state.high }))

import PictureControls from '@/components/PictureControls.vue'

const PATH = '/documents/1/cover'

function mountControls(props = {}) {
  return mount(PictureControls, {
    props: { path: PATH, label: 'Ganti cover', ...props },
    global: { stubs: { Icon: true, RouterLink: { template: '<a data-test="plans"><slot /></a>' } } },
  })
}

async function choose(wrapper, file) {
  const input = wrapper.find('input[type=file]')
  Object.defineProperty(input.element, 'files', { value: [file], configurable: true })
  await input.trigger('change')
  await flushPromises()
}

const image = (bytes = 10) => new File([new Uint8Array(bytes)], 'cover.png', { type: 'image/png' })

beforeEach(() => {
  put.mockReset()
  del.mockReset()
  state.high = true
})

describe('PictureControls', () => {
  it('sends the chosen file to the endpoint and reports the change', async () => {
    put.mockResolvedValue({ data: {} })
    const w = mountControls()
    await choose(w, image())
    expect(put).toHaveBeenCalledTimes(1)
    const [path, form] = put.mock.calls[0]
    expect(path).toBe(PATH)
    expect(form.get('file').name).toBe('cover.png')
    expect(w.emitted('changed')).toEqual([[true]])
  })

  it('refuses a file over 2 MB without calling the server', async () => {
    const w = mountControls()
    await choose(w, image(2 * 1024 * 1024 + 1))
    expect(put).not.toHaveBeenCalled()
    expect(w.text()).toContain('Ukuran gambar maksimal 2 MB.')
    expect(w.emitted('changed')).toBeUndefined()
  })

  it('shows the server message when the upload is rejected', async () => {
    put.mockRejectedValue({ response: { data: { detail: 'Format gambar tidak didukung. Gunakan JPG, PNG, atau WebP.' } } })
    const w = mountControls()
    await choose(w, image())
    expect(w.find('[role=alert]').text()).toContain('Format gambar tidak didukung')
    expect(w.emitted('changed')).toBeUndefined()
  })

  it('offers the default only when there is a picture, and reports the reset', async () => {
    const without = mountControls({ hasPicture: false })
    expect(without.find('[aria-label="Kembalikan ke gambar bawaan"]').exists()).toBe(false)

    del.mockResolvedValue({})
    const w = mountControls({ hasPicture: true })
    await w.find('[aria-label="Kembalikan ke gambar bawaan"]').trigger('click')
    await flushPromises()
    expect(del).toHaveBeenCalledWith(PATH)
    expect(w.emitted('changed')).toEqual([[false]])
  })

  it('shows a link to the plans instead of the controls below High', () => {
    state.high = false
    const w = mountControls({ hasPicture: true })
    expect(w.find('[data-test=plans]').exists()).toBe(true)
    expect(w.find('input[type=file]').exists()).toBe(false)
    expect(w.find('[aria-label="Kembalikan ke gambar bawaan"]').exists()).toBe(false)
  })
})
