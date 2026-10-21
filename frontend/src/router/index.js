import { createRouter, createWebHistory } from 'vue-router'
import { isLoggedIn } from '@/lib/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  scrollBehavior: () => ({ top: 0 }),
  routes: [
    // Situs: Beranda, Koleksi, Berlangganan
    { path: '/', name: 'home', component: () => import('@/pages/HomePage.vue') },
    { path: '/koleksi', name: 'library', component: () => import('@/pages/KoleksiPage.vue'), meta: { requiresAuth: true } },
    { path: '/berlangganan', name: 'plans', component: () => import('@/pages/BerlanggananPage.vue') },

    { path: '/masuk', name: 'login', component: () => import('@/pages/AuthPage.vue'), props: { mode: 'masuk' }, meta: { bare: true, guest: true } },
    { path: '/daftar', name: 'register', component: () => import('@/pages/AuthPage.vue'), props: { mode: 'daftar' }, meta: { bare: true, guest: true } },

    // Ruang kerja satu buku
    {
      path: '/buku/:id',
      component: () => import('@/pages/Sidebar.vue'),
      props: true,
      meta: { bare: true, requiresAuth: true },
      children: [
        { path: '', name: 'document', component: () => import('@/pages/HasilAnalisisPage.vue'), props: true },
        { path: 'baca', name: 'reader', component: () => import('@/pages/ReadingModePage.vue'), props: true },
        { path: 'rangkuman', name: 'summary', component: () => import('@/pages/SummaryPage.vue'), props: true },
        { path: 'tokoh', name: 'characters', component: () => import('@/pages/TokohPage.vue'), props: true },
        { path: 'relasi', name: 'relations', component: () => import('@/pages/RelasiPage.vue'), props: true },
      ],
    },
    { path: '/dokumen/:id', redirect: (to) => `/buku/${to.params.id}` },
    { path: '/dokumen/:id/baca', redirect: (to) => `/buku/${to.params.id}/baca` },

    { path: '/:pathMatch(.*)*', name: 'not-found', component: () => import('@/pages/NotFoundPage.vue') },
  ],
})

router.beforeEach((to) => {
  if (to.matched.some((r) => r.meta.requiresAuth) && !isLoggedIn()) {
    return { name: 'login', query: { next: to.fullPath } }
  }
  if (to.meta.guest && isLoggedIn()) return { name: 'library' }
})

export default router