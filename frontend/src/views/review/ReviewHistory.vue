<template>
  <div class="page-view">
    <div class="page-header">
      <h3>审核历史</h3>
      <p class="page-desc">{{ isSuperAdmin ? '按部门筛选查看各部门审核记录' : '查看本部门审核记录' }}</p>
    </div>

    <div class="toolbar">
      <el-select
        v-if="isSuperAdmin"
        v-model="selectedDepartmentId"
        placeholder="选择部门"
        clearable
        class="toolbar-input"
        @change="onDepartmentChange"
      >
        <el-option
          v-for="dept in departments"
          :key="dept.id"
          :label="dept.name"
          :value="dept.id"
        />
      </el-select>
      <el-input
        v-model="keyword"
        placeholder="搜索审核对象"
        clearable
        class="toolbar-input"
        prefix-icon="Search"
        @input="onSearch"
      />
    </div>

    <el-table :data="items" border stripe v-loading="loading" class="review-table">
      <el-table-column label="审核类型" width="100" align="center">
        <template #default="{ row }">
          <el-tag :type="row.type === 'document' ? 'primary' : 'warning'" size="small" effect="plain">
            {{ row.type === 'document' ? '文档审核' : '申请审核' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="target_name" label="审核对象" min-width="180" show-overflow-tooltip />
      <el-table-column label="审核结果" width="100" align="center">
        <template #default="{ row }">
          <el-tag :type="row.action === 'approved' ? 'success' : 'danger'" size="small">
            {{ row.action === 'approved' ? '已通过' : '已拒绝' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="审核时间" width="180" align="center">
        <template #default="{ row }">
          <span class="time-text">{{ formatTime(row.review_time) }}</span>
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
        @change="fetchHistory"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { reviewApi } from '@/api/review'
import { adminApi } from '@/api/admin'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const isSuperAdmin = computed(() => auth.isSuperAdmin)

const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const keyword = ref('')
const departments = ref([])
const selectedDepartmentId = ref(null)
let searchTimer = null

onMounted(async () => {
  if (isSuperAdmin.value) {
    await fetchDepartments()
  }
  fetchHistory()
})

async function fetchDepartments() {
  try {
    const res = await adminApi.getDepartments()
    if (Array.isArray(res)) {
      departments.value = res
    } else if (res && res.items) {
      departments.value = res.items
    }
  } catch (e) {
    // handled
  }
}

function onDepartmentChange() {
  page.value = 1
  fetchHistory()
}

async function fetchHistory() {
  loading.value = true
  try {
    const params = {
      page: page.value,
      page_size: pageSize.value,
      keyword: keyword.value || undefined
    }
    if (isSuperAdmin.value && selectedDepartmentId.value) {
      params.department_id = selectedDepartmentId.value
    }
    const res = await reviewApi.getReviewHistory(params)
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

function formatTime(ts) {
  if (!ts) return '-'
  try { return new Date(ts).toLocaleString('zh-CN') } catch { return ts }
}

function onSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    page.value = 1
    fetchHistory()
  }, 300)
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
</style>