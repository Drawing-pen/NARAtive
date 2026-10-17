import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
})

const FIELD_LABEL = { title: 'Judul' }

/** Ubah error axios/FastAPI menjadi pesan yang ramah dibaca. */
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