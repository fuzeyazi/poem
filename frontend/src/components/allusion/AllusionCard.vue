<template>
  <div class="allusion-card" v-if="allusion">
    <!-- 头部：词条、拼音、时代/意象标签与朱砂小印 -->
    <div class="card-head">
      <div class="head-left">
        <div class="title-row">
          <span class="allusion-title">{{ allusion.name }}</span>
          <span v-if="allusion.pinyin" class="allusion-pinyin">{{ allusion.pinyin }}</span>
        </div>
        <div class="meta-row">
          <span v-if="allusion.dynasty" class="tag dynasty-tag">{{ allusion.dynasty }}</span>
          <span v-if="allusion.sentiment" class="tag sentiment-tag">{{ allusion.sentiment }}</span>
        </div>
      </div>
      <div class="seal-mark" title="文化典故">典</div>
    </div>

    <!-- 出处溯源 -->
    <div class="card-section">
      <div class="section-label">出处溯源</div>
      <div class="origin-box">
        <div class="origin-source">{{ allusion.origin }}</div>
        <div v-if="allusion.originQuote" class="origin-quote">
          “{{ allusion.originQuote }}”
        </div>
      </div>
    </div>

    <!-- 源流释义 -->
    <div class="card-section">
      <div class="section-label">源流释义</div>
      <p class="story-text">{{ allusion.story }}</p>
    </div>

    <!-- 延伸诗境 -->
    <div v-if="parsedQuotes.length > 0" class="card-section quotes-section">
      <div class="section-label">延伸诗境</div>
      <ul class="quote-list">
        <li v-for="(q, idx) in parsedQuotes" :key="idx" class="quote-item">
          <span class="quote-bullet">✦</span>
          <span class="quote-content">{{ q }}</span>
        </li>
      </ul>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Allusion } from '@/utils/allusionSeed'

const props = defineProps<{
  allusion: Allusion
}>()

const parsedQuotes = computed(() => {
  if (!props.allusion?.relatedQuotes) return []
  return props.allusion.relatedQuotes
    .split('\n')
    .map(s => s.trim())
    .filter(Boolean)
})
</script>

<style scoped>
.allusion-card {
  max-width: 360px;
  background: var(--paper-card, #161d29);
  color: var(--ink-900, #f0e9d8);
  font-family: var(--f-sans, sans-serif);
  padding: 18px 20px 16px;
  border-radius: 6px;
  box-shadow: var(--shadow-md, 0 6px 20px rgba(0, 0, 0, 0.4));
  line-height: 1.6;
  text-align: left;
  user-select: text;
}

.card-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--line-strong, rgba(143, 163, 189, 0.34));
  margin-bottom: 12px;
}

.title-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.allusion-title {
  font-family: var(--f-serif, serif);
  font-size: 20px;
  font-weight: 700;
  letter-spacing: 2px;
  color: var(--ink-900, #f0e9d8);
}

.allusion-pinyin {
  font-size: 12px;
  color: var(--gold, #c9a86a);
  font-family: var(--f-sans, sans-serif);
  letter-spacing: 0.5px;
}

.meta-row {
  display: flex;
  gap: 6px;
  margin-top: 6px;
}

.tag {
  font-size: 11px;
  padding: 1px 7px;
  border-radius: 3px;
  letter-spacing: 1px;
}

.dynasty-tag {
  background: rgba(143, 163, 189, 0.12);
  color: var(--ink-500, #8fa3bd);
  border: 1px solid var(--line, rgba(143, 163, 189, 0.16));
}

.sentiment-tag {
  background: rgba(201, 168, 106, 0.12);
  color: var(--gold, #c9a86a);
  border: 1px solid rgba(201, 168, 106, 0.28);
}

.seal-mark {
  width: 26px;
  height: 26px;
  background: var(--cinnabar, #b03a2a);
  color: #f6efdc;
  font-family: var(--f-serif, serif);
  font-size: 14px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 2px;
  box-shadow: 0 0 0 1.5px rgba(176, 58, 42, 0.3);
  flex-shrink: 0;
  user-select: none;
}

.card-section {
  margin-top: 10px;
}

.section-label {
  font-size: 11px;
  letter-spacing: 2px;
  color: var(--gold, #c9a86a);
  font-weight: 500;
  margin-bottom: 5px;
  text-transform: uppercase;
}

.origin-box {
  background: rgba(20, 26, 36, 0.6);
  border-left: 2px solid var(--gold, #c9a86a);
  padding: 6px 10px;
  border-radius: 0 4px 4px 0;
}

.origin-source {
  font-size: 12px;
  font-weight: 600;
  color: var(--ink-900, #f0e9d8);
  font-family: var(--f-serif, serif);
}

.origin-quote {
  font-size: 12px;
  color: var(--ink-700, #cfc9b8);
  margin-top: 4px;
  font-style: italic;
  line-height: 1.5;
}

.story-text {
  font-size: 13px;
  color: var(--ink-700, #cfc9b8);
  line-height: 1.8;
  margin: 0;
  text-align: justify;
}

.quotes-section {
  padding-top: 8px;
  border-top: 1px dashed var(--line, rgba(143, 163, 189, 0.16));
}

.quote-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.quote-item {
  display: flex;
  align-items: baseline;
  gap: 6px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--ink-700, #cfc9b8);
}

.quote-bullet {
  color: var(--gold, #c9a86a);
  font-size: 9px;
  flex-shrink: 0;
}

.quote-content {
  font-family: var(--f-serif, serif);
}
</style>
