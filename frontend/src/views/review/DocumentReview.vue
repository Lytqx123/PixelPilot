<template>
  <div class="page-view">
    <div class="toolbar">
      <div class="toolbar-left">
        <el-input
          v-model="keyword"
          placeholder="搜索文档名称 / 上传人"
          clearable
          class="toolbar-input"
          prefix-icon="Search"
          @input="onSearch"
        />
      </div>
      <div class="toolbar-right">
        <el-tag type="warning" effect="light" round>待审核: {{ total }}</el-tag>
      </div>
    </div>

    <el-table :data="items" border stripe v-loading="loading" class="review-table">
      <el-table-column prop="name" label="文档名称" min-width="200" show-overflow-tooltip />
      <el-table-column label="标签" width="110">
        <template #default="{ row }">
          <el-popover placement="bottom" :width="320" trigger="click">
            <template #reference>
              <el-button size="small" type="primary" effect="plain" class="tag-detail-btn">
                <el-icon><Collection /></el-icon>
                查看
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
      <el-table-column label="文件大小" width="110" align="center">
        <template #default="{ row }">
          <span class="size-text">{{ formatSize(row.file_size) }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="uploader_name" label="上传人" width="110" />
      <el-table-column label="上传时间" width="170" align="center">
        <template #default="{ row }">
          <span class="time-text">{{ formatTime(row.created_at) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="320" fixed="right" align="center">
        <template #default="{ row }">
          <div class="action-cell">
            <el-button size="small" type="info" effect="plain" round @click="handleView(row)">
              <el-icon><View /></el-icon>预览
            </el-button>
            <el-button size="small" effect="plain" round @click="handleDownload(row)">
              <el-icon><Download /></el-icon>下载
            </el-button>
            <el-button size="small" type="success" effect="plain" round @click="handleApprove(row)">
              <el-icon><Check /></el-icon>通过
            </el-button>
            <el-button size="small" type="danger" effect="plain" round @click="handleReject(row)">
              <el-icon><Close /></el-icon>拒绝
            </el-button>
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
        @change="fetchDocuments"
      />
    </div>

    <!-- 审核通过对话框（含访问模式设置） -->
    <el-dialog v-model="approveDialogVisible" :title="'审核通过：' + (currentDoc?.name || '')" width="520px">
      <el-form :model="approveForm" label-width="100px">
        <el-form-item label="访问模式">
          <el-radio-group v-model="approveForm.access_mode">
            <el-radio label="department_public">部门内公开</el-radio>
            <el-radio label="apply_required">需申请访问</el-radio>
          </el-radio-group>
        </el-form-item>
        <div class="mode-hint" v-if="approveForm.access_mode === 'department_public'">
          <el-icon><InfoFilled /></el-icon>
          <span>同部门所有员工可直接查看和下载此文档</span>
        </div>
        <div class="mode-hint" v-else>
          <el-icon><InfoFilled /></el-icon>
          <span>同部门普通员工需申请后才能访问，管理员/审核员可直接访问</span>
        </div>
        <el-form-item label="审核备注">
          <el-input
            v-model="approveForm.comment"
            type="textarea"
            :rows="3"
            placeholder="可输入审核备注（可选）"
            maxlength="500"
            show-word-limit
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="approveDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="approving" @click="submitApprove">确认通过</el-button>
      </template>
    </el-dialog>

    <!-- 审核拒绝对话框 -->
    <el-dialog v-model="rejectDialogVisible" :title="'审核拒绝：' + (currentDoc?.name || '')" width="500px">
      <el-form :model="rejectForm" label-width="100px">
        <el-form-item label="拒绝原因">
          <el-input
            v-model="rejectForm.comment"
            type="textarea"
            :rows="4"
            placeholder="请填写拒绝原因（必填）"
            maxlength="500"
            show-word-limit
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rejectDialogVisible = false">取消</el-button>
        <el-button type="danger" :loading="rejecting" @click="submitReject">确认拒绝</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { reviewApi } from '@/api/review'
import { Collection, Check, Close, InfoFilled, View, Download } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

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

const approveDialogVisible = ref(false)
const rejectDialogVisible = ref(false)
const approving = ref(false)
const rejecting = ref(false)
const currentDoc = ref(null)
const approveForm = reactive({
  access_mode: 'department_public',
  comment: '',
})
const rejectForm = reactive({
  comment: '',
})

onMounted(() => {
  fetchDocuments()
})

async function fetchDocuments() {
  loading.value = true
  try {
    const res = await reviewApi.getPendingDocuments({
      page: page.value,
      page_size: pageSize.value,
      keyword: keyword.value || undefined
    })
    if (res.items) {
      items.value = res.items
      total.value = res.total
    } else if (Array.isArray(res)) {
      items.value = res
      total.value = res.length
    }
  } catch (e) {
    // handled
  } finally {
    loading.value = false
  }
}

function onSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    page.value = 1
    fetchDocuments()
  }, 300)
}

function getDownloadUrl(row) {
  const token = localStorage.getItem('token') || ''
  return `/api/documents/${row.id}/download?token=${encodeURIComponent(token)}`
}

function getViewUrl(row) {
  const token = localStorage.getItem('token') || ''
  return `/api/documents/${row.id}/view?token=${encodeURIComponent(token)}`
}

function handleView(row) {
  window.open(getViewUrl(row), '_blank')
}

function handleDownload(row) {
  window.open(getDownloadUrl(row), '_blank')
}

async function handleApprove(row) {
  currentDoc.value = row
  approveForm.access_mode = 'department_public'
  approveForm.comment = ''
  approveDialogVisible.value = true
}

async function handleReject(row) {
  currentDoc.value = row
  rejectForm.comment = ''
  rejectDialogVisible.value = true
}

async function submitApprove() {
  if (!currentDoc.value) return
  approving.value = true
  try {
    await reviewApi.approveDocument(currentDoc.value.id, {
      comment: approveForm.comment || undefined,
      access_mode: approveForm.access_mode,
    })
    ElMessage.success('审核已通过，文档访问模式已设置')
    approveDialogVisible.value = false
    fetchDocuments()
  } catch (e) {
    // handled
  } finally {
    approving.value = false
  }
}

async function submitReject() {
  if (!currentDoc.value) return
  if (!rejectForm.comment || !rejectForm.comment.trim()) {
    ElMessage.warning('拒绝原因不能为空')
    return
  }
  rejecting.value = true
  try {
    await reviewApi.rejectDocument(currentDoc.value.id, {
      comment: rejectForm.comment,
    })
    ElMessage.success('已拒绝')
    rejectDialogVisible.value = false
    fetchDocuments()
  } catch (e) {
    // handled
  } finally {
    rejecting.value = false
  }
}

function formatTime(ts) {
  if (!ts) return '-'
  try { return new Date(ts).toLocaleString('zh-CN') } catch { return ts }
}

function formatSize(bytes) {
  if (!bytes) return '0 B'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}
</script>

<style scoped>
.toolbar-input {
  width: 360px;
}

.review-table :deep(.el-table__header th) {
  background: var(--color-bg-hover);
  color: var(--color-text-regular);
  font-weight: 600;
  font-size: 13px;
}

.review-table :deep(.el-table__body td) {
  color: var(--color-text-regular);
  font-size: 13px;
}

.tag-detail-btn {
  padding: 4px 12px;
}

.size-text {
  color: var(--color-text-secondary);
  font-size: 13px;
}

.action-cell {
  display: flex;
  justify-content: center;
  gap: 4px;
  flex-wrap: wrap;
}

.action-cell :deep(.el-button) {
  padding: 6px 14px;
  font-size: 12px;
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

.mode-hint {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  color: var(--color-text-regular);
  background: var(--color-primary-lighter);
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  margin-top: -8px;
  margin-bottom: 12px;
}

.mode-hint .el-icon {
  margin-top: 3px;
  color: var(--color-primary);
}
</style>
