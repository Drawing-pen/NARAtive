<script setup>
import logo from '@/assets/logo.png'
import logoLight from '@/assets/logo-light.png'

// light = versi putih untuk latar gelap (footer)
defineProps({ light: Boolean })
</script>

<template>
  <img
    :src="light ? logoLight : logo"
    alt="NARAtive, Narrative Analysis & Rating Assistant"
    class="block w-auto"
    :class="light ? 'h-20 sm:h-24' : 'h-14 -my-2 sm:h-16 sm:-my-3'"
    width="1200"
    height="370"
  />
</template>