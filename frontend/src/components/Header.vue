<script setup>
import Logo from '@/components/Logo.vue'
import SoonButton from '@/components/SoonButton.vue'
import TierChip from '@/components/TierChip.vue'

const nav = [
  { name: 'home', label: 'Beranda' },
  { name: 'library', label: 'Koleksi' },
  { name: 'plans', label: 'Berlangganan' },
]
</script>

<template>
  <header class="sticky top-0 z-30 border-b border-line bg-paper/85 backdrop-blur">
    <div class="container-page flex flex-wrap items-center justify-between gap-x-4 gap-y-1 py-3">
      <div class="contents md:flex md:min-w-0 md:items-center md:gap-8">
        <RouterLink :to="{ name: 'home' }" aria-label="NARAtive, ke beranda" class="shrink-0">
          <Logo />
        </RouterLink>
        <nav class="order-last flex w-full items-center justify-around border-t border-line/70 pt-1 md:order-none md:w-auto md:justify-start md:gap-6 md:border-0 md:pt-0" aria-label="Menu utama">
          <RouterLink
            v-for="item in nav"
            :key="item.name"
            :to="{ name: item.name }"
            class="relative px-1 py-2 text-[15px] font-semibold text-muted transition hover:text-navy after:absolute after:inset-x-0 after:-bottom-px after:h-0.5 after:scale-x-0 after:bg-amber after:transition aria-[current=page]:text-navy aria-[current=page]:after:scale-x-100"
          >
            {{ item.label }}
          </RouterLink>
        </nav>
      </div>

      <div class="flex shrink-0 items-center gap-2">
        <TierChip tier="standard" class="hidden lg:inline-flex" />
        <SoonButton variant="outline" small>Masuk</SoonButton>
        <SoonButton variant="primary" small class="hidden sm:inline-flex">Daftar</SoonButton>
      </div>
    </div>
  </header>
</template>