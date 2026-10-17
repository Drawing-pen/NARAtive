// Label dan aturan tampilan untuk hasil analisis.
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

// Ambang standar Safe Mode (sama dengan THRESHOLDS di backend app/ml/analyzer.py).
// Pengguna Free dan Middle memakai ambang ini; High User boleh mengatur sendiri per dimensi (UC-12).
export const STANDARD_THRESHOLDS = { profanity: 0.5, sexual: 0.5, violence: 0.8 }

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

export const num = (n) => (n === null || n === undefined ? '-' : String(n).replace('.', ','))

// Tingkatan akun (SRS): Standard (Free), Middle, High.
export const TIERS = {
  standard: { label: 'Standard', cls: 'bg-sand text-navy', icon: 'lucide:user' },
  middle: { label: 'Middle', cls: 'bg-lavender/25 text-navy', icon: 'lucide:lock' },
  high: { label: 'High', cls: 'bg-amber/40 text-navy', icon: 'lucide:lock' },
}

// Fitur lanjutan yang belum dibangun (tampilan saja). Nama dan deskripsi mengikuti use case SRS.
export const UPCOMING = [
  { uc: 'UC-10', icon: 'lucide:contact-round', title: 'Biodata tokoh', tier: 'middle', action: 'Lihat tokoh',
    desc: 'Daftar tokoh beserta peran (utama/pendukung) dan seberapa sering muncul.' },
  { uc: 'UC-11', icon: 'lucide:git-fork', title: 'Relasi antar tokoh', tier: 'middle', action: 'Lihat relasi',
    desc: 'Peta hubungan tokoh (akrab/konflik) yang bisa dilihat per bab.' },
  { uc: 'UC-12', icon: 'lucide:sliders-horizontal', title: 'Profil sensitivitas', tier: 'high', action: 'Atur ambang batas',
    desc: 'Atur sendiri ambang batas Safe Mode untuk kekerasan, konten seksual, dan bahasa kasar.' },
]