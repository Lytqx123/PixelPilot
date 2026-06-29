<template>
  <div class="page-view">
    <div class="page-header">
      <h3>我的收藏</h3>
      <p class="page-desc">收藏的文档列表，可快速查看和下载</p>
    </div>

    <div class="toolbar">
      <el-input
        v-model="keyword"
        placeholder="搜索文档名称"
        clearable
        class="toolbar-input"
        prefix-icon="Search"
        @input="onSearch"
      />
    </div>

    <el-table :data="items" border stripe v-loading="loading" class="fav-table">
      <el-table-column prop="document_name" label="文档名称" min-width="200" show-overflow-tooltip>
        <template #default="{ row }">
          <span>{{ row.document_name || '未命名文档' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="数据标签" width="110" align="center">
        <template #default="{ row }">
          <el-popover placement="bottom" :width="260" trigger="click">
            <template #reference>
              <el-button size="small" type="primary" effect="plain" class="tag-detail-btn">
                <el-icon><Collection /></el-icon>查看
              </el-button>
            </template>
            <div class="tag-popover">
              <div class="tag-row">
                <span class="tag-label">车型：</span>
                <div class="tag-list-inline">
                  <template v-if="getTagArray(row.model_tag).length > 0">
                    <el-tag v-for="t in getTagArray(row.model_tag)" :key="t" size="small" type="primary" class="inline-tag">{{ t }}</el-tag>
                  </template>
                  <span v-else class="empty-text">暂无</span>
                </div>
              </div>
              <div class="tag-row">
                <span class="tag-label">区域：</span>
                <div class="tag-list-inline">
                  <template v-if="getTagArray(row.region_tag).length > 0">
                    <el-tag v-for="t in getTagArray(row.region_tag)" :key="t" size="small" type="success" class="inline-tag">{{ t }}</el-tag>
                  </template>
                  <span v-else class="empty-text">暂无</span>
                </div>
              </div>
              <div class="tag-row">
                <span class="tag-label">分类：</span>
                <div class="tag-list-inline">
                  <template v-if="getTagArray(row.doc_type_tag).length > 0">
                    <el-tag v-for="t in getTagArray(row.doc_type_tag)" :key="t" size="small" type="warning" class="inline-tag">{{ t }}</el-tag>
                  </template>
                  <span v-else class="empty-text">暂无</span>
                </div>
              </div>
            </div>
          </el-popover>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100" align="center">
        <template #default="{ row }">
          <el-tag size="small" effect="dark" :type="row.status === 1 ? 'success' : 'warning'">
            {{ row.status === 1 ? '已通过' : row.status === 0 ? '待审核' : '已拒绝' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right" align="center">
        <template #default="{ row }">
          <div class="action-cell">
            <el-dropdown trigger="click" @command="(cmd) => handleAction(cmd, row)">
              <el-button size="small" type="primary" effect="plain" round>
                <el-icon><Operation /></el-icon>操作
                <el-icon class="el-icon--right"><ArrowDown /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="view" :disabled="!isViewableFormat(row.format) || !canOperate(row)">
                    <el-icon><View /></el-icon>查看文档
                  </el-dropdown-item>
                  <el-dropdown-item command="download" :disabled="!canOperate(row)">
                    <el-icon><Download /></el-icon>下载文档
                  </el-dropdown-item>
                  <el-dropdown-item divided command="unfavorite">
                    <el-icon><StarFilled /></el-icon><span style="color:#e6a23c">取消收藏</span>
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination-wrap">
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
import { ElMessage } from 'element-plus'
import { StarFilled, Collection, Operation, ArrowDown, View, Download } from '@element-plus/icons-vue'

const VIEWABLE_FORMATS = new Set(['PDF', 'MD', 'TXT', 'PNG', 'JPG', 'JPEG'])

function isViewableFormat(format) {
  if (!format) return false
  return VIEWABLE_FORMATS.has(format.toUpperCase())
}

function getTagArray(tagStr) {
  if (!tagStr) return []
  return tagStr.split(',').map(t => t.trim()).filter(t => t)
}

const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const keyword = ref('')
let searchTimer = null

onMounted(() => fetchList())

function canOperate(row) {
  const st = row.source_type || 'UPLOADER'
  return st !== 'AUTHORIZED_EXPIRED'
}

async function fetchList() {
  loading.value = true
  try {
    const res = await documentsApi.getFavorites({
      page: page.value,
      page_size: pageSize.value,
      keyword: keyword.value || undefined
    })
    items.value = res.items || []
    total.value = res.total || 0
  } catch {
    // handled
  } finally {
    loading.value = false
  }
}

function onSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    page.value = 1
    fetchList()
  }, 300)
}

function handleAction(cmd, row) {
  if (cmd === 'view') return handleView(row.document_id)
  if (cmd === 'download') return handleDownload(row.document_id)
  if (cmd === 'unfavorite') return handleUnfavorite(row.document_id)
}

async function handleView(documentId) {
  try {
    const url = documentsApi.getViewDocumentUrl(documentId)
    window.open(url, '_blank')
  } catch {
    // ignore
  }
}

async function handleDownload(documentId) {
  try {
    const res = await documentsApi.downloadDocument(documentId)
    if (res instanceof Blob) {
      const url = window.URL.createObjectURL(res)
      const a = document.createElement('a')
      a.href = url
      a.download = `document_${documentId}`
      a.click()
      window.URL.revokeObjectURL(url)
      ElMessage.success('下载成功')
      await fetchList()
    }
  } catch {
    // handled
  }
}

async function handleUnfavorite(documentId) {
  try {
    await documentsApi.removeFavorite(documentId)
    ElMessage.success('已取消收藏')
    await fetchList()
  } catch {
    // handled
  }
}
</script>

<style scoped>
.page-desc {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin: 0;
}

.toolbar-input {
  width: 320px;
}

.fav-table :deep(.el-table__header th) {
  background: var(--color-bg-hover);
  color: var(--color-text-regular);
  font-weight: 600;
  font-size: 13px;
}

.fav-table :deep(.el-table__body td) {
  color: var(--color-text-regular);
  font-size: 13px;
}

.tag-detail-btn {
  padding: 4px 12px;
}

.tag-popover {
  padding: 4px;
}

.tag-popover .tag-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px solid var(--color-border-light);
}

.tag-popover .tag-row:last-child {
  border-bottom: none;
}

.tag-label {
  flex-shrink: 0;
  color: var(--color-text-secondary);
  font-size: 12px;
  font-weight: 500;
  width: 48px;
}

.tag-list-inline {
  flex: 1;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  line-height: 1.5;
}

.inline-tag {
  margin: 0;
}

.empty-text {
  color: var(--color-text-disabled);
  font-size: 12px;
}

.action-cell {
  display: flex;
  justify-content: center;
}
</style>
