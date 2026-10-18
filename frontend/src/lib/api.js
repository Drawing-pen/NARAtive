import axios from 'axios'
import { auth, logout } from '@/lib/auth'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
})

api.interceptors.request.use((config) => {
  if (auth.token) config.headers.Authorization = `Bearer ${auth.token}`
  return config
})

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const url = error.config?.url ?? ''
    const isAuthCall = url.startsWith('/auth/login') || url.startsWith('/auth/register')
    if (error.response?.status === 401 && !isAuthCall && auth.token) {
      logout()
      const { default: router } = await import('@/router')
      const current = router.currentRoute.value
      if (!current.meta.guest) router.replace({ name: 'login', query: { next: current.fullPath, expired: '1' } })
    }
    return Promise.reject(error)
  },
)

const FIELD_LABEL = { title: 'Judul', name: 'Nama', email: 'Email', password: 'Kata sandi' }

export function errorMessage(error, fallback = 'Terjadi kesalahan. Coba lagi.') {
  if (!error?.response) return 'Tidak dapat terhubung ke server. Pastikan backend sedang berjalan.'
  const detail = error.response.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length) {
    return detail
      .map((item) => {
        const field = item.loc?.[item.loc.length - 1]
        const label = FIELD_LABEL[field] ?? 'Isian'
        if (item.type?.includes('too_short')) return `${label} terlalu pendek (min. ${item.ctx?.min_length} karakter).`
        if (item.type?.includes('too_long')) return `${label} terlalu panjang.`
        if (item.type?.includes('value_error') && field === 'email') return 'Format email tidak valid.'
        return `${label} tidak valid.`
      })
      .join(' ')
  }
  return fallback
}

export default api