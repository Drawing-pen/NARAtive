export const RATINGS = {
  General: {
    label: 'General',
    note: 'Aman untuk hampir semua pembaca.',
    cls: 'bg-lavender/20 text-navy',
    icon: 'lucide:smile',
  },
  Teen: {
    label: 'Teen',
    note: 'Ada muatan ringan hingga sedang.',
    cls: 'bg-amber/35 text-navy',
    icon: 'lucide:book-open',
  },
  Mature: {
    label: 'Mature',
    note: 'Muatan dewasa yang cukup signifikan.',
    cls: 'bg-navy text-white',
    icon: 'lucide:shield-alert',
  },
  Explicit: {
    label: 'Explicit',
    note: 'Muatan eksplisit, hanya untuk pembaca dewasa.',
    cls: 'bg-danger text-white',
    icon: 'lucide:octagon-alert',
  },
}

export const DIMENSIONS = {
  profanity: { label: 'Bahasa kasar', icon: 'lucide:message-square-warning' },
  sexual: { label: 'Konten seksual', icon: 'lucide:flame' },
  violence: { label: 'Kekerasan', icon: 'lucide:swords' },
}

export const STANDARD_THRESHOLDS = { profanity: 0.5, sexual: 0.5, violence: 0.8 }

// Safe Mode standar hanya menyamarkan konten seksual; null = jenis konten itu tidak disamarkan.
// Cermin STANDARD_PROFILE di backend (services/sensitivity.py), dipakai bila profil belum termuat.
export const STANDARD_SAFE_MODE = { profanity: null, sexual: 0.5, violence: null }

export const EMOTIONS = {
  sad: { label: 'Sedih', icon: 'lucide:cloud-rain' },
  angry: { label: 'Marah', icon: 'lucide:flame-kindling' },
  fear: { label: 'Takut', icon: 'lucide:ghost' },
  happy: { label: 'Senang', icon: 'lucide:sun' },
}

export const STATUS = {
  queued: { label: 'Menunggu antrean', cls: 'bg-sand text-muted', icon: 'lucide:hourglass' },
  analyzing: { label: 'Sedang dianalisis', cls: 'bg-amber/35 text-navy', icon: 'lucide:loader-circle', spin: true },
  done: { label: 'Selesai dianalisis', cls: 'bg-lavender/20 text-navy', icon: 'lucide:circle-check' },
  failed: { label: 'Analisis gagal', cls: 'bg-danger/10 text-danger', icon: 'lucide:circle-x' },
}

export function formatDate(iso) {
  if (!iso) return ''
  return new Date(iso + (iso.endsWith('Z') ? '' : 'Z')).toLocaleDateString('id-ID', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

export function formatDateTime(iso) {
  if (!iso) return ''
  return new Date(iso + (iso.endsWith('Z') ? '' : 'Z')).toLocaleString('id-ID', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export const rupiah = (n) => `Rp ${Number(n).toLocaleString('id-ID')}`

export const BANKS = { bca: 'BCA', bni: 'BNI', bri: 'BRI', permata: 'Permata' }

export const TX_STATUS = {
  pending: { label: 'Menunggu pembayaran', cls: 'bg-amber/35 text-navy', icon: 'lucide:hourglass' },
  paid: { label: 'Berhasil', cls: 'bg-lavender/20 text-navy', icon: 'lucide:circle-check' },
  failed: { label: 'Gagal', cls: 'bg-danger/10 text-danger', icon: 'lucide:circle-x' },
  expired: { label: 'Kedaluwarsa', cls: 'bg-sand text-muted', icon: 'lucide:clock-alert' },
  cancelled: { label: 'Dibatalkan', cls: 'bg-sand text-muted', icon: 'lucide:ban' },
}

export const txItem = (tx) => (tx.kind === 'upgrade' ? `Paket ${TIERS[tx.plan].label} (30 hari)` : `${tx.quantity} analisis tambahan`)

export const num =(n) => (n === null || n === undefined ? '-' : String(n).replace('.', ','))

export const TIERS = {
  standard: { label: 'Standard', cls: 'bg-sand text-navy', icon: 'lucide:user' },
  middle: { label: 'Middle', cls: 'bg-lavender/25 text-navy', icon: 'lucide:lock' },
  high: { label: 'High', cls: 'bg-amber/40 text-navy', icon: 'lucide:lock' },
}

export const ROLES = {
  'Tokoh utama': { chip: 'bg-navy text-white', avatar: 'bg-navy text-white', node: 'fill-navy' },
  'Tokoh pendukung': { chip: 'bg-amber/35 text-navy', avatar: 'bg-amber/40 text-navy', node: 'fill-amber' },
  'Tokoh figuran': { chip: 'bg-sand text-muted', avatar: 'bg-sand text-muted', node: 'fill-lavender' },
}

export const RELATION_TYPES = {
  pasangan: { label: 'Pasangan', color: '#d6457a' },
  sahabat: { label: 'Sahabat', color: '#1f8a5b' },
  teman: { label: 'Teman', color: '#3f74c4' },
  keluarga: { label: 'Keluarga', color: '#b7791f' },
  musuh: { label: 'Musuh', color: '#c53030', dash: '7 5' },
  kenalan: { label: 'Kenalan', color: '#8a8f98', dash: '2 5' },
}
// nama lama sebelum jenis hubungan dirinci; tetap terbaca untuk buku yang belum dideteksi ulang
export const RELATION_ALIAS = { akrab: 'kenalan', konflik: 'musuh' }

export function relationType(type) {
  const key = RELATION_ALIAS[type] ?? type
  return { key, ...(RELATION_TYPES[key] ?? RELATION_TYPES.kenalan) }
}

export const UPCOMING = [
  { uc: 'UC-10', icon: 'lucide:contact-round', title: 'Biodata tokoh', tier: 'middle', action: 'Lihat tokoh', route: 'characters',
    desc: 'Daftar tokoh beserta peran (utama/pendukung) dan seberapa sering muncul.' },
  { uc: 'UC-11', icon: 'lucide:git-fork', title: 'Relasi antar tokoh', tier: 'middle', action: 'Lihat relasi', route: 'relations',
    desc: 'Peta hubungan tokoh (pasangan, sahabat, teman, keluarga, musuh) yang bisa dilihat per bab.' },
  { uc: 'UC-12', icon: 'lucide:sliders-horizontal', title: 'Profil sensitivitas', tier: 'high', action: 'Atur ambang batas', route: 'sensitivity',
    desc: 'Atur sendiri ambang batas Safe Mode untuk kekerasan, konten seksual, dan bahasa kasar.' },
]