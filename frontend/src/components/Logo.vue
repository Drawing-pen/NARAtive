<script setup>
import { computed } from 'vue'
import logo from '@/assets/logo.png'
import logoLight from '@/assets/logo-light.png'
import logoOnly from '@/assets/logo-only.png'
import logoLightOnly from '@/assets/logo-light-only.png'

const props = defineProps({ light: Boolean, mark: Boolean })

const source = computed(() => {
  if (props.mark) return props.light ? logoLightOnly : logoOnly
  return props.light ? logoLight : logo
})
const size = computed(() => {
  if (props.mark) return props.light ? [411, 370] : [675, 592]
  return props.light ? [1200, 370] : [1921, 592]
})
const height = computed(() => {
  if (props.mark) return 'h-20 sm:h-24'
  return props.light ? 'h-20 sm:h-24' : 'h-10 sm:h-12'
})
</script>

<template>
  <img
    :src="source"
    alt="NARAtive, Narrative Analysis & Rating Assistant"
    class="block w-auto"
    :class="height"
    :width="size[0]"
    :height="size[1]"
  />
</template>
