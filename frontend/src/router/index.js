import { createRouter, createWebHistory } from 'vue-router'

export default createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  scrollBehavior: () => ({ top: 0 }),
  routes: [
    // Situs: Beranda, Koleksi, Berlangganan
    { path: '/', name: 'home', component: () => import('@/pages/HomePage.vue') },
    { path: '/koleksi', name: 'library', component: () => import('@/pages/KoleksiPage.vue') },
    { path: '/berlangganan', name: 'plans', component: () => import('@/pages/BerlanggananPage.vue') },

    // Ruang kerja satu buku: sidebar + hasil analisis / mode baca (tanpa header dan footer situs)
    {
      path: '/buku/:id',
      component: () => import('@/pages/Sidebar.vue'),
      props: true,
      meta: { bare: true },
      children: [
        { path: '', name: 'document', component: () => import('@/pages/HasilAnalisisPage.vue'), props: true },
        { path: 'baca', name: 'reader', component: () => import('@/pages/ReadingModePage.vue'), props: true },
        { path: 'rangkuman', name: 'summary', component: () => import('@/pages/SummaryPage.vue'), props: true },
      ],
    },
    { path: '/dokumen/:id', redirect: (to) => `/buku/${to.params.id}` },
    { path: '/dokumen/:id/baca', redirect: (to) => `/buku/${to.params.id}/baca` },

    { path: '/:pathMatch(.*)*', name: 'not-found', component: () => import('@/pages/NotFoundPage.vue') },
  ],
})