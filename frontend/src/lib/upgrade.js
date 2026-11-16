import { reactive } from 'vue'

export const upgrade = reactive({ open: false, tier: null, message: '', quota: false })

export function showUpgrade({ tier = null, message = '', quota = false } = {}) {
  if (upgrade.open) return
  Object.assign(upgrade, { open: true, tier, message, quota })
}

export function closeUpgrade() {
  Object.assign(upgrade, { open: false, tier: null, message: '', quota: false })
}

const TIER_ONLY = /khusus pengguna (Middle|High) Tier/

export function tierDenial(error) {
  const status = error?.response?.status
  const detail = error?.response?.data?.detail
  const message = typeof detail === 'string' ? detail : ''
  if (status === 402) return { tier: null, message, quota: true }
  if (status === 403) {
    const match = TIER_ONLY.exec(message)
    if (match) return { tier: match[1].toLowerCase(), message, quota: false }
  }
  return null
}
