<script setup>
import { useRoute } from 'vue-router'
import Header from '@/components/Header.vue'
import Footer from '@/components/Footer.vue'

const route = useRoute()
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