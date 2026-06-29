<template>
  <div class="source-card">
    <!-- 头部:格式徽标 + 文档名 + 匹配度 -->
    <div class="source-header">
      <div class="source-format-badge" :class="getFormatClass(source.format)">
        {{ source.format || '?' }}
      </div>
      <div class="source-title-area">
        <div class="source-title" :title="source.document_name">{{ source.document_name }}</div>
        <div class="source-submeta">
          <span v-if="source.page_number" class="submeta-item">
            <el-icon :size="12"><Document /></el-icon>第 {{ source.page_number }} 页
          </span>
          <span v-if="source.paragraph" class="submeta-item">段落 {{ source.paragraph }}</span>
          <span v-if="source.score" class="submeta-item score">
            <el-icon :size="12"><Aim /></el-icon>{{ formatScore(source.score) }}
          </span>
        </div>
      </div>
    </div>

    <!-- 内容片段 -->
    <div
      v-if="source.highlighted_snippet || source.content_snippet"
      class="source-body"
    >
      <p
        v-if="source.highlighted_snippet"
        class="source-snippet"
        v-html="source.highlighted_snippet"
      ></p>
      <p v-else class="source-snippet">{{ source.content_snippet }}</p>
    </div>

    <!-- 操作区 -->
    <div class="source-footer">
      <template v-if="isViewableFormat(source.format)">
        <el-tooltip
          v-if="!source.can_view && !source.can_download"
          content="您没有查看权限,请申请访问"
          placement="top"
        >
          <el-button size="small" type="primary" text disabled>
            <el-icon><View /></el-icon>查看
          </el-button>
        </el-tooltip>
        <el-button
          v-else
          size="small"
          type="primary"
          text
          :disabled="!source.can_view"
          @click="$emit('view', source.document_id)"
        >
          <el-icon><View /></el-icon>查看
        </el-button>
      </template>

      <el-tooltip
        v-if="!source.can_download && !source.can_view"
        content="您没有下载权限,请申请访问"
        placement="top"
      >
        <el-button size="small" type="success" text disabled>
          <el-icon><Download /></el-icon>下载
        </el-button>
      </el-tooltip>
      <el-button
        v-else
        size="small"
        type="success"
        text
        :disabled="!source.can_download"
        @click="$emit('download', source.document_id)"
      >
        <el-icon><Download /></el-icon>下载
      </el-button>

      <el-button
        size="small"
        text
        :class="{ 'fav-active': source.is_favorited }"
        @click="$emit('favorite', source.document_id)"
      >
        <el-icon><StarFilled v-if="source.is_favorited" /><Star v-else /></el-icon>
        {{ source.is_favorited ? '已收藏' : '收藏' }}
      </el-button>

      <el-button
        v-if="!(source.can_download || source.can_view) && !source.has_pending_application"
        size="small"
        type="primary"
        round
        class="apply-btn"
        @click="$emit('apply', source.document_id)"
      >
        <el-icon><Unlock /></el-icon>申请访问
      </el-button>
      <el-tag
        v-else-if="source.has_pending_application"
        type="warning"
        size="small"
        class="pending-tag"
      >
        审核中
      </el-tag>
    </div>

    <!-- 授权到期提醒 -->
    <div v-if="source.permission_expires_at && !source.has_pending_application" class="expiry-bar" :class="{ 'expiry-urgent': isExpiringSoon(source.permission_expires_at) }">
      <el-icon :size="12"><Clock /></el-icon>
      <span>{{ formatExpiry(source.permission_expires_at) }}</span>
    </div>
  </div>
</template>

<script setup>
import { Document, Star, StarFilled, View, Download, Unlock, Aim, Clock } from '@element-plus/icons-vue'

const props = defineProps({
  source: { type: Object, required: true },
})

defineEmits(['apply', 'view', 'download', 'favorite'])

const VIEWABLE_FORMATS = new Set(['PDF', 'MD', 'TXT', 'PNG', 'JPG', 'JPEG'])

function isViewableFormat(format) {
  if (!format) return false
  return VIEWABLE_FORMATS.has(format.toUpperCase())
}

function getFormatClass(format) {
  if (!format) return 'fmt-default'
  const f = format.toUpperCase()
  if (f === 'PDF') return 'fmt-pdf'
  if (['MD', 'TXT'].includes(f)) return 'fmt-text'
  if (['PNG', 'JPG', 'JPEG', 'GIF', 'BMP'].includes(f)) return 'fmt-image'
  if (['DOC', 'DOCX'].includes(f)) return 'fmt-doc'
  if (['XLS', 'XLSX'].includes(f)) return 'fmt-xls'
  if (['PPT', 'PPTX'].includes(f)) return 'fmt-ppt'
  if (['ZIP', 'RAR', '7Z'].includes(f)) return 'fmt-zip'
  return 'fmt-default'
}

function formatScore(score) {
  if (score === undefined || score === null) return ''
  const pct = Math.round(score * 100)
  return `匹配 ${pct}%`
}

function isExpiringSoon(expiresAt) {
  if (!expiresAt) return false
  const now = new Date()
  const expiry = new Date(expiresAt)
  const diffMs = expiry - now
  return diffMs > 0 && diffMs < 24 * 60 * 60 * 1000  // 24小时内
}

function formatExpiry(expiresAt) {
  if (!expiresAt) return ''
  const now = new Date()
  const expiry = new Date(expiresAt)
  const diffMs = expiry - now
  if (diffMs <= 0) return '授权已过期'
  const hours = Math.floor(diffMs / (1000 * 60 * 60))
  const days = Math.floor(hours / 24)
  if (days > 0) return `授权 ${days} 天后到期`
  if (hours > 0) return `授权 ${hours} 小时后到期`
  const mins = Math.floor(diffMs / (1000 * 60))
  return `授权 ${mins} 分钟后到期`
}
</script>

<style scoped>
.source-card {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 14px 16px;
  margin-bottom: 10px;
  transition: all 0.2s ease;
}

.source-card:hover {
  border-color: #7dd3fc;
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}

/* 头部 */
.source-header {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 10px;
}

.source-format-badge {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: var(--radius-sm);
  font-size: 10px;
  font-weight: 700;
  color: #ffffff;
  letter-spacing: 0.5px;
  text-transform: uppercase;
}

.fmt-pdf { background: #ef4444; }
.fmt-text { background: var(--color-primary); }
.fmt-image { background: #8b5cf6; }
.fmt-doc { background: #2563eb; }
.fmt-xls { background: #10b981; }
.fmt-ppt { background: #f59e0b; }
.fmt-zip { background: #64748b; }
.fmt-default { background: var(--color-info); }

.source-title-area {
  flex: 1;
  min-width: 0;
}

.source-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-bottom: 4px;
}

.source-submeta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 11px;
  color: var(--color-text-secondary);
}

.submeta-item {
  display: inline-flex;
  align-items: center;
  gap: 3px;
}

.submeta-item.score {
  color: var(--color-primary);
  font-weight: 600;
}

/* 内容片段 */
.source-body {
  margin: 0 0 10px 0;
  padding: 10px 12px;
  background: var(--color-primary-lighter);
  border-radius: var(--radius-sm);
  border-left: 3px solid var(--color-primary);
  max-height: 120px;
  overflow-y: auto;
}

.source-snippet {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--color-text-regular);
}

.source-snippet :deep(strong) {
  color: #b45309;
  font-weight: 600;
  background: #fef3c7;
  padding: 0 2px;
  border-radius: 3px;
}

/* 操作区 */
.source-footer {
  display: flex;
  align-items: center;
  gap: 4px;
  padding-top: 8px;
  border-top: 1px solid var(--color-border-light);
  flex-wrap: wrap;
}

.source-footer :deep(.el-button) {
  padding: 4px 10px;
  font-size: 12px;
  height: auto;
}

.fav-active {
  color: var(--color-warning) !important;
}

.apply-btn {
  margin-left: auto;
  padding: 4px 14px !important;
}

.pending-tag {
  margin-left: auto;
}

/* 授权到期提醒 */
.expiry-bar {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 10px;
  margin-top: 8px;
  background: #f0f9ff;
  border: 1px solid #bae6fd;
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: #0369a1;
}

.expiry-urgent {
  background: #fef2f2;
  border-color: #fecaca;
  color: #dc2626;
  font-weight: 600;
}

/* 滚动条 */
.source-body::-webkit-scrollbar {
  width: 4px;
}

.source-body::-webkit-scrollbar-track {
  background: transparent;
  border-radius: 2px;
}

.source-body::-webkit-scrollbar-thumb {
  background: var(--color-text-disabled);
  border-radius: 2px;
}

.source-body::-webkit-scrollbar-thumb:hover {
  background: var(--color-text-placeholder);
}
</style>
