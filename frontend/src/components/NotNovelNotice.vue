<script setup>
defineProps({
  id: { type: String, default: '' },
  link: { type: Boolean, default: true },
})
</script>

<template>
  <section role="status" class="card grid place-items-center gap-3 px-6 py-14 text-center">
    <Icon icon="lucide:file-text" class="size-12 text-lavender" />
    <h2 class="text-2xl font-semibold">Dokumen ini bukan novel</h2>
    <p class="max-w-md text-sm text-muted">
      NARAtive menilai rating konten untuk novel dan buku bercerita, jadi dokumen seperti artikel, makalah, atau catatan tidak dianalisis. Kuota analisismu tidak terpakai.
    </p>
    <RouterLink v-if="link" :to="{ name: 'document', params: { id } }" class="btn btn-primary btn-sm">Lihat hasil analisis</RouterLink>
  </section>
</template>
