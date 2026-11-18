<template>
  <div class="nf">
    <div class="nf-seal">诗</div>
    <div class="nf-code">404</div>
    <div class="nf-text">此页不在诗境之中</div>
    <router-link class="nf-back" to="/poetry">回诗词库 →</router-link>
  </div>
</template>

<script setup lang="ts"></script>

<style scoped>
.nf { min-height: 100dvh; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 14px;  padding: 24px;  background: var(--md-surface);  color: var(--md-on-surface);  font-family: var(--f-sans); }
.nf-seal {
  width: 56px; height: 56px; border-radius: 20px;
  background: var(--md-primary-container); color: var(--md-on-primary-container);
  display: flex; align-items: center; justify-content: center;
  font-size: 30px; box-shadow: var(--shadow-sm);
}
.nf-code { font-size: 64px; letter-spacing: normal; color: var(--md-on-surface); }
.nf-text { font-size: 18px; letter-spacing: normal; color: var(--md-on-surface-variant); }
.nf-back { margin-top: 12px; font-size: 14px; letter-spacing: normal; color: var(--md-on-primary); text-decoration: none; border-bottom: 1px solid transparent;  padding: 12px 24px;  min-height: 48px;  border-radius: 999px;  background: var(--md-primary); }
.nf-back:hover { border-bottom-color: var(--md-primary); }

:deep(.el-button) { min-height: 44px; border-radius: 999px; font-family: var(--f-sans); letter-spacing: normal; }
:deep(.el-input__wrapper) { min-height: 48px; border-radius: 12px; }
:deep(.el-textarea__inner) { border-radius: 12px; font-size: 15px; }
:deep(.el-tabs__item) { min-height: 48px; font-family: var(--f-sans); letter-spacing: normal; }
:deep(.el-dialog) { max-width: calc(100vw - 32px); border-radius: 28px; }
.form-error { font-size: 14px; line-height: 1.5; color: var(--md-error); background: var(--md-error-container); border-radius: 12px; padding: 12px 16px; }

</style>
