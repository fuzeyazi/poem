<template>
  <div class="classical-seal-wrapper" :style="{ width: `${computedSize}px`, height: `${computedSize}px` }">
    <svg
      :viewBox="viewBox"
      class="classical-seal-svg"
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <!-- 金石残损噪点滤镜 -->
        <filter :id="`erosion-${uid}`" x="-10%" y="-10%" width="120%" height="120%">
          <feTurbulence type="fractalNoise" baseFrequency="0.045" numOctaves="3" seed="8" result="noise" />
          <feDisplacementMap in="SourceGraphic" in2="noise" scale="2.0" xChannelSelector="R" yChannelSelector="G" />
        </filter>

        <!-- 朱砂古印微渐变印泥质感 -->
        <linearGradient :id="`cinnabar-${uid}`" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" :stop-color="cinnabarColor" />
          <stop offset="55%" stop-color="#992a1e" />
          <stop offset="100%" stop-color="#832116" />
        </linearGradient>

        <!-- 阴刻印章朱砂底层金石滤镜 -->
        <filter :id="`shadow-${uid}`">
          <feDropShadow dx="0.5" dy="0.8" stdDeviation="0.8" flood-color="#4a150e" flood-opacity="0.35" />
        </filter>
      </defs>

      <!-- 印章主体图层（带金石残损滤镜） -->
      <g :filter="`url(#erosion-${uid})`">
        <!-- 阴刻模式：满地朱砂红底 -->
        <template v-if="carving === 'yin'">
          <rect
            v-if="isSquare"
            x="5"
            y="5"
            width="90"
            height="90"
            rx="5"
            :fill="`url(#cinnabar-${uid})`"
          />
          <ellipse
            v-else
            cx="50"
            cy="50"
            rx="45"
            ry="45"
            :fill="`url(#cinnabar-${uid})`"
          />
          <!-- 阴刻内衬极细残线装饰 -->
          <rect
            v-if="isSquare"
            x="9"
            y="9"
            width="82"
            height="82"
            rx="3"
            fill="none"
            :stroke="paperColor"
            stroke-width="0.8"
            opacity="0.25"
          />
        </template>

        <!-- 阳刻模式：镂空透底，朱砂粗外边框 -->
        <template v-else>
          <rect
            v-if="isSquare"
            x="5"
            y="5"
            width="90"
            height="90"
            rx="5"
            fill="none"
            :stroke="`url(#cinnabar-${uid})`"
            stroke-width="5.5"
          />
          <ellipse
            v-else
            cx="50"
            cy="50"
            rx="45"
            ry="45"
            fill="none"
            :stroke="`url(#cinnabar-${uid})`"
            stroke-width="5.5"
          />
          <!-- 阳刻内边细线 -->
          <rect
            v-if="isSquare"
            x="9.5"
            y="9.5"
            width="81"
            height="81"
            rx="3"
            fill="none"
            :stroke="`url(#cinnabar-${uid})`"
            stroke-width="1.2"
            opacity="0.65"
          />
          <ellipse
            v-else
            cx="50"
            cy="50"
            rx="41"
            ry="41"
            fill="none"
            :stroke="`url(#cinnabar-${uid})`"
            stroke-width="1.2"
            opacity="0.65"
          />
        </template>

        <!-- 篆刻文字节点 -->
        <text
          v-for="(item, idx) in positionedChars"
          :key="idx"
          :x="item.x"
          :y="item.y"
          :font-size="item.fontSize"
          :fill="carving === 'yin' ? paperColor : `url(#cinnabar-${uid})`"
          :font-weight="carving === 'yin' ? 'bold' : '900'"
          text-anchor="middle"
          dominant-baseline="central"
          class="seal-char-text"
        >
          {{ item.char }}
        </text>
      </g>
    </svg>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { toTraditional } from '@/utils/s2tDict'

export interface SealProps {
  text?: string
  size?: number | string
  shape?: 'square' | 'oval' | 'round'
  carving?: 'yang' | 'yin' // yang=朱文(阳刻), yin=白文(阴刻)
  paperColor?: string
  cinnabarColor?: string
  traditional?: boolean
}

const props = withDefaults(defineProps<SealProps>(), {
  text: '太白',
  size: 56,
  shape: 'square',
  carving: 'yang',
  paperColor: '#faf6ee',
  cinnabarColor: '#ab3124',
  traditional: true
})

const uid = Math.random().toString(36).slice(2, 9)
const viewBox = '0 0 100 100'

const computedSize = computed(() => {
  if (typeof props.size === 'number') return props.size
  const n = parseInt(props.size, 10)
  return isNaN(n) ? 56 : n
})

const isSquare = computed(() => props.shape === 'square')

interface PositionedChar {
  char: string
  x: number
  y: number
  fontSize: number
}

// 计算篆刻字符序列（1~4 字传统逆时针 2x2 篆刻章法）
const positionedChars = computed<PositionedChar[]>(() => {
  const raw = (props.text || '印').trim()
  const converted = props.traditional ? toTraditional(raw) : raw
  const chars = Array.from(converted).slice(0, 4)

  if (chars.length === 0) return []

  // 1 字章：置中放大
  if (chars.length === 1) {
    return [
      { char: chars[0], x: 50, y: 51, fontSize: 48 }
    ]
  }

  // 2 字章：单竖列自上而下
  if (chars.length === 2) {
    return [
      { char: chars[0], x: 50, y: 32, fontSize: 30 },
      { char: chars[1], x: 50, y: 68, fontSize: 30 }
    ]
  }

  // 3 字章：右列两字，左列一字置中
  if (chars.length === 3) {
    return [
      { char: chars[0], x: 69, y: 32, fontSize: 26 }, // 右上 (第1字)
      { char: chars[1], x: 69, y: 68, fontSize: 26 }, // 右下 (第2字)
      { char: chars[2], x: 31, y: 50, fontSize: 28 }  // 左中 (第3字)
    ]
  }

  // 4 字章：自右向左、自上而下 2x2 回文经典规矩
  // 右上: 0, 右下: 1, 左上: 2, 左下: 3
  return [
    { char: chars[0], x: 69, y: 32, fontSize: 26 }, // 1. 右上
    { char: chars[1], x: 69, y: 68, fontSize: 26 }, // 2. 右下
    { char: chars[2], x: 31, y: 32, fontSize: 26 }, // 3. 左上
    { char: chars[3], x: 31, y: 68, fontSize: 26 }  // 4. 左下
  ]
})
</script>

<style scoped>
.classical-seal-wrapper {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  user-select: none;
  flex-shrink: 0;
}

.classical-seal-svg {
  width: 100%;
  height: 100%;
  display: block;
  overflow: visible;
}

.seal-char-text {
  font-family: "Noto Serif SC", "Songti SC", "SimSun", serif;
  letter-spacing: 0;
  user-select: none;
}
</style>
