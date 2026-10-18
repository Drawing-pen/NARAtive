<script setup>
import { onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/lib/api'
import WorkspaceNav from '@/components/WorkspaceNav.vue'

const props = defineProps({ id: { type: String, required: true } })

const doc = ref(null)
const open = ref(false)   

async function loadDoc() {
  try {
    doc.value = (await api.get(`/documents/${props.id}`)).data
  } catch {
    doc.value = null   
  }
}
const route = useRoute()
onMounted(loadDoc)
watch(() => route.fullPath, loadDoc)   
</script>

<template>
  <div class="min-h-screen lg:grid lg:grid-cols-[19rem_1fr]">
    <!-- Sidebar desktop -->
    <aside class="sticky top-0 hidden h-screen border-r border-line bg-white lg:block">
      <WorkspaceNav :id="id" :doc="doc" />
    </aside>

    <!-- Bilah atas -->
    <div class="flex items-center gap-3 border-b border-line bg-white px-4 py-3 lg:hidden">
      <button class="btn btn-quiet btn-sm !px-2.5" aria-label="Buka menu buku" @click="open = true">
        <Icon icon="lucide:menu" class="size-5" />
      </button>
      <p class="min-w-0 flex-1 truncate font-display text-base font-semibold text-navy">{{ doc?.title ?? 'Buku' }}</p>
      <RouterLink :to="{ name: 'library' }" class="btn btn-outline btn-sm">
        <Icon icon="lucide:arrow-left" class="size-4" />
        Website
      </RouterLink>
    </div>
    <div v-if="open" class="fixed inset-0 z-50 lg:hidden">
      <div class="absolute inset-0 bg-navy-deep/50" @click="open = false" />
      <aside class="absolute inset-y-0 left-0 w-72 max-w-[85%] bg-white shadow-xl">
        <button class="absolute top-3 right-3 grid size-8 place-items-center rounded-lg text-muted hover:bg-sand" aria-label="Tutup menu" @click="open = false">
          <Icon icon="lucide:x" class="size-5" />
        </button>
        <WorkspaceNav :id="id" :doc="doc" @navigate="open = false" />
      </aside>
    </div>

    <main class="min-w-0">
      <RouterView :key="id" />
    </main>
  </div>
</template>