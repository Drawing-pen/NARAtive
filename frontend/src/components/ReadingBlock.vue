<script setup>
import { computed } from 'vue'
import { renderMarkdown } from '@/lib/markdown'

const props = defineProps({
  paragraph: { type: Object, required: true },
  dropCap: { type: Boolean, default: false },
})

const html = computed(() => renderMarkdown(props.paragraph.markdown))
</script>

<template>
  <div v-if="paragraph.markdown" class="md-block" :class="[`md-${paragraph.kind ?? 'p'}`, { 'drop-cap': dropCap }]" v-html="html" />
  <p v-else class="whitespace-pre-line" :class="{ 'drop-cap': dropCap }">{{ paragraph.text }}</p>
</template>
