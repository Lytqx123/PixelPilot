<template>
  <router-view />
</template>

<script setup>
import { onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

onMounted(async () => {
  if (authStore.isLoggedIn) {
    await Promise.allSettled([
      authStore.fetchUserInfo(),
      authStore.fetchMenus(),
    ])
  }
})
</script>

<style>
/* ============================================================
   全局设计令牌(Design Tokens) — 青蓝色 sky/cyan 主题
   ============================================================ */
:root {
  /* 主色 sky */
  --color-primary: #0ea5e9;
  --color-primary-hover: #0284c7;
  --color-primary-active: #0369a1;
  --color-primary-light: #e0f2fe;
  --color-primary-lighter: #f0f9ff;
  --color-primary-gradient: linear-gradient(135deg, #0ea5e9, #38bdf8);

  /* 辅助色 */
  --color-success: #10b981;
  --color-warning: #f59e0b;
  --color-danger: #ef4444;
  --color-info: #64748b;

  /* 中性色 */
  --color-text-primary: #0f172a;
  --color-text-regular: #334155;
  --color-text-secondary: #64748b;
  --color-text-placeholder: #94a3b8;
  --color-text-disabled: #cbd5e1;
  --color-border: #e2e8f0;
  --color-border-light: #f1f5f9;
  --color-bg-page: #f0f9ff;
  --color-bg-card: #ffffff;
  --color-bg-hover: #f0f9ff;

  /* 圆角 */
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 14px;
  --radius-xl: 20px;
  --radius-pill: 999px;

  /* 阴影 */
  --shadow-sm: 0 1px 3px rgba(15, 23, 42, 0.04);
  --shadow-md: 0 4px 12px rgba(15, 23, 42, 0.06);
  --shadow-lg: 0 8px 24px rgba(15, 23, 42, 0.08);
  --shadow-primary: 0 4px 14px rgba(14, 165, 233, 0.25);

  /* 间距 */
  --spacing-xs: 4px;
  --spacing-sm: 8px;
  --spacing-md: 16px;
  --spacing-lg: 24px;
  --spacing-xl: 32px;
}

/* ============================================================
   基础重置
   ============================================================ */
html, body, #app {
  margin: 0;
  padding: 0;
  height: 100%;
  font-family: 'Segoe UI', 'PingFang SC', 'Inter', system-ui, sans-serif;
  background: var(--color-bg-page);
  color: var(--color-text-primary);
  font-size: 14px;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

* {
  box-sizing: border-box;
}

::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

::-webkit-scrollbar-thumb {
  background: var(--color-text-disabled);
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: var(--color-text-secondary);
}

::-webkit-scrollbar-track {
  background: transparent;
}

/* ============================================================
   Element Plus 主题覆盖 — 统一为青蓝色
   ============================================================ */

/* 主按钮 */
.el-button--primary {
  --el-button-bg-color: var(--color-primary);
  --el-button-border-color: var(--color-primary);
  --el-button-hover-bg-color: var(--color-primary-hover);
  --el-button-hover-border-color: var(--color-primary-hover);
  --el-button-active-bg-color: var(--color-primary-active);
  --el-button-active-border-color: var(--color-primary-active);
  --el-button-disabled-bg-color: var(--color-primary-light);
  --el-button-disabled-border-color: var(--color-primary-light);
  --el-button-disabled-text-color: #ffffff;
}

/* 链接/文字按钮 */
.el-button--primary.is-link,
.el-button--primary.is-text {
  --el-button-text-color: var(--color-primary);
  --el-button-hover-text-color: var(--color-primary-hover);
  --el-button-active-text-color: var(--color-primary-active);
}

/* 主色 Tag */
.el-tag.el-tag--primary {
  --el-tag-bg-color: var(--color-primary-lighter);
  --el-tag-border-color: var(--color-primary-light);
  --el-tag-text-color: var(--color-primary-hover);
}

.el-tag.el-tag--primary.el-tag--dark {
  --el-tag-bg-color: var(--color-primary);
  --el-tag-border-color: var(--color-primary);
  --el-tag-text-color: #ffffff;
}

/* 输入框聚焦色 */
.el-input__wrapper.is-focus,
.el-textarea__inner:focus {
  box-shadow: 0 0 0 1px var(--color-primary) inset !important;
}

.el-radio__input.is-checked .el-radio__inner,
.el-checkbox__input.is-checked .el-checkbox__inner {
  background-color: var(--color-primary);
  border-color: var(--color-primary);
}

.el-radio__input.is-checked + .el-radio__label,
.el-checkbox__input.is-checked + .el-checkbox__label {
  color: var(--color-primary-hover);
}

.el-radio.is-bordered.is-checked,
.el-checkbox.is-bordered.is-checked {
  border-color: var(--color-primary);
}

/* Switch */
.el-switch.is-checked .el-switch__core {
  background-color: var(--color-primary);
  border-color: var(--color-primary);
}

/* Pagination 选中 */
.el-pagination.is-background .el-pager li.is-active {
  background-color: var(--color-primary);
}

/* Menu 选中 */
.el-menu-item.is-active {
  color: var(--color-primary);
}

/* Tabs 选中 */
.el-tabs__item.is-active {
  color: var(--color-primary);
}
.el-tabs__active-bar {
  background-color: var(--color-primary);
}

/* 面包屑链接 */
.el-breadcrumb__inner.is-link:hover {
  color: var(--color-primary-hover);
}

/* Loading */
.el-loading-spinner .circular .path {
  stroke: var(--color-primary);
}

/* 日期选择器选中 */
.el-date-table td.current:not(.disabled) span,
.el-time-panel__btn.confirm {
  background-color: var(--color-primary);
}

/* Select 选中项 */
.el-select-dropdown__item.selected {
  color: var(--color-primary);
  font-weight: 600;
}

/* 全局卡片圆角统一 */
.el-card {
  border-radius: var(--radius-lg);
  border-color: var(--color-border);
}

/* Dialog 圆角 */
.el-dialog {
  border-radius: var(--radius-lg);
  overflow: hidden;
}

/* Dropdown 圆角 */
.el-dropdown-menu {
  border-radius: var(--radius-md);
}

/* Message / Notification */
.el-message-box {
  border-radius: var(--radius-lg);
}

/* ============================================================
   全局通用布局类 — 所有面板共享
   ============================================================ */

/* 页面容器：统一最大宽度 + 居中 + 内边距 */
.page-view {
  max-width: 1280px;
  margin: 0 auto;
  padding: 20px 24px;
}

/* 工具栏：搜索/筛选区，所有面板统一 */
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 20px;
  padding: 16px 20px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
}

.toolbar-left,
.toolbar-right,
.filter-group,
.action-group {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.toolbar-input { width: 260px; }
.toolbar-select { width: 200px; }

/* 页面标题区 */
.page-header {
  margin-bottom: 20px;
}

.page-header h3 {
  font-size: 22px;
  font-weight: 700;
  color: var(--color-text-primary);
  margin: 0 0 6px;
  letter-spacing: -0.3px;
}

.page-header .subtitle {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin: 0;
}

/* 分页区：统一右对齐 + 上间距 */
.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  padding: 20px 0 0;
}

/* 内容表格：统一圆角 + 阴影 */
.content-table {
  border-radius: var(--radius-md);
  overflow: hidden;
  box-shadow: var(--shadow-sm);
}

/* 表格内时间/大小等辅助文字 */
.time-text,
.size-text {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.text-muted {
  color: var(--color-text-disabled);
}

/* 空状态 */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 60px 20px;
  color: var(--color-text-placeholder);
  font-size: 14px;
}
</style>
