<template>
  <div class="page-view">
    <div class="toolbar">
      <div class="toolbar-left">
        <el-input
          v-model="keyword"
          placeholder="搜索申请人 / 文档名称"
          clearable
          class="toolbar-input"
          prefix-icon="Search"
          @input="onSearch"
        />
      </div>
      <div class="toolbar-right">
        <el-tag type="warning" effect="light" round>待审核: {{ pendingCount }}</el-tag>
      </div>
    </div>

    <el-table :data="items" border stripe v-loading="loading" class="review-table">
      <el-table-column prop="applicant_name" label="申请人" width="100" />
      <el-table-column prop="document_name" label="申请文档" min-width="180" show-overflow-tooltip />
      <el-table-column prop="reason" label="申请原因" min-width="180">
        <template #default="{ row }">
          <el-tooltip :content="row.reason" placement="top" :show-after="300">
            <span class="reason-text">{{ truncateText(row.reason, 50) }}</span>
          </el-tooltip>
        </template>
      </el-table-column>
      <el-table-column label="期望时长" width="110" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.expected_hours === 0" type="success" size="small" effect="plain">永久</el-tag>
          <el-tag v-else-if="row.expected_hours" type="warning" size="small" effect="plain">{{ formatExpectedHours(row.expected_hours) }}</el-tag>
          <span v-else class="empty-text">-</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100" align="center">
        <template #default="{ row }">
          <el-tag :type="getStatusType(row.status)" size="small" effect="dark">
            {{ row.status_text || '待审核' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="申请时间" width="170" align="center">
        <template #default="{ row }">
          <span class="time-text">{{ formatTime(row.created_at) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="220" fixed="right" align="center">
        <template #default="{ row }">
          <template v-if="row.status === 0">
            <div class="action-cell">
              <el-button size="small" type="success" effect="plain" round @click="openApproveDialog(row)">
                <el-icon><Check/></el-icon>通过
              </el-button>
              <el-button size="small" type="danger" effect="plain" round @click="handleReject(row)">
                <el-icon><Close/></el-icon>拒绝
              </el-button>
            </div>
          </template>
          <template v-else>
            <span class="handled-text">{{ row.reviewer_name ? `已由 ${row.reviewer_name} 处理` : '已处理' }}</span>
          </template>
        </template>
      </el-table-column>
    </el-table>

    <div v-if="items.length > 0" class="pagination-wrap">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        background
        @change="fetchApplications"
      />
    </div>

    <el-empty v-if="!loading && items.length === 0" description="暂无待处理申请" class="empty-wrap" />

    <!-- 授权配置弹窗 -->
    <el-dialog v-model="approveDialogVisible" title="授权配置" width="480px" class="approve-dialog">
      <el-form :model="approveForm" label-width="90px" class="approve-form">
        <el-form-item label="申请人">
          <el-tag type="primary" effect="plain">{{ currentApp?.applicant_name || '' }}</el-tag>
        </el-form-item>
        <el-form-item label="文档">
          <el-tag type="info" effect="plain">{{ currentApp?.document_name || '' }}</el-tag>
        </el-form-item>
        <el-form-item label="授权类型">
          <el-radio-group v-model="approveForm.permission_type">
            <el-radio value="download">查看并下载</el-radio>
            <el-radio value="view_only">仅查看</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="授权时长">
          <div style="width: 100%">
            <el-checkbox v-model="approveForm.permanent" @change="onPermanentChange">永久授权</el-checkbox>
            <el-input-number
              v-if="!approveForm.permanent"
              v-model="approveForm.expires_in_hours"
              :min="1" :max="720" :step="1"
              style="width: 100%; margin-top: 8px"
            />
            <span v-if="!approveForm.permanent" class="help-text">小时（默认24小时）</span>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="approveDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="approving" @click="confirmApprove">确认授权</el-button>
      </template>
    </el-dialog>

    <!-- 令牌信息弹窗 -->
    <el-dialog v-model="tokenDialogVisible" title="审核通过 - 临时令牌" width="520px" class="token-dialog">
      <el-alert type="success" title="申请已通过" :closable="false" show-icon class="token-alert" />
      <el-descriptions :column="1" border style="margin-top: 16px">
        <el-descriptions-item label="授权类型">
          {{ tokenInfo.permission_type === 'view_only' ? '仅查看' : '查看并下载' }}
        </el-descriptions-item>
        <el-descriptions-item label="临时令牌">
          <div class="token-row">
            <code class="token-code">{{ tokenInfo.token }}</code>
            <el-button size="small" @click="copyToken">
              <el-icon><CopyDocument /></el-icon>
              复制
            </el-button>
          </div>
        </el-descriptions-item>
        <el-descriptions-item label="过期时间">{{ tokenInfo.expires_at }}</el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="tokenDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { reviewApi } from '@/api/review'
import { ElMessage, ElMessageBox } from 'element-plus'
import { CopyDocument, Check, Close } from '@element-plus/icons-vue'

const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const approving = ref(false)
const keyword = ref('')
let searchTimer = null

const pendingCount = ref(0)

function getStatusType(status) {
  return status === 0 ? 'warning' : status === 1 ? 'success' : 'danger'
}

const approveDialogVisible = ref(false)
const tokenDialogVisible = ref(false)
const currentApp = ref(null)
const approveForm = reactive({ permission_type: 'download', expires_in_hours: 24, permanent: false })
const tokenInfo = reactive({ token: '', expires_at: '', permission_type: '' })

onMounted(() => {
  fetchApplications()
})

function onSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    page.value = 1
    fetchApplications()
  }, 300)
}

async function fetchApplications() {
  loading.value = true
  try {
    const res = await reviewApi.getPendingApplications({
      page: page.value,
      page_size: pageSize.value,
      keyword: keyword.value || undefined,
    })
    if (res.items) {
      items.value = res.items
      total.value = res.total
      pendingCount.value = res.total
    } else if (Array.isArray(res)) {
      items.value = res
      total.value = res.length
      pendingCount.value = res.length
    }
  } catch (e) {
    // handled
  } finally {
    loading.value = false
  }
}

function openApproveDialog(row) {
  currentApp.value = row
  approveForm.permission_type = 'download'
  // 预填申请人期望时长：0=永久，其他按期望值
  if (row.expected_hours === 0) {
    approveForm.permanent = true
    approveForm.expires_in_hours = 24
  } else {
    approveForm.permanent = false
    approveForm.expires_in_hours = row.expected_hours || 24
  }
  approveDialogVisible.value = true
}

function onPermanentChange(val) {
  // 切换永久授权时无需额外处理，提交时根据 permanent 决定
}

async function confirmApprove() {
  if (!currentApp.value) return
  approving.value = true
  try {
    const res = await reviewApi.approveApplication(currentApp.value.id, {
      permission_type: approveForm.permission_type,
      expires_in_hours: approveForm.permanent ? 0 : approveForm.expires_in_hours,
    })
    tokenInfo.token = res.token || ''
    tokenInfo.expires_at = res.expires_at || ''
    tokenInfo.permission_type = res.permission_type || ''
    approveDialogVisible.value = false
    tokenDialogVisible.value = true
    fetchApplications()
  } catch {
    // handled
  } finally {
    approving.value = false
  }
}

async function handleReject(row) {
  try {
    await ElMessageBox.confirm(
      `确定要拒绝申请人 "${row.applicant_name}" 对文档 "${row.document_name}" 的访问申请吗？`,
      '确认拒绝',
      { confirmButtonText: '确认拒绝', cancelButtonText: '取消', type: 'warning' }
    )
    const res = await reviewApi.rejectApplication(row.id)
    if (res.cooldown_warning) {
      ElMessage.warning(res.cooldown_warning)
      fetchApplications()
      return
    }
    ElMessage.success('已拒绝')
    fetchApplications()
  } catch (e) {
    // cancelled or error
  }
}

function copyToken() {
  navigator.clipboard.writeText(tokenInfo.token).then(
    () => ElMessage.success('令牌已复制到剪贴板'),
    () => ElMessage.warning('复制失败，请手动复制')
  )
}

function formatTime(ts) {
  if (!ts) return '-'
  try { return new Date(ts).toLocaleString('zh-CN') } catch { return ts }
}

function truncateText(text, maxLen) {
  if (!text) return '-'
  return text.length > maxLen ? text.slice(0, maxLen) + '...' : text
}

function formatExpectedHours(hours) {
  if (!hours || hours === 0) return '永久'
  if (hours < 24) return `${hours}小时`
  const days = Math.floor(hours / 24)
  const remain = hours % 24
  return remain === 0 ? `${days}天` : `${days}天${remain}小时`
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

.reason-text {
  color: var(--color-text-regular);
  font-size: 13px;
}

.handled-text {
  color: var(--color-text-placeholder);
  font-size: 13px;
}

.action-cell {
  display: flex;
  justify-content: center;
  gap: 8px;
}

.action-cell :deep(.el-button) {
  padding: 6px 14px;
  font-size: 12px;
}

.empty-wrap {
  padding: 40px 0;
}

.approve-form .help-text {
  display: inline-block;
  margin-left: 8px;
  color: var(--color-text-placeholder);
  font-size: 12px;
  font-weight: normal;
}

.token-dialog :deep(.el-dialog__body) {
  padding-top: 24px;
}

.token-alert {
  margin-bottom: 16px;
}

.token-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.token-code {
  flex: 1;
  padding: 6px 10px;
  background: var(--color-bg-hover);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  color: var(--color-text-primary);
  word-break: break-all;
}
</style>
