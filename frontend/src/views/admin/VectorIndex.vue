<template>
  <div class="page-view">
    <div class="page-header">
      <h3>向量索引管理</h3>
      <p class="page-desc">查看 Qdrant 向量数据库状态，并执行索引重建与清理</p>
    </div>

    <!-- ========== 状态概览 ========== -->
    <el-row :gutter="16" v-if="status" class="status-row">
      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-card-body">
            <div class="stat-title">向量总数</div>
            <div class="stat-value">{{ status.vector_count }}</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-card-body">
            <div class="stat-title">文档总数</div>
            <div class="stat-value">{{ status.document_count }}</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-card-body">
            <div class="stat-title">已处理向量</div>
            <div class="stat-value">{{ status.processed_vectors }}</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-card-body">
            <div class="stat-title">未处理向量</div>
            <div class="stat-value">{{ status.unprocessed_vectors }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- ========== 操作区 ========== -->
    <el-card class="section-card">
      <template #header>
        <div class="card-header">
          <el-icon><Operation /></el-icon>
          <span>索引操作</span>
        </div>
      </template>

      <el-space wrap size="large">
        <div class="action-block">
          <div class="action-title">全量重建</div>
          <p class="action-desc">清理并重新处理所有文档中的向量（耗时较长，请谨慎使用）</p>
          <div class="action-actions">
            <el-button
              type="danger"
              round
              :loading="rebuildingAll"
              @click="handleRebuildAll"
            >
              <el-icon><Warning /></el-icon>
              重建全部索引
            </el-button>
          </div>
        </div>

        <el-divider direction="vertical" class="action-divider" />

        <div class="action-block">
          <div class="action-title">单文档重建</div>
          <p class="action-desc">对指定文档重新执行向量化与入库</p>
          <div class="action-actions">
            <el-input
              v-model="rebuildDocId"
              type="number"
              placeholder="文档 ID（数字）"
              style="width: 220px"
              @keyup.enter="handleRebuildSingle"
            />
            <el-button
              type="primary"
              round
              :loading="rebuildingSingle"
              :disabled="!rebuildDocId"
              @click="handleRebuildSingle"
            >
              <el-icon><RefreshRight /></el-icon>
              重建
            </el-button>
          </div>
        </div>

        <el-divider direction="vertical" class="action-divider" />

        <div class="action-block">
          <div class="action-title">清理孤儿向量</div>
          <p class="action-desc">删除数据库中已不存在的文档对应的向量</p>
          <div class="action-actions">
            <el-button
              type="warning"
              round
              :loading="cleaningOrphans"
              @click="handleCleanupOrphans"
            >
              <el-icon><Delete /></el-icon>
              清理
            </el-button>
          </div>
        </div>
      </el-space>

      <el-divider v-if="lastActionResult" />

      <el-alert
        v-if="lastActionResult"
        :title="lastActionResult.title"
        :type="lastActionResult.type"
        :description="lastActionResult.description"
        show-icon
        closable
        @close="lastActionResult = null"
        class="action-result"
      />
    </el-card>

    <!-- ========== 刷新按钮 ========== -->
    <el-card class="section-card">
      <template #header>
        <div class="card-header">
          <el-icon><Refresh /></el-icon>
          <span>状态刷新</span>
          <div style="margin-left: auto;">
            <el-tag size="small" effect="plain" type="info" v-if="lastRefreshTime">
              最后刷新: {{ lastRefreshTime }}
            </el-tag>
          </div>
        </div>
      </template>

      <el-button type="primary" round :loading="loadingStatus" @click="fetchStatus">
        <el-icon><Refresh /></el-icon>
        刷新状态
      </el-button>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { adminApi } from '@/api/admin'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Operation,
  Warning,
  RefreshRight,
  Delete,
  Refresh,
} from '@element-plus/icons-vue'

const status = ref(null)
const loadingStatus = ref(false)
const lastRefreshTime = ref('')

const rebuildingAll = ref(false)
const rebuildingSingle = ref(false)
const cleaningOrphans = ref(false)

const rebuildDocId = ref('')
const lastActionResult = ref(null)

function formatNow() {
  const d = new Date()
  const pad = n => String(n).padStart(2, '0')
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

onMounted(() => {
  fetchStatus()
})

async function fetchStatus() {
  loadingStatus.value = true
  try {
    const res = await adminApi.getVectorIndexStatus()
    status.value = res
    lastRefreshTime.value = formatNow()
  } catch {
    // handled by interceptor
  } finally {
    loadingStatus.value = false
  }
}

async function handleRebuildAll() {
  try {
    await ElMessageBox.confirm(
      '确认要重建全部向量索引吗？操作将清理现有向量并重新处理所有文档，可能耗时较长。',
      '危险操作确认',
      { type: 'warning', confirmButtonText: '确认重建', cancelButtonText: '取消' }
    )
  } catch {
    return
  }

  rebuildingAll.value = true
  lastActionResult.value = null
  try {
    const res = await adminApi.rebuildAllVectorIndex()
    lastActionResult.value = {
      title: '全量索引重建任务已发起',
      type: 'success',
      description: `已排队 ${res.queued_count} 个文档，文档 ID 列表：${
        (res.document_ids || []).slice(0, 10).join(', ')
      }${(res.document_ids || []).length > 10 ? '...' : ''}`,
    }
    ElMessage.success('全量索引重建任务已提交')
  } catch {
    // handled by interceptor
  } finally {
    rebuildingAll.value = false
  }
}

async function handleRebuildSingle() {
  const docId = Number(rebuildDocId.value)
  if (!docId || docId <= 0) {
    ElMessage.warning('请输入有效的文档 ID')
    return
  }

  rebuildingSingle.value = true
  lastActionResult.value = null
  try {
    const res = await adminApi.rebuildSingleDocumentVector(docId)
    lastActionResult.value = {
      title: `文档 #${docId} 索引重建任务已发起`,
      type: 'success',
      description: res.detail || '已提交重新向量化任务',
    }
    ElMessage.success(`文档 #${docId} 索引重建任务已提交`)
  } catch {
    // handled by interceptor
  } finally {
    rebuildingSingle.value = false
  }
}

async function handleCleanupOrphans() {
  try {
    await ElMessageBox.confirm(
      '确认要清理孤儿向量吗？将删除 Qdrant 中存在但数据库文档已不存在的向量。',
      '操作确认',
      { type: 'info' }
    )
  } catch {
    return
  }

  cleaningOrphans.value = true
  lastActionResult.value = null
  try {
    const res = await adminApi.cleanupOrphanVectors()
    lastActionResult.value = {
      title: '孤儿向量清理完成',
      type: 'success',
      description: `清理结果: ${JSON.stringify(res)}`,
    }
    ElMessage.success('清理任务已提交')
  } catch {
    // handled by interceptor
  } finally {
    cleaningOrphans.value = false
  }
}
</script>

<style scoped>
.status-row {
  margin-bottom: 16px;
}

.stat-card {
  border-radius: 12px;
}

.stat-card-body {
  text-align: center;
}

.stat-title {
  font-size: 13px;
  color: var(--text-color-2);
  margin-bottom: 6px;
}

.stat-value {
  font-size: 28px;
  font-weight: 600;
  color: var(--text-color);
}

.section-card {
  margin-bottom: 16px;
}

.action-block {
  padding: 8px 12px;
  flex: 1;
  min-width: 260px;
}

.action-title {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 6px;
  color: var(--text-color);
}

.action-desc {
  font-size: 13px;
  color: var(--text-color-2);
  line-height: 1.6;
  margin: 0 0 12px 0;
}

.action-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.action-divider {
  margin: 0;
}

.action-result {
  margin-top: 8px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
