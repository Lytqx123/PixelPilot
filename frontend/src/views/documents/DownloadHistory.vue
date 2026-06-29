<template>
  <div class="page-view">
    <div class="page-header">
      <h3>下载历史</h3>
      <p class="page-desc">查看历史下载文档记录</p>
    </div>

    <el-table :data="items" border stripe v-loading="loading" empty-text="暂无下载记录" class="history-table">
      <el-table-column prop="document_name" label="文档名称" min-width="300" show-overflow-tooltip>
        <template #default="{ row }">
          <span>{{ row.document_name || '未知文档' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="下载时间" width="200" align="center">
        <template #default="{ row }">
          <span class="time-text">{{ formatTime(row.created_at) }}</span>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination-wrap" v-if="total > 0">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        background
        @change="fetchList"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { documentsApi } from '@/api/documents'

const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)

onMounted(() => fetchList())

async function fetchList() {
  loading.value = true
  try {
    const res = await documentsApi.getDownloadHistory({ page: page.value, page_size: pageSize.value })
    items.value = res.items || []
    total.value = res.total || 0
  } catch {
    // handled
  } finally {
    loading.value = false
  }
}

function formatTime(ts) {
  if (!ts) return '-'
  try {
    return new Date(ts).toLocaleString('zh-CN')
  } catch {
    return ts
  }
}
</script>

<style scoped>
.page-desc {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin: 0;
}

.history-table :deep(.el-table__header th) {
  background: var(--color-bg-hover);
  color: var(--color-text-regular);
  font-weight: 600;
  font-size: 13px;
}

.history-table :deep(.el-table__body td) {
  color: var(--color-text-regular);
  font-size: 13px;
}
</style>
