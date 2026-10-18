import { reactive } from 'vue'
import api from '@/lib/api'

const KEY = 'narative.auth'

function readSaved() {
  try {
    const saved = JSON.parse(localStorage.getItem(KEY) || 'null')
    if (saved?.token && saved?.user) return saved
  } catch {
    return null
  }
  return null
}

function persist(token, user) {
  try {
    if (token) localStorage.setItem(KEY, JSON.stringify({ token, user }))
    else localStorage.removeItem(KEY)
  } catch {
    return
  }
}

const saved = readSaved()

export const auth = reactive({
  token: saved?.token ?? null,
  user: saved?.user ?? null,
})

export function isLoggedIn() {
  return Boolean(auth.token)
}

function apply({ access_token, user }) {
  auth.token = access_token
  auth.user = user
  persist(access_token, user)
}

export async function login(email, password) {
  const { data } = await api.post('/auth/login', { email, password })
  apply(data)
}

export async function register(name, email, password) {
  const { data } = await api.post('/auth/register', { name, email, password })
  apply(data)
}

export function logout() {
  auth.token = null
  auth.user = null
  persist(null, null)
}