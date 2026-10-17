<template>
    <section class="container-page grid place-items-center py-24 text-center">
      <div class="space-y-4">
        <Icon icon="lucide:book-x" class="mx-auto size-12 text-lavender" />
        <h1 class="text-3xl font-semibold">Halaman tidak ditemukan</h1>
        <p class="text-muted">Lembar yang kamu cari tidak ada di koleksi ini.</p>
        <RouterLink :to="{ name: 'library' }" class="btn btn-primary">Kembali ke koleksi</RouterLink>
      </div>
    </section>
  </template>  