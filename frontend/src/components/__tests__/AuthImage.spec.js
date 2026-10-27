import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const get = vi.fn()

vi.mock('@/lib/api', () => ({ default: { get: (...args) => get(...args) } }))

import AuthImage from '@/components/AuthImage.vue'

const PATH = '/documents/1/cover'

function mountImage(props = {}) {
  return mount(AuthImage, { props: { path: PATH, ...props }, slots: { default: '<span data-test="fallback">A</span>' } })
}

beforeEach(() => {
  get.mockReset()
  URL.createObjectURL = vi.fn(() => 'blob:gambar')
  URL.revokeObjectURL = vi.fn()
})

describe('AuthImage', () => {
  it('fetches the picture as a blob and shows it', async () => {
    get.mockResolvedValue({ data: new Blob(['x']) })
    const w = mountImage()
    await flushPromises()
    expect(get).toHaveBeenCalledWith(PATH, { responseType: 'blob' })
    expect(w.find('img').attributes('src')).toBe('blob:gambar')
    expect(w.find('[data-test=fallback]').exists()).toBe(false)
  })

  it('does not call the server when there is no picture, and shows the fallback', async () => {
    const w = mountImage({ active: false })
    await flushPromises()
    expect(get).not.toHaveBeenCalled()
    expect(w.find('[data-test=fallback]').exists()).toBe(true)
    expect(w.find('img').exists()).toBe(false)
  })

  it('falls back when the picture cannot be loaded', async () => {
    get.mockRejectedValue(new Error('404'))
    const w = mountImage()
    await flushPromises()
    expect(w.find('[data-test=fallback]').exists()).toBe(true)
  })

  it('reloads when the version changes and frees the old picture', async () => {
    get.mockResolvedValue({ data: new Blob(['x']) })
    const w = mountImage({ version: 0 })
    await flushPromises()
    await w.setProps({ version: 1 })
    await flushPromises()
    expect(get).toHaveBeenCalledTimes(2)
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:gambar')
  })

  it('returns to the fallback and frees the picture when it is removed', async () => {
    get.mockResolvedValue({ data: new Blob(['x']) })
    const w = mountImage()
    await flushPromises()
    await w.setProps({ active: false })
    await flushPromises()
    expect(w.find('img').exists()).toBe(false)
    expect(URL.revokeObjectURL).toHaveBeenCalled()
  })

  it('frees the picture when the component goes away', async () => {
    get.mockResolvedValue({ data: new Blob(['x']) })
    const w = mountImage()
    await flushPromises()
    w.unmount()
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:gambar')
  })
})
