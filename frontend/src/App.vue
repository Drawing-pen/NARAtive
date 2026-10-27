<script setup>
import { onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { refreshUser } from '@/lib/auth'
import Header from '@/components/Header.vue'
import Footer from '@/components/Footer.vue'

const route = useRoute()
onMounted(refreshUser)
</script>

<template>
  <div class="flex min-h-screen flex-col">
    <Header v-if="!route.meta.bare" />
    <main class="flex-1">
      <RouterView />
    </main>
    <Footer v-if="!route.meta.bare" />
  </div>
</template>