import { onBeforeUnmount, onMounted, ref } from 'vue'
import api, { errorMessage } from '@/lib/api'

export function useCharacters(getId) {
  const doc = ref(null)
  const data = ref(null)
  const loading = ref(true)
  const missing = ref(false)
  const error = ref('')
  const locked = ref(false)
  const starting = ref(false)
  let timer = null

  async function load(silent = false) {
    try {
      const id = getId()
      const [d, c] = await Promise.all([api.get(`/documents/${id}`), api.get(`/documents/${id}/characters`)])
      doc.value = d.data
      data.value = c.data
      locked.value = false
      error.value = ''
    } catch (e) {
      if (e.response?.status === 404) missing.value = true
      else if (e.response?.status === 403) {
        locked.value = true
        doc.value = (await api.get(`/documents/${getId()}`).catch(() => null))?.data ?? null
      }
      else if (!silent) error.value = errorMessage(e, 'Gagal mengambil data tokoh.')
    } finally {
      loading.value = false
    }
  }

  async function start(ai = false) {
    starting.value = true
    error.value = ''
    try {
      const { data: next } = await api.post(`/documents/${getId()}/characters`, null, { params: { ai: ai === true } })
      data.value = next
    } catch (e) {
      error.value = errorMessage(e, 'Gagal memulai pendeteksian tokoh.')
    } finally {
      starting.value = false
    }
  }

  onMounted(() => {
    load()
    timer = setInterval(() => {
      if (data.value?.status === 'running') load(true)
    }, 3000)
  })
  onBeforeUnmount(() => clearInterval(timer))

  return { doc, data, loading, missing, error, locked, starting, start }
}