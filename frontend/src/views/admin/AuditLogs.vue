<template>
  <div class="page-view">
    <div class="toolbar">
      <div class="filter-group">
        <el-select
          v-model="filterType"
          placeholder="操作类型"
          clearable
          class="toolbar-select"
          @change="handleSearch"
        >
          <el-option label="上传 (UPLOAD)" value="UPLOAD" />
          <el-option label="下载 (DOWNLOAD)" value="DOWNLOAD" />
        </el-select>

        <el-date-picker
          v-model="dateRange"
          type="daterange"
          range-separator="-"
          start-placeholder="开始"
          end-placeholder="结束"
          value-format="YYYY-MM-DD"
          style="width: 320px"
          popper-class="audit-date-picker"
          @change="handleSearch"
        />

        <el-button type="primary" @click="handleSearch">
          <el-icon><Search /></el-icon>
          搜索
        </el-button>
      </div>
      <div class="action-group">
        <el-button type="success" :loading="exporting" @click="handleExport">
          <el-icon><Download /></el-icon>
          导出 CSV
        </el-button>
      </div>
    </div>

    <el-table :data="items" border stripe v-loading="loading" class="content-table">
      <el-table-column label="操作人" min-width="150">
        <template #default="{ row }">
          {{ row.username || '-' }}|{{ row.real_name || '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="operation_type" label="操作类型" min-width="120">
        <template #default="{ row }">
          <el-tag :type="operationTagType(row.operation_type)" size="small">
            {{ row.operation_type }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作详情" min-width="200">
        <template #default="{ row }">
          <el-popover placement="left" :width="400" trigger="click">
            <template #reference>
              <el-button size="small" link type="primary">
                {{ truncateText(JSON.stringify(row.operation_content || {}), 60) }}
              </el-button>
            </template>
            <pre class="json-view">{{ JSON.stringify(row.operation_content, null, 2) }}</pre>
          </el-popover>
        </template>
      </el-table-column>
      <el-table-column prop="ip_address" label="IP 地址" min-width="140" />
      <el-table-column prop="created_at" label="操作时间" min-width="180">
        <template #default="{ row }">
          <span class="time-text">{{ formatTime(row.created_at) }}</span>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination-wrap">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        background
        @change="fetchLogs"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { adminApi } from '@/api/admin'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const exporting = ref(false)
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const filterType = ref('UPLOAD')
const dateRange = ref(null)

onMounted(() => { fetchLogs() })

async function fetchLogs() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value, operation_type: filterType.value || undefined }
    if (dateRange.value && dateRange.value.length === 2) {
      params.start_time = dateRange.value[0] + 'T00:00:00'
      params.end_time = dateRange.value[1] + 'T23:59:59'
    }
    const res = await adminApi.getAuditLogs(params)
    if (res.items) { items.value = res.items; total.value = res.total }
    else if (Array.isArray(res)) { items.value = res; total.value = res.length }
  } catch { /* handled */ } finally { loading.value = false }
}

function handleSearch() { page.value = 1; fetchLogs() }

async function handleExport() {
  exporting.value = true
  try {
    const params = { page_size: 10000, operation_type: filterType.value || undefined }
    if (dateRange.value && dateRange.value.length === 2) {
      params.start_time = dateRange.value[0] + 'T00:00:00'
      params.end_time = dateRange.value[1] + 'T23:59:59'
    }
    const blob = await adminApi.exportAuditLogs(params)
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `audit_logs_${new Date().toISOString().slice(0, 10)}.csv`
    link.click()
    window.URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch { /* handled */ } finally { exporting.value = false }
}

function operationTagType(type) {
  const map = { LOGIN: 'primary', UPLOAD: 'success', QUERY: 'info', EXPORT: 'warning', DOWNLOAD: 'danger', REVIEW: '' }
  return map[type] || 'info'
}

function truncateText(text, maxLen) {
  if (!text) return '-'
  return text.length > maxLen ? text.slice(0, maxLen) + '...' : text
}

function formatTime(isoStr) {
  if (!isoStr) return '-'
  try {
    const d = new Date(isoStr)
    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}:${String(d.getSeconds()).padStart(2,'0')}`
  } catch { return isoStr }
}
</script>

<style scoped>
.json-view {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 300px;
  overflow-y: auto;
  background: var(--color-bg-hover);
  padding: 12px;
  border-radius: var(--radius-sm);
}
</style>