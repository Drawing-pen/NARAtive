<script setup>
import { ref } from 'vue'
import api, { errorMessage } from '@/lib/api'
import { hasTier } from '@/lib/auth'

const MAX_BYTES = 2 * 1024 * 1024

const props = defineProps({
  path: { type: String, required: true },
  hasPicture: { type: Boolean, default: false },
  label: { type: String, default: 'Ganti gambar' },
  compact: { type: Boolean, default: false },
})
const emit = defineEmits(['changed'])

const input = ref(null)
const busy = ref(false)
const error = ref('')

async function run(call) {
  busy.value = true
  error.value = ''
  try {
    await call()
    return true
  } catch (e) {
    error.value = errorMessage(e, 'Gagal menyimpan gambar. Coba lagi.')
    return false
  } finally {
    busy.value = false
  }
}

async function pick(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  if (file.size > MAX_BYTES) {
    error.value = 'Ukuran gambar maksimal 2 MB.'
    return
  }
  const form = new FormData()
  form.append('file', file)
  if (await run(() => api.put(props.path, form))) emit('changed', true)
}

async function reset() {
  if (await run(() => api.delete(props.path))) emit('changed', false)
}
</script>

<template>
  <div class="space-y-2">
    <RouterLink v-if="!hasTier('high')" :to="{ name: 'plans' }" class="btn btn-outline btn-sm w-full" title="Khusus High Tier">
      <Icon icon="lucide:lock" class="size-4" />
      <span v-if="!compact">{{ label }}</span>
    </RouterLink>
    <div v-else class="flex gap-2">
      <button type="button" class="btn btn-outline btn-sm flex-1" :disabled="busy" :aria-label="label" :title="label" @click="input.click()">
        <Icon :icon="busy ? 'lucide:loader-circle' : 'lucide:image-up'" class="size-4" :class="{ 'animate-spin': busy }" />
        <span v-if="!compact">{{ label }}</span>
      </button>
      <button
        v-if="hasPicture"
        type="button"
        class="btn btn-quiet btn-sm !px-2.5"
        :disabled="busy"
        aria-label="Kembalikan ke gambar bawaan"
        title="Kembalikan ke gambar bawaan"
        @click="reset"
      >
        <Icon icon="lucide:undo-2" class="size-4" />
      </button>
      <input ref="input" type="file" accept="image/jpeg,image/png,image/webp" class="hidden" @change="pick" />
    </div>
    <p v-if="error" role="alert" class="text-xs text-danger">{{ error }}</p>
  </div>
</template>
