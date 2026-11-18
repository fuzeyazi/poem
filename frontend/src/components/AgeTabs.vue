<script setup lang="ts">
const props = defineProps<{ dynasties: string[]; modelValue: string }>()
const emit = defineEmits<{ 'update:modelValue': [string]; change: [string] }>()
const pick = (dynasty: string) => { emit('update:modelValue', dynasty); emit('change', dynasty) }
</script>

<template>
  <div class="age" role="group" aria-label="朝代筛选">
    <button class="at" type="button" :class="{ on: !props.modelValue }" :aria-pressed="!props.modelValue" @click="pick('')">全部</button>
    <button v-for="dynasty in props.dynasties" :key="dynasty" class="at" type="button" :class="{ on: props.modelValue === dynasty }" :aria-pressed="props.modelValue === dynasty" @click="pick(dynasty)">{{ dynasty }}</button>
  </div>
</template>

<style scoped>
.age { display: flex; flex-wrap: wrap; gap: 8px; }
.at { min-height: 44px; padding: 8px 16px; border-radius: 999px; cursor: pointer; font: inherit; font-size: 14px; color: var(--md-on-surface-variant); background: var(--md-surface); border: 1px solid var(--md-outline); transition: background 150ms; }
.at:hover { background: var(--md-surface-container); }.at.on { color: var(--md-on-primary-container); background: var(--md-primary-container); border-color: var(--md-primary); }.at:focus-visible { outline: 3px solid var(--md-primary); outline-offset: 3px; }
@media (prefers-reduced-motion: reduce) { .at { transition: none; } }
</style>
