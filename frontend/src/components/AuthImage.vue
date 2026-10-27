<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import api from '@/lib/api'

const props = defineProps({
  path: { type: String, required: true },
  active: { type: Boolean, default: true },
  version: { type: [Number, String], default: 0 },
  alt: { type: String, default: '' },
})

const src = ref('')
let current = ''

function clear() {
  if (current) URL.revokeObjectURL(current)
  current = ''
  src.value = ''
}

async function load() {
  if (!props.active) return clear()
  try {
    const { data } = await api.get(props.path, { responseType: 'blob' })
    clear()
    current = URL.createObjectURL(data)
    src.value = current
  } catch {
    clear()
  }
}

watch(() => [props.path, props.active, props.version], load, { immediate: true })
onBeforeUnmount(clear)
</script>

<template>
  <img v-if="src" :src="src" :alt="alt" class="size-full object-cover" />
  <slot v-else />
</template>
