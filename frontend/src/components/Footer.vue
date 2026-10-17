<script setup>
import Logo from '@/components/Logo.vue'
</script>

<template>
  <footer class="mt-16 bg-navy text-white/80">
    <div class="container-page flex flex-col gap-6 py-10 sm:flex-row sm:items-center sm:justify-between">
      <div class="space-y-3">
        <Logo light />
        <p class="max-w-sm text-sm text-white/60">
          Sistem penilaian konten dan eksplorasi naratif e-book berbasis pemrosesan bahasa alami.
        </p>
      </div>
      <nav class="flex gap-6 text-sm font-semibold" aria-label="Tautan footer">
        <RouterLink :to="{ name: 'home' }" class="transition hover:text-amber">Beranda</RouterLink>
        <RouterLink :to="{ name: 'library' }" class="transition hover:text-amber">Koleksi</RouterLink>
        <RouterLink :to="{ name: 'plans' }" class="transition hover:text-amber">Berlangganan</RouterLink>
      </nav>
    </div>
    <div class="border-t border-white/10">
      <p class="container-page py-4 text-xs text-white/50">
        © 2026 NARAtive · Proyek IPPL, Informatika Institut Teknologi Kalimantan
      </p>
    </div>
  </footer>
</template>