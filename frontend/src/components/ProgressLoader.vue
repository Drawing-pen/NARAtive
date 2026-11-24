<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  percent: { type: Number, default: null },
  title: { type: String, default: '' },
  detail: { type: String, default: '' },
  tips: { type: Array, default: () => [] },
  compact: { type: Boolean, default: false },
  icon: { type: String, default: 'lucide:book-open' },
})

const TIP_EVERY = 4000
const STEP_EVERY = 30

const target = computed(() => {
  if (props.percent === null || props.percent === undefined || Number.isNaN(Number(props.percent))) return null
  return Math.min(100, Math.max(0, Math.round(Number(props.percent))))
})
const fillStyle = computed(() => (target.value === null ? {} : { width: `${target.value}%` }))

const shown = ref(target.value ?? 0)
const tipIndex = ref(0)
let ease = null
let rotate = null

function reducedMotion() {
  return typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches
}

function stopEase() {
  if (ease !== null) clearInterval(ease)
  ease = null
}

watch(target, (to) => {
  stopEase()
  if (to === null) return
  if (reducedMotion() || shown.value === to) {
    shown.value = to
    return
  }
  ease = setInterval(() => {
    const diff = to - shown.value
    if (Math.abs(diff) < 1) {
      shown.value = to
      stopEase()
      return
    }
    shown.value += Math.sign(diff) * Math.max(1, Math.round(Math.abs(diff) * 0.25))
  }, STEP_EVERY)
})

onMounted(() => {
  if (props.tips.length > 1 && !props.compact) {
    rotate = setInterval(() => {
      tipIndex.value = (tipIndex.value + 1) % props.tips.length
    }, TIP_EVERY)
  }
})

onBeforeUnmount(() => {
  stopEase()
  if (rotate !== null) clearInterval(rotate)
})
</script>

<template>
  <div class="progress-loader" :class="compact ? 'is-compact space-y-1.5' : 'is-full grid w-full justify-items-center gap-4'">
    <Icon v-if="!compact" :icon="icon" class="pl-bob size-12 text-navy" />
    <p v-if="!compact && target !== null" data-test="percent" class="font-display text-5xl font-semibold text-navy tabular-nums">{{ shown }}%</p>
    <div v-if="!compact" class="space-y-1 text-center">
      <h2 class="text-2xl font-semibold">{{ title }}</h2>
      <p v-if="detail" class="mx-auto max-w-md text-sm text-muted">{{ detail }}</p>
    </div>
    <div class="flex w-full items-center gap-2" :class="compact ? '' : 'max-w-md'">
      <div class="pl-track" role="progressbar" :aria-label="title || 'Progres'" :aria-valuenow="target ?? undefined" aria-valuemin="0" aria-valuemax="100">
        <div data-test="fill" class="pl-fill" :class="{ 'is-indeterminate': target === null }" :style="fillStyle" />
      </div>
      <span v-if="compact && target !== null" data-test="percent" class="w-9 shrink-0 text-right text-xs font-semibold text-navy tabular-nums">{{ shown }}%</span>
    </div>
    <p v-if="compact && detail" class="text-xs text-muted">{{ detail }}</p>
    <p v-if="!compact && tips.length" data-test="tip" class="max-w-md text-xs text-muted">{{ tips[tipIndex % tips.length] }}</p>
  </div>
</template>

<style scoped>
.pl-track {
  position: relative;
  flex: 1;
  height: 0.75rem;
  overflow: hidden;
  border-radius: 999px;
  background: var(--color-sand);
  box-shadow: inset 0 1px 2px rgb(36 54 95 / 0.18);
}
.is-compact .pl-track {
  height: 0.5rem;
}
.pl-fill {
  position: relative;
  height: 100%;
  overflow: hidden;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--color-amber), #f7d28f);
  transition: width 0.7s cubic-bezier(0.22, 1, 0.36, 1);
}
.pl-fill::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(110deg, transparent 30%, rgb(255 255 255 / 0.6) 50%, transparent 70%);
  transform: translateX(-100%);
  animation: pl-shine 1.8s linear infinite;
}
.pl-fill.is-indeterminate {
  width: 40%;
  animation: pl-slide 1.3s ease-in-out infinite alternate;
}
.pl-bob {
  animation: pl-bob 1.6s ease-in-out infinite;
}
@keyframes pl-shine {
  to {
    transform: translateX(100%);
  }
}
@keyframes pl-slide {
  from {
    margin-left: 0;
  }
  to {
    margin-left: 60%;
  }
}
@keyframes pl-bob {
  50% {
    transform: translateY(-5px);
  }
}
@media (prefers-reduced-motion: reduce) {
  .pl-fill::before,
  .pl-fill.is-indeterminate,
  .pl-bob {
    animation: none;
  }
  .pl-fill {
    transition: none;
  }
}
</style>
