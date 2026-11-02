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

export async function startRegistration(name, email, password) {
  const { data } = await api.post('/auth/register', { name, email, password })
  return data
}

export async function resendCode(email) {
  const { data } = await api.post('/auth/register/resend', { email })
  return data
}

export async function verifyRegistration(email, code) {
  const { data } = await api.post('/auth/register/verify', { email, code })
  apply(data)
}

export async function requestPasswordReset(email) {
  const { data } = await api.post('/auth/password/forgot', { email })
  return data
}

export async function resetPassword(email, code, newPassword) {
  const { data } = await api.post('/auth/password/reset', { email, code, new_password: newPassword })
  apply(data)
}

// backend menamai paket gratis "free", UI menyebutnya "standard"
export const tierKey = () => (auth.user?.tier === 'free' || !auth.user?.tier ? 'standard' : auth.user.tier)
export const isHighTier = () => tierKey() === 'high'
const TIER_RANK = { standard: 0, middle: 1, high: 2 }
export const hasTier = (minimum) => TIER_RANK[tierKey()] >= TIER_RANK[minimum]

// tingkatan akun bisa berubah di server (mis. setelah upgrade), jadi sinkronkan data pengguna yang tersimpan
export async function refreshUser() {
  if (!auth.token) return
  try {
    const { data } = await api.get('/auth/me')
    auth.user = data
    persist(auth.token, data)
  } catch {
    /* 401 ditangani interceptor; galat lain tidak mengubah sesi */
  }
}

export async function renameAccount(name) {
  const { data } = await api.patch('/auth/me', { name })
  auth.user = data
  persist(auth.token, data)
}

export async function changePassword(currentPassword, newPassword) {
  await api.put('/auth/me/password', { current_password: currentPassword, new_password: newPassword })
}

export async function deleteAccount(password) {
  await api.delete('/auth/me', { data: { password } })
  logout()
}

export function logout() {
  auth.token = null
  auth.user = null
  persist(null, null)
}