<template>
  <div
    ref="cardRoot"
    class="poem-card-container"
    :class="[`theme-${theme}`, { 'is-traditional': traditional }]"
  >
    <!-- 宣纸纤维底纹 (仅在澄素宣纸/朱丝阑格生效) -->
    <div v-if="theme !== 'dark'" class="paper-texture-layer" />

    <!-- 仿古双线外框 -->
    <div class="card-border-outer">
      <div class="card-border-inner">
        <!-- 竖排主体内容区域 (自右向左 reading flow) -->
        <div class="card-flow-body">
          <!-- 1. 诗题列 (最右列) -->
          <div class="flow-column title-column">
            <h2 class="poem-title">{{ displayTitle }}</h2>
            <span v-if="poem.type" class="poem-type-tag">{{ displayType }}</span>
          </div>

          <!-- 2. 正文诗句列 (自右向左逐列排列) -->
          <div
            v-for="(line, idx) in verseColumns"
            :key="idx"
            class="flow-column verse-column"
          >
            <div class="verse-chars">{{ line }}</div>
          </div>

          <!-- 3. 落款与款识列 (左侧末列，下沉对齐) -->
          <div class="flow-column colophon-column">
            <div class="colophon-text-wrapper">
              <span class="colophon-line">{{ displayColophon }}</span>
              <span v-if="userDedication" class="colophon-sub">
                {{ userDedication }}
              </span>
            </div>

            <!-- 印章区 (置于落款下方) -->
            <div class="seals-group">
              <!-- 作者印 (默认方印阳刻) -->
              <ClassicalSeal
                v-if="showAuthorSeal && authorSealText"
                :text="authorSealText"
                :size="sealSize"
                :shape="authorSealShape"
                :carving="authorSealCarving"
                :traditional="traditional"
                :paper-color="themePaperColor"
                :cinnabar-color="themeCinnabarColor"
              />

              <!-- 用户藏书/鉴赏印 (由控制台动态配置) -->
              <ClassicalSeal
                v-if="showUserSeal && cleanUserSealText"
                :text="cleanUserSealText"
                :size="sealSize"
                :shape="userSealShape"
                :carving="userSealCarving"
                :traditional="traditional"
                :paper-color="themePaperColor"
                :cinnabar-color="themeCinnabarColor"
              />
            </div>
          </div>
        </div>

        <!-- 卡片角落古典雅致水印/标语 -->
        <div class="card-bottom-imprint">
          <span>诗境 · 东方雅集</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import ClassicalSeal from './ClassicalSeal.vue'
import { toTraditional, stripPunctuation, splitVerseColumns } from '@/utils/s2tDict'

export interface PoemCardData {
  title: string
  dynasty?: string
  writer: string
  type?: string
  content: string
}

export interface PoemCardProps {
  poem: PoemCardData
  theme?: 'xuan' | 'dark' | 'grid' // 澄素宣纸 | 墨夜泥金 | 朱丝阑格
  removePunctuation?: boolean
  traditional?: boolean
  userSealText?: string
  userSealShape?: 'square' | 'oval' | 'round'
  userSealCarving?: 'yang' | 'yin'
  showAuthorSeal?: boolean
  showUserSeal?: boolean
  sealSize?: number
}

const props = withDefaults(defineProps<PoemCardProps>(), {
  theme: 'xuan',
  removePunctuation: false,
  traditional: true,
  userSealText: '雅赏',
  userSealShape: 'square',
  userSealCarving: 'yin',
  showAuthorSeal: true,
  showUserSeal: true,
  sealSize: 46
})

const cardRoot = ref<HTMLElement | null>(null)

// 转换文字辅助函数
const transformText = (text?: string): string => {
  if (!text) return ''
  let res = text
  if (props.removePunctuation) {
    res = stripPunctuation(res)
  }
  if (props.traditional) {
    res = toTraditional(res)
  }
  return res
}

// 诗题
const displayTitle = computed(() => {
  return transformText(props.poem.title || '无题')
})

// 体裁（如 五言律诗 / 词）
const displayType = computed(() => {
  return transformText(props.poem.type || '')
})

// 正文多列竖排拆分
const verseColumns = computed(() => {
  return splitVerseColumns(
    props.poem.content || '',
    props.removePunctuation,
    props.traditional
  )
})

// 默认作者印文本（提取作者前 2~4 字，如“太白”、“李白印”）
const authorSealText = computed(() => {
  const writer = (props.poem.writer || '墨客').replace(/[\[\]（）()·\s]/g, '')
  if (writer.length <= 2) {
    return `${writer}印`
  }
  return writer.slice(0, 4)
})

const authorSealShape = computed<'square' | 'oval' | 'round'>(() => 'square')
const authorSealCarving = computed<'yang' | 'yin'>(() => 'yang')

// 用户自定义印文本
const cleanUserSealText = computed(() => {
  const t = (props.userSealText || '').trim().replace(/[\[\]（）()·\s]/g, '')
  return t ? t.slice(0, 4) : ''
})

// 落款文字（如：“唐·李白 诗” 或 “宋·苏轼 词”）
const displayColophon = computed(() => {
  const dynasty = props.poem.dynasty ? `${props.poem.dynasty}·` : ''
  const writer = props.poem.writer || '佚名'
  const genre = props.poem.type?.includes('词') ? '词' : '诗'
  const raw = `${dynasty}${writer} ${genre}`
  return props.traditional ? toTraditional(raw) : raw
})

// 用户品鉴小款
const userDedication = computed(() => {
  if (!cleanUserSealText.value) return ''
  const raw = `岁次有嘉·${cleanUserSealText.value}`
  return props.traditional ? toTraditional(raw) : raw
})

// 主题对应的底色与朱砂色（传递给印章）
const themePaperColor = computed(() => {
  if (props.theme === 'dark') return '#111622'
  if (props.theme === 'grid') return '#f9f6ed'
  return '#f7f4ec'
})

const themeCinnabarColor = computed(() => {
  if (props.theme === 'dark') return '#b83b2a'
  return '#a93226'
})

defineExpose({
  cardRoot
})
</script>

<style scoped>
.poem-card-container {
  position: relative;
  width: 480px;
  min-height: 580px;
  max-width: 100%;
  box-sizing: border-box;
  padding: 24px;
  font-family: "Noto Serif SC", "Songti SC", "SimSun", serif;
  user-select: none;
  overflow: hidden;
  transition: all 0.3s cubic-bezier(0.2, 0.8, 0.2, 1);
}

/* 宣纸纤维底纹滤镜图层 */
.paper-texture-layer {
  position: absolute;
  inset: 0;
  pointer-events: none;
  opacity: 0.35;
  background-image: radial-gradient(circle at 50% 50%, rgba(200, 180, 140, 0.12) 0%, transparent 80%),
                    repeating-linear-gradient(45deg, rgba(160, 140, 110, 0.03) 0px, rgba(160, 140, 110, 0.03) 2px, transparent 2px, transparent 6px);
}

/* 仿古外框与内框 */
.card-border-outer {
  position: relative;
  width: 100%;
  height: 100%;
  box-sizing: border-box;
  border-radius: 2px;
  padding: 10px;
}

.card-border-inner {
  position: relative;
  width: 100%;
  min-height: 520px;
  box-sizing: border-box;
  padding: 32px 28px 24px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

/* 竖排主体布局：核心 writing-mode: vertical-rl */
.card-flow-body {
  writing-mode: vertical-rl;
  text-orientation: mixed;
  display: flex;
  flex-direction: row;
  align-items: flex-start;
  justify-content: flex-start;
  gap: 20px;
  width: 100%;
  min-height: 440px;
}

/* 竖排每一列基础规则 */
.flow-column {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
  height: auto;
}

/* 1. 诗题列 */
.title-column {
  margin-left: 12px;
}

.poem-title {
  margin: 0;
  font-size: 26px;
  font-weight: 900;
  letter-spacing: 0.2em;
  line-height: 1.4;
}

.poem-type-tag {
  margin-top: 14px;
  font-size: 11px;
  letter-spacing: 0.18em;
  opacity: 0.65;
  border: 1px solid currentColor;
  padding: 6px 2px;
  border-radius: 2px;
}

/* 2. 正文诗句列 */
.verse-column {
  line-height: 1.6;
}

.verse-chars {
  font-size: 19px;
  font-weight: 600;
  letter-spacing: 0.22em;
  line-height: 1.8;
}

/* 3. 落款与款识列 (下沉章法) */
.colophon-column {
  margin-right: auto; /* 在 flex vertical-rl 下推到左侧 */
  padding-top: 54px;   /* 传统章法：款识避开天头，大幅下沉 */
  gap: 14px;
}

.colophon-text-wrapper {
  display: inline-flex;
  flex-direction: column;
  gap: 10px;
}

.colophon-line {
  font-size: 13px;
  letter-spacing: 0.16em;
  line-height: 1.5;
  opacity: 0.85;
}

.colophon-sub {
  font-size: 11px;
  letter-spacing: 0.14em;
  opacity: 0.65;
}

/* 印章排列 */
.seals-group {
  display: inline-flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 10px;
}

/* 底部防伪标识印 */
.card-bottom-imprint {
  writing-mode: horizontal-tb;
  text-align: right;
  font-size: 10px;
  letter-spacing: 0.25em;
  opacity: 0.35;
  padding-top: 12px;
}

/* ================= 主题 1：澄素宣纸 (Ivory Xuan Paper) ================= */
.theme-xuan {
  background-color: #f7f4ec;
  color: #1e1b18;
  box-shadow: 0 14px 40px rgba(45, 35, 20, 0.12);
}

.theme-xuan .card-border-outer {
  border: 2px solid rgba(110, 75, 40, 0.45);
}

.theme-xuan .card-border-inner {
  border: 1px solid rgba(138, 92, 45, 0.22);
}

.theme-xuan .poem-title {
  color: #161412;
}

.theme-xuan .verse-chars {
  color: #27231f;
}

.theme-xuan .colophon-column {
  color: #685d4f;
}

/* ================= 主题 2：墨夜泥金 (Midnight Dark & Gold) ================= */
.theme-dark {
  background: radial-gradient(ellipse at 50% 25%, #161d2d 0%, #0d121c 100%);
  color: #ede2cd;
  box-shadow: 0 18px 48px rgba(0, 0, 0, 0.55);
}

.theme-dark .card-border-outer {
  border: 1.5px solid rgba(212, 175, 55, 0.4);
}

.theme-dark .card-border-inner {
  border: 1px solid rgba(212, 175, 55, 0.18);
}

.theme-dark .poem-title {
  color: #faebd2;
  text-shadow: 0 0 10px rgba(212, 175, 55, 0.25);
}

.theme-dark .poem-type-tag {
  color: #c9ab73;
  border-color: rgba(201, 171, 115, 0.4);
}

.theme-dark .verse-chars {
  color: #e3d8be;
}

.theme-dark .colophon-column {
  color: #8b9bb2;
}

.theme-dark .card-bottom-imprint {
  color: #c9ab73;
  opacity: 0.45;
}

/* ================= 主题 3：朱丝阑格 (Vermilion Grid Lines) ================= */
.theme-grid {
  background-color: #f9f6ed;
  color: #201c19;
  box-shadow: 0 14px 40px rgba(160, 40, 30, 0.08);
}

.theme-grid .card-border-outer {
  border: 2px solid rgba(175, 50, 36, 0.55);
}

.theme-grid .card-border-inner {
  border: 1px solid rgba(175, 50, 36, 0.25);
}

/* 朱丝阑：每列诗句下方铺设极淡的朱砂红竖格线 */
.theme-grid .verse-column {
  border-left: 1px solid rgba(175, 50, 36, 0.22);
  padding-left: 10px;
}

.theme-grid .title-column {
  border-left: 1.5px solid rgba(175, 50, 36, 0.35);
  padding-left: 12px;
}

.theme-grid .poem-title {
  color: #1b1715;
}

.theme-grid .verse-chars {
  color: #27221e;
}

.theme-grid .colophon-column {
  color: #6a5749;
}
</style>
