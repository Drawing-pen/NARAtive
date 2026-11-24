<script setup>
import { onMounted, ref } from 'vue'
import api, { errorMessage } from '@/lib/api'
import { formatDateTime, rupiah } from '@/lib/content'
import Logo from '@/components/Logo.vue'

const props = defineProps({ orderId: { type: String, required: true } })

const invoice = ref(null)
const loading = ref(true)
const missing = ref(false)
const blocked = ref('')
const failed = ref(false)
const downloading = ref(false)
const downloadError = ref('')

async function load() {
  loading.value = true
  missing.value = false
  blocked.value = ''
  failed.value = false
  try {
    invoice.value = (await api.get(`/billing/transactions/${props.orderId}/invoice`)).data
  } catch (e) {
    invoice.value = null
    if (e.response?.status === 404) missing.value = true
    else if (e.response?.status === 409) blocked.value = errorMessage(e, 'Invoice hanya tersedia untuk pembayaran yang berhasil.')
    else failed.value = true
  } finally {
    loading.value = false
  }
}

async function download() {
  downloading.value = true
  downloadError.value = ''
  try {
    const { data } = await api.get(`/billing/transactions/${props.orderId}/invoice.pdf`, { responseType: 'blob' })
    const url = URL.createObjectURL(data)
    const link = document.createElement('a')
    link.href = url
    link.download = `Invoice NARAtive ${props.orderId}.pdf`
    document.body.appendChild(link)
    link.click()
    link.remove()
    setTimeout(() => URL.revokeObjectURL(url), 0)
  } catch {
    downloadError.value = 'Gagal mengunduh invoice.'
  } finally {
    downloading.value = false
  }
}

onMounted(load)
</script>

<template>
  <main class="container-page space-y-6 py-10">
    <div v-if="loading" class="card grid place-items-center gap-3 px-6 py-16 text-center">
      <Icon icon="lucide:loader-circle" class="size-8 animate-spin text-navy" />
      <p class="text-sm text-muted">Memuat invoice…</p>
    </div>

    <div v-else-if="missing" class="card grid place-items-center gap-3 px-6 py-16 text-center">
      <Icon icon="lucide:file-question" class="size-10 text-lavender" />
      <h1 class="text-2xl font-semibold">Invoice tidak ditemukan</h1>
      <RouterLink :to="{ name: 'profile', hash: '#riwayat' }" class="btn btn-primary btn-sm">Kembali ke riwayat</RouterLink>
    </div>

    <div v-else-if="blocked" class="card grid place-items-center gap-3 px-6 py-16 text-center">
      <Icon icon="lucide:file-clock" class="size-10 text-lavender" />
      <p class="max-w-md text-sm text-muted">{{ blocked }}</p>
      <RouterLink :to="{ name: 'profile', hash: '#riwayat' }" class="btn btn-primary btn-sm">Kembali ke riwayat</RouterLink>
    </div>

    <div v-else-if="failed" class="card grid place-items-center gap-3 px-6 py-16 text-center">
      <Icon icon="lucide:circle-x" class="size-10 text-danger" />
      <h1 class="text-2xl font-semibold">Gagal memuat invoice</h1>
      <button type="button" class="btn btn-primary btn-sm" @click="load">Coba lagi</button>
    </div>

    <template v-else-if="invoice">
      <article class="card mx-auto max-w-3xl space-y-8 p-6 sm:p-10">
        <header class="flex flex-wrap items-start justify-between gap-4 border-b border-line pb-6">
          <div class="space-y-1">
            <Logo />
            <p class="text-xs text-muted">Analisis rating konten e-book</p>
          </div>
          <div class="space-y-2 text-right">
            <h1 class="font-display text-3xl font-semibold text-navy">INVOICE</h1>
            <span class="chip bg-emerald-50 text-emerald-700">TERBAYAR</span>
          </div>
        </header>

        <section class="grid gap-6 sm:grid-cols-2">
          <div class="space-y-1">
            <p class="eyebrow">Ditagihkan kepada</p>
            <p class="text-lg font-semibold break-words text-navy">{{ invoice.customer_name }}</p>
            <p class="text-sm break-all text-muted">Email : {{ invoice.customer_email }}</p>
          </div>
          <dl class="space-y-2 rounded-xl border border-line bg-paper p-4 text-sm">
            <div class="flex justify-between gap-3">
              <dt class="text-muted">No. Invoice</dt>
              <dd class="font-semibold break-all text-navy">{{ invoice.number }}</dd>
            </div>
            <div class="flex justify-between gap-3">
              <dt class="text-muted">Tanggal Invoice</dt>
              <dd class="font-semibold text-navy">{{ formatDateTime(invoice.issued_at) }}</dd>
            </div>
            <div class="flex justify-between gap-3">
              <dt class="text-muted">Batas Pembayaran</dt>
              <dd class="font-semibold text-navy">{{ formatDateTime(invoice.due_at) }}</dd>
            </div>
            <div class="flex justify-between gap-3 border-t border-line pt-2">
              <dt class="text-muted">Tanggal Terbayar</dt>
              <dd class="font-semibold text-emerald-700">{{ formatDateTime(invoice.paid_at) }}</dd>
            </div>
          </dl>
        </section>

        <section class="space-y-2">
          <p class="eyebrow">Informasi pembayaran</p>
          <p class="rounded-xl border border-line px-5 py-4 text-lg font-semibold text-navy">{{ invoice.method }}</p>
        </section>

        <section class="overflow-x-auto">
          <table class="w-full min-w-[30rem] text-sm">
            <thead>
              <tr class="border-b border-line text-left text-[11px] font-semibold tracking-wider text-muted uppercase">
                <th class="py-2 pr-3">No</th>
                <th class="py-2 pr-3">Item</th>
                <th class="py-2 pr-3 text-right">Harga satuan</th>
                <th class="py-2 pr-3 text-right">Jumlah</th>
                <th class="py-2 text-right">Total</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in invoice.items" :key="item.no" data-test="item" class="border-b border-line">
                <td class="py-3 pr-3">{{ item.no }}</td>
                <td class="py-3 pr-3 font-semibold text-navy">{{ item.name }}</td>
                <td class="py-3 pr-3 text-right tabular-nums">{{ rupiah(item.unit_price) }}</td>
                <td class="py-3 pr-3 text-right tabular-nums">{{ item.quantity }}</td>
                <td class="py-3 text-right tabular-nums">{{ rupiah(item.total) }}</td>
              </tr>
            </tbody>
          </table>
        </section>

        <section class="ml-auto w-full max-w-xs space-y-2 text-sm">
          <div data-test="subtotal" class="flex justify-between gap-3">
            <span class="text-muted">Subtotal Item</span>
            <span class="tabular-nums">{{ rupiah(invoice.subtotal) }}</span>
          </div>
          <div data-test="total" class="flex justify-between gap-3 border-t border-line pt-2">
            <span class="font-semibold text-navy">Total Bayar</span>
            <span class="text-base font-semibold text-danger tabular-nums">{{ rupiah(invoice.total) }}</span>
          </div>
        </section>
      </article>

      <div class="mx-auto flex max-w-3xl flex-wrap items-center gap-3">
        <button type="button" class="btn btn-primary" :disabled="downloading" @click="download">
          <Icon :icon="downloading ? 'lucide:loader-circle' : 'lucide:download'" class="size-4.5" :class="{ 'animate-spin': downloading }" />
          Unduh PDF
        </button>
        <RouterLink :to="{ name: 'profile', hash: '#riwayat' }" class="btn btn-outline">Kembali ke riwayat</RouterLink>
        <p v-if="downloadError" role="alert" class="w-full rounded-lg bg-danger/10 px-3 py-2.5 text-sm text-danger">{{ downloadError }}</p>
      </div>
    </template>
  </main>
</template>
