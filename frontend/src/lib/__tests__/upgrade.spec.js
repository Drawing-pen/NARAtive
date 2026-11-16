import { beforeEach, describe, expect, it } from 'vitest'
import api, { errorMessage } from '@/lib/api'
import { auth } from '@/lib/auth'
import { closeUpgrade, showUpgrade, upgrade } from '@/lib/upgrade'

const rejected = api.interceptors.response.handlers[0].rejected

function failure(status, detail, url = '/documents/1/summary') {
  return { config: { url }, response: { status, data: { detail } } }
}

async function pass(error) {
  try {
    await rejected(error)
  } catch (e) {
    return e
  }
  return null
}

beforeEach(() => {
  closeUpgrade()
  auth.token = 'token'
  auth.user = { tier: 'free' }
})

describe('state pop-up', () => {
  it('showUpgrade membuka pop-up dengan tier dan pesan', () => {
    showUpgrade({ tier: 'high', message: 'Khusus High.' })
    expect(upgrade).toMatchObject({ open: true, tier: 'high', message: 'Khusus High.', quota: false })
  })

  it('pemanggilan kedua saat masih terbuka diabaikan', () => {
    showUpgrade({ tier: 'high', message: 'Pertama.' })
    showUpgrade({ tier: 'middle', message: 'Kedua.' })
    expect(upgrade.message).toBe('Pertama.')
    expect(upgrade.tier).toBe('high')
  })

  it('closeUpgrade menutup dan menyetel ulang', () => {
    showUpgrade({ tier: 'high', message: 'x', quota: true })
    closeUpgrade()
    expect(upgrade).toMatchObject({ open: false, tier: null, message: '', quota: false })
    showUpgrade({ tier: 'middle', message: 'baru' })
    expect(upgrade.message).toBe('baru')
  })
})

describe('interseptor respons', () => {
  it('403 fitur khusus Middle membuka pop-up dengan tier middle', async () => {
    const error = await pass(failure(403, 'Fitur ini khusus pengguna Middle Tier.'))
    expect(upgrade).toMatchObject({ open: true, tier: 'middle', message: 'Fitur ini khusus pengguna Middle Tier.', quota: false })
    expect(error.tierDenied).toBe(true)
  })

  it('403 fitur khusus High membuka pop-up dengan tier high', async () => {
    await pass(failure(403, 'Fitur ini khusus pengguna High Tier.'))
    expect(upgrade).toMatchObject({ open: true, tier: 'high' })
  })

  it('402 batas paket membuka pop-up kuota tanpa tier tertentu', async () => {
    const error = await pass(failure(402, 'Kuota analisis bulan ini habis.', '/documents'))
    expect(upgrade).toMatchObject({ open: true, tier: null, message: 'Kuota analisis bulan ini habis.', quota: true })
    expect(error.tierDenied).toBe(true)
  })

  it('403 lain (akun tidak aktif) tidak membuka pop-up', async () => {
    const error = await pass(failure(403, 'Akun tidak aktif.', '/auth/login'))
    expect(upgrade.open).toBe(false)
    expect(error.tierDenied).toBeUndefined()
  })

  it('galat biasa tidak membuka pop-up', async () => {
    await pass(failure(500, 'Meledak.'))
    await pass(failure(404, 'Tidak ada.'))
    expect(upgrade.open).toBe(false)
  })

  it('tanpa sesi masuk tidak membuka pop-up', async () => {
    auth.token = null
    await pass(failure(402, 'Kuota habis.'))
    expect(upgrade.open).toBe(false)
  })

  it('galat tetap ditolak agar pemanggil bisa menanganinya', async () => {
    const original = failure(403, 'Fitur ini khusus pengguna Middle Tier.')
    expect(await pass(original)).toBe(original)
  })
})

describe('errorMessage', () => {
  it('mengembalikan teks kosong untuk penolakan tier agar tidak tampil error mentah', async () => {
    const error = await pass(failure(402, 'Kuota habis.'))
    expect(errorMessage(error, 'Gagal.')).toBe('')
  })

  it('tetap menampilkan pesan untuk galat biasa', async () => {
    const error = await pass(failure(409, 'Analisis belum selesai.'))
    expect(errorMessage(error, 'Gagal.')).toBe('Analisis belum selesai.')
  })
})
