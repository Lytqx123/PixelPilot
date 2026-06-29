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
        <el-select
          v-if="isSuperAdmin && departments.length > 0"
          v-model="selectedDepartmentId"
          placeholder="按部门筛选"
          clearable
          class="toolbar-select"
          @change="onDepartmentChange"
        >
          <el-option label="全部部门" :value="null" />
          <el-option v-for="d in departments" :key="d.id" :label="d.name" :value="d.id" />
        </el-select>
      </div>
      <div class="toolbar-right">
        <el-button type="primary" round @click="$router.push('/documents/upload')">
          <el-icon><Upload /></el-icon>
          上传文档
        </el-button>
      </div>
    </div>

    <div class="doc-grid" v-loading="loading">
      <div v-if="items.length === 0 && !loading" class="doc-empty">
        <el-icon :size="48" color="var(--color-text-disabled)"><Document /></el-icon>
        <p>暂无文档</p>
      </div>
      <div v-for="row in items" :key="row.id" class="doc-card">
        <!-- 卡片头部:格式图标 -->
        <div class="card-header">
          <div class="card-format-icon" :class="getFormatClass(row.format)">
            <span class="format-text">{{ row.format || '?' }}</span>
          </div>
        </div>

        <!-- 卡片主体 -->
        <div class="card-body">
          <!-- 标题行 -->
          <h3 class="card-title" :title="row.name">{{ row.name }}</h3>

          <!-- 标签行 -->
          <div class="card-tags">
            <el-tag size="small" :type="row.status === 1 ? 'success' : row.status === 0 ? 'warning' : 'danger'" effect="plain" round>
              {{ row.status_text || (row.status === 1 ? '已通过' : row.status === 0 ? '待审核' : '已拒绝') }}
            </el-tag>
            <el-icon
              v-if="favoriteIds.has(row.id)"
              class="card-fav-icon"
              color="var(--color-warning)"
              :size="16"
            ><StarFilled /></el-icon>
            <el-tag v-if="row.department_name" size="small" type="primary" effect="plain" round>{{ row.department_name }}</el-tag>
            <el-tag v-if="row.is_public_to_all" size="small" type="success" effect="dark" round>全员可见</el-tag>
            <el-tag
              v-else
              size="small"
              :type="row.access_mode === 'department_public' ? 'success' : 'warning'"
              effect="plain"
              round
            >
              {{ row.access_mode_text || (row.access_mode === 'department_public' ? '部门内公开' : '需申请') }}
            </el-tag>
          </div>

          <!-- 元信息行 -->
          <div class="card-meta">
            <span class="meta-item">
              <el-icon :size="13"><User /></el-icon>
              {{ row.uploader_name || '-' }}
            </span>
            <span class="meta-item">
              <el-icon :size="13"><Clock /></el-icon>
              {{ formatTime(row.created_at) }}
            </span>
            <span v-if="row.permission_expires_at" class="meta-item" :class="{ 'expires-warn': isExpiringSoon(row.permission_expires_at) }">
              <el-icon :size="13"><Timer /></el-icon>
              授权至 {{ formatTime(row.permission_expires_at) }}
            </span>
          </div>
        </div>

        <!-- 卡片操作 -->
        <div class="card-footer">
          <el-button
            v-if="isViewableFormat(row.format) && row.can_view"
            size="small" text type="primary"
            @click="handleAction('view', row)"
          >
            <el-icon><View /></el-icon> 查看
          </el-button>
          <el-button
            v-if="row.can_download"
            size="small" text type="success"
            @click="handleAction('download', row)"
          >
            <el-icon><Download /></el-icon> 下载
          </el-button>
          <el-button
            v-if="!row.can_download && !row.can_view && !row.has_pending_application"
            size="small" text type="warning"
            @click="handleAction('apply', row)"
          >
            <el-icon><Lock /></el-icon> 申请
          </el-button>
          <el-button
            v-if="!row.can_download && !row.can_view && row.has_pending_application"
            size="small" text type="info"
            disabled
          >
            <el-icon><Loading /></el-icon> 审核中
          </el-button>
          <el-popover placement="bottom" :width="380" trigger="click">
            <template #reference>
              <el-button size="small" text type="primary">
                <el-icon><Collection /></el-icon>
                标签
              </el-button>
            </template>
            <div class="tag-popover">
              <div v-if="getTagsByCategory(row.tags).length === 0" class="tag-empty-text">
                <span class="empty-text">暂无数据标签</span>
              </div>
              <div v-for="catGroup in getTagsByCategory(row.tags)" :key="catGroup.category_id" class="tag-row">
                <span class="tag-label" :style="{ color: getTagColor(catGroup.color) }">
                  <span class="tag-dot" :style="{ backgroundColor: getTagColor(catGroup.color) }"></span>
                  {{ catGroup.category_name }}：
                </span>
                <div class="tag-list-inline">
                  <el-tag v-for="t in catGroup.tags" :key="t.id" size="small" :type="catGroup.color" class="inline-tag">{{ t.name }}</el-tag>
                </div>
              </div>
              <div v-if="isReviewerOrAdmin" class="tag-popover-footer">
                <el-button size="small" type="primary" link @click="openEditTagsDialog(row)">编辑标签</el-button>
              </div>
            </div>
          </el-popover>
          <el-dropdown trigger="click" @command="(cmd) => handleAction(cmd, row)" class="card-more">
            <el-button size="small" text>
              <el-icon><MoreFilled /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="favorite" v-if="!favoriteIds.has(row.id)" icon="Star">收藏</el-dropdown-item>
                <el-dropdown-item command="unfavorite" v-else icon="StarFilled">取消收藏</el-dropdown-item>
                <el-dropdown-item v-if="isReviewerOrAdmin && !isSuperAdmin" command="set_access_mode" icon="Setting" divided>设置访问模式</el-dropdown-item>
                <el-dropdown-item v-if="isReviewerOrAdmin && !isSuperAdmin && !row.is_public_to_all" command="grant" icon="UserFilled">批量授权</el-dropdown-item>
                <el-dropdown-item v-if="authStore.isAdmin" command="delete" icon="Delete" divided>
                  <span class="danger">删除文档</span>
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>
    </div>

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


    <!-- 批量授权对话框 -->
    <el-dialog v-model="batchGrantVisible" title="批量授权" width="640px">
      <el-form :model="batchGrantForm" label-width="100px">
        <el-form-item label="目标文档">
          <el-tag>{{ currentGrantDoc?.name || '' }}</el-tag>
        </el-form-item>

        <el-divider content-position="left">
          <span style="font-weight: 600; color: #606266;">选择授权对象（满足任一条件即可）</span>
        </el-divider>

        <el-form-item label="按角色">
          <el-select v-model="batchGrantForm.role_codes" multiple placeholder="选择角色（可多选）" style="width: 100%">
            <el-option v-for="r in batchGrantableRoles" :key="r.role_code" :label="r.role_name" :value="r.role_code" />
          </el-select>
        </el-form-item>

        <el-divider content-position="left">
          <span style="font-weight: 600; color: #606266;">按数据标签筛选</span>
        </el-divider>

        <div v-if="tagCategories.length === 0" style="text-align: center; padding: 10px; color: #94a3b8; margin-bottom: 18px;">
          暂无数据标签
        </div>
        <el-form-item v-for="cat in tagCategories" :key="cat.id" :label="cat.name">
          <el-select v-model="batchGrantForm.tag_ids" multiple :placeholder="`选择${cat.name}（可多选）`" style="width: 100%" collapse-tags collapse-tags-tooltip>
            <el-option v-for="t in cat.tags" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
        </el-form-item>

        <el-form-item label="指定员工">
          <el-select v-model="batchGrantForm.user_ids" multiple filterable remote reserve-keyword :remote-method="searchBatchUsers" :loading="batchUserSearching" placeholder="按ID或姓名搜索（可多选）" style="width: 100%">
            <el-option v-for="u in batchUserOptions" :key="u.id" :label="`${u.real_name || u.username} (${u.username})`" :value="u.id" />
          </el-select>
        </el-form-item>

        <el-divider content-position="left">
          <span style="font-weight: 600; color: #606266;">授权设置</span>
        </el-divider>

        <el-form-item label="授权类型">
          <span style="color: #606266;">查看并下载（指定员工默认拥有查看与下载权限）</span>
        </el-form-item>

        <el-form-item label="有效期">
          <el-date-picker
            v-model="batchGrantForm.expires_at"
            type="datetime"
            placeholder="选择到期时间（可选）"
            style="width: 100%"
          />
        </el-form-item>

        <el-form-item label=" ">
          <el-button :loading="batchPreviewLoading" type="success" @click="previewBatchGrantUsers">
            <el-icon><Search /></el-icon>
            预览匹配员工
          </el-button>
          <span style="margin-left: 12px; color: #67c23a; font-size: 13px;" v-if="batchPreviewUsers.length > 0">
            共 {{ batchPreviewUsers.length }} 名员工将被授权
          </span>
          <span style="margin-left: 12px; color: #f56c6c; font-size: 13px;" v-else-if="batchPreviewTried && batchPreviewUsers.length === 0">
            未匹配到任何员工，请调整条件
          </span>
        </el-form-item>

        <el-form-item v-if="batchPreviewUsers.length > 0" label="匹配列表">
          <div class="preview-table-wrap">
            <el-table :data="batchPreviewUsers.slice(0, 30)" size="small" border max-height="240px">
              <el-table-column prop="real_name" label="姓名" width="100" show-overflow-tooltip />
              <el-table-column prop="username" label="账号" width="140" show-overflow-tooltip />
              <el-table-column prop="role_code" label="角色" width="110" show-overflow-tooltip />
              <el-table-column prop="department_name" label="部门" show-overflow-tooltip />
            </el-table>
            <div v-if="batchPreviewUsers.length > 30" class="preview-more-hint">
              还有 {{ batchPreviewUsers.length - 30 }} 名员工未展示...
            </div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="batchGrantVisible = false">取消</el-button>
        <el-button type="primary" :loading="batchGranting" @click="submitBatchGrant">确认授权</el-button>
      </template>
    </el-dialog>

    <!-- 访问模式设置对话框 -->
    <el-dialog v-model="setAccessModeVisible" title="设置文档访问模式" width="480px">
      <el-form label-width="100px">
        <el-form-item label="文档名称">
          <el-tag>{{ currentAccessModeDoc?.name || '' }}</el-tag>
        </el-form-item>
        <el-form-item label="当前模式">
          <el-tag
            :type="(accessModeForm.current_mode === 'department_public') ? 'success' : 'warning'"
            effect="plain"
          >
            {{ accessModeForm.current_mode === 'department_public' ? '部门内公开' : '需申请访问' }}
          </el-tag>
        </el-form-item>
        <el-form-item label="设置为">
          <el-radio-group v-model="accessModeForm.new_mode">
            <el-radio label="department_public">部门内公开</el-radio>
            <el-radio label="apply_required">需申请访问</el-radio>
          </el-radio-group>
        </el-form-item>
        <div v-if="accessModeForm.new_mode === 'department_public'" class="mode-hint">
          <el-icon><InfoFilled /></el-icon>
          <span>同部门所有员工可直接查看和下载此文档</span>
        </div>
        <div v-else class="mode-hint">
          <el-icon><InfoFilled /></el-icon>
          <span>同部门普通员工需申请后才能访问，管理员/审核员可直接访问</span>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="setAccessModeVisible = false">取消</el-button>
        <el-button type="primary" :loading="accessModeLoading" @click="submitSetAccessMode">确认</el-button>
      </template>
    </el-dialog>

    <!-- 申请访问对话框 -->
    <el-dialog v-model="applyDialogVisible" title="申请文档访问权限" width="500px">
      <el-form label-width="100px">
        <el-alert
          type="info"
          :closable="false"
          title="请选择审核员并说明申请原因，完成后提交审核"
          style="margin-bottom: 16px"
        />
        <el-form-item label="审核员">
          <el-select
            v-model="applyForm.reviewer_ids"
            multiple
            placeholder="请选择本部门的审核员/管理员（可多选）"
            style="width: 100%"
          >
            <el-option
              v-for="r in reviewers"
              :key="r.id"
              :label="`${r.real_name || r.username}（${r.role_name}）`"
              :value="r.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="申请原因">
          <el-input
            v-model="applyForm.reason"
            type="textarea"
            :rows="3"
            placeholder="请说明申请访问该文档的原因"
            maxlength="500"
            show-word-limit
          />
        </el-form-item>
        <el-form-item label="期望时长">
          <el-select v-model="applyForm.expected_hours" placeholder="请选择期望授权时长" style="width: 100%">
            <el-option label="4 小时" :value="4" />
            <el-option label="8 小时" :value="8" />
            <el-option label="24 小时（1天）" :value="24" />
            <el-option label="72 小时（3天）" :value="72" />
            <el-option label="168 小时（7天）" :value="168" />
            <el-option label="永久（由审核员决定）" :value="0" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="applyDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="applying" @click="submitApply">提交申请</el-button>
      </template>
    </el-dialog>

    <!-- 标签管理对话框 -->
    <el-dialog v-model="editTagsDialogVisible" title="标签管理" width="600px" @close="resetEditTagsState">
      <el-form label-width="100px">
        <el-form-item label="文档名称">
          <el-tag>{{ currentEditDoc?.name || '' }}</el-tag>
        </el-form-item>

        <template v-if="!isEditingTags">
          <el-form-item v-for="catGroup in getTagsByCategory(currentEditDoc?.tags || [])" :key="catGroup.category_id" :label="catGroup.category_name">
            <div class="tag-display">
              <el-tag v-for="t in catGroup.tags" :key="t.id" size="small" :type="catGroup.color" style="margin-right: 6px; margin-bottom: 4px">{{ t.name }}</el-tag>
              <span v-if="catGroup.tags.length === 0" style="color: #94a3b8">暂无</span>
            </div>
          </el-form-item>
          <el-form-item v-if="getTagsByCategory(currentEditDoc?.tags || []).length === 0" label="数据标签">
            <span style="color: #94a3b8">暂无数据标签</span>
          </el-form-item>
        </template>

        <template v-else>
          <div v-if="tagCategories.length === 0" style="text-align: center; padding: 20px; color: #94a3b8;">
            暂无数据标签，请先在系统设置中配置
          </div>
          <el-form-item v-for="cat in tagCategories" :key="cat.id" :label="cat.name">
            <el-select
              v-model="editTagsForm.tag_ids"
              multiple
              filterable
              :placeholder="`选择${cat.name}（可多选）`"
              style="width: 100%"
              collapse-tags
              collapse-tags-tooltip
            >
              <el-option
                v-for="t in cat.tags"
                :key="t.id"
                :label="t.name"
                :value="t.id"
              />
            </el-select>
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <template v-if="!isEditingTags">
          <el-button @click="editTagsDialogVisible = false">关闭</el-button>
          <el-button type="primary" @click="isEditingTags = true" v-if="tagCategories.length > 0">修改</el-button>
        </template>
        <template v-else>
          <el-button @click="cancelEditTags">取消</el-button>
          <el-button type="primary" :loading="editTagsLoading" @click="submitEditTags">保存</el-button>
        </template>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { documentsApi } from '@/api/documents'
import { adminApi } from '@/api/admin'
import { useAuthStore } from '@/stores/auth'
import {
  Star, StarFilled, Collection, Operation, ArrowDown,
  View, Download, Lock, UserFilled, Delete, Setting, InfoFilled, Upload, Search,
  Document, User, Clock, Timer, MoreFilled, Loading
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const VIEWABLE_FORMATS = new Set(['PDF', 'MD', 'TXT', 'PNG', 'JPG', 'JPEG'])

const colorMap = {
  primary: '#0ea5e9',
  success: '#10b981',
  warning: '#f59e0b',
  danger: '#ef4444',
  info: '#6366f1',
}

function getTagColor(color) {
  return colorMap[color] || colorMap.primary
}

function getTagsByCategory(tags) {
  if (!tags || !Array.isArray(tags) || tags.length === 0) return []
  const groups = {}
  tags.forEach(t => {
    const catId = t.category_id
    if (!groups[catId]) {
      groups[catId] = {
        category_id: catId,
        category_name: t.category_name || '未分类',
        color: t.color || 'primary',
        tags: []
      }
    }
    groups[catId].tags.push(t)
  })
  return Object.values(groups)
}

function isViewableFormat(format) {
  if (!format) return false
  return VIEWABLE_FORMATS.has(format.toUpperCase())
}

function formatTime(ts) {
  if (!ts) return '-'
  try { return new Date(ts).toLocaleString('zh-CN') } catch { return ts }
}

function isExpiringSoon(expiresAt) {
  if (!expiresAt) return false
  try {
    const diff = new Date(expiresAt).getTime() - Date.now()
    return diff > 0 && diff < 24 * 60 * 60 * 1000 // 24小时内到期标红
  } catch { return false }
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

const authStore = useAuthStore()
const canDirectAccess = computed(() => authStore.isAdmin || authStore.isReviewer)
const isReviewerOrAdmin = computed(() => authStore.isReviewer || authStore.isAdmin)
// isAdmin 已包含 SUPER_ADMIN 和 ADMIN，无需重复定义别名变量
const isSuperAdmin = computed(() => authStore.isSuperAdmin)

const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const keyword = ref('')
const selectedDepartmentId = ref(null)
const departments = ref([])
const loading = ref(false)
const applying = ref(false)
const currentGrantDoc = ref(null)
let searchTimer = null

const applyDialogVisible = ref(false)
const applyForm = reactive({ document_id: null, reason: '', reviewer_ids: [], expected_hours: 24 })
const reviewers = ref([])

const favoriteIds = ref(new Set())

const editTagsDialogVisible = ref(false)
const editTagsLoading = ref(false)
const currentEditDoc = ref(null)
const tagCategories = ref([])
const editTagsForm = reactive({
  tag_ids: [],
})

const setAccessModeVisible = ref(false)
const accessModeLoading = ref(false)
const currentAccessModeDoc = ref(null)
const accessModeForm = reactive({
  current_mode: 'department_public',
  new_mode: 'department_public',
})

onMounted(async () => {
  await Promise.all([
    fetchDepartments(),
    fetchDataTags()
  ])
  fetchDocuments()
  fetchFavoriteIds()
  window.addEventListener('pixelpulse:403-apply', handle403ApplyEvent)
})
onUnmounted(() => {
  window.removeEventListener('pixelpulse:403-apply', handle403ApplyEvent)
})

async function fetchDepartments() {
  if (!isSuperAdmin.value) {
    departments.value = []
    return
  }
  try {
    const res = await documentsApi.getDepartments()
    if (Array.isArray(res)) {
      departments.value = res
    } else if (res && Array.isArray(res.items)) {
      departments.value = res.items
    } else if (res && Array.isArray(res.departments)) {
      departments.value = res.departments
    }
  } catch {
    departments.value = []
  }
}

function onDepartmentChange() {
  page.value = 1
  fetchDocuments()
}

async function fetchReviewers() {
  try {
    const res = await adminApi.getReviewers()
    reviewers.value = (res && res.items) ? res.items : []
  } catch {
    reviewers.value = []
  }
}

async function handle403ApplyEvent(e) {
  const { document_id, document_name } = e.detail || {}
  if (document_id) {
    applyForm.document_id = document_id
    applyForm.reason = `通过"${document_name || '文档'}"的访问权限提示发起申请`
    applyForm.reviewer_ids = []
    applyForm.expected_hours = 24
    await fetchReviewers()
    applyDialogVisible.value = true
  }
}

async function fetchFavoriteIds() {
  try {
    const res = await documentsApi.getFavorites({ page_size: 1000 })
    const favDocs = res.items || []
    const ids = new Set()
    favDocs.forEach(f => ids.add(f.document_id))
    favoriteIds.value = ids
  } catch {
    // ignore
  }
}

async function fetchDocuments() {
  loading.value = true
  try {
    const params = {
      page: page.value,
      page_size: pageSize.value,
      keyword: keyword.value || undefined,
    }
    if (isSuperAdmin.value && selectedDepartmentId.value != null) {
      params.department_id = selectedDepartmentId.value
    }
    const res = await documentsApi.getDocuments(params)
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

async function handleView(row) {
  try {
    const url = documentsApi.getViewDocumentUrl(row.id)
    window.open(url, '_blank')
    ElMessage.success('正在打开文档')
  } catch (e) {
    ElMessage.warning('查看失败，请检查权限')
  }
}

async function handleDownload(row) {
  try {
    const blob = await documentsApi.downloadDocument(row.id)
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = row.name || 'document'
    link.click()
    window.URL.revokeObjectURL(url)
    ElMessage.success('下载成功')
  } catch (e) {
    // handled
  }
}

async function handleApply(row) {
  applyForm.document_id = row.id
  applyForm.reason = ''
  applyForm.reviewer_ids = []
  applyForm.expected_hours = 24
  await fetchReviewers()
  applyDialogVisible.value = true
}

const batchGrantVisible = ref(false)
const batchGranting = ref(false)
const batchUserSearching = ref(false)
const batchUserOptions = ref([])
const batchPreviewLoading = ref(false)
const batchPreviewTried = ref(false)
const batchPreviewUsers = ref([])
const batchGrantableRoles = ref([])
const batchGrantForm = reactive({
  role_codes: [],
  tag_ids: [],
  user_ids: [],
  permission_type: 'download',
  expires_at: null,
})

async function fetchDataTags() {
  try {
    const res = await documentsApi.getAllDataTags()
    tagCategories.value = res || []
  } catch {
    tagCategories.value = []
  }
}
let batchSearchTimer = null

async function fetchBatchGrantableRoles() {
  try {
    const res = await adminApi.getGrantableRoles()
    if (res && res.items) {
      batchGrantableRoles.value = res.items
    }
  } catch { /* ignore */ }
}

async function openBatchGrantDialog(row) {
  currentGrantDoc.value = row
  batchGrantForm.role_codes = []
  batchGrantForm.tag_ids = []
  batchGrantForm.user_ids = []
  batchGrantForm.permission_type = 'download'
  batchGrantForm.expires_at = null
  batchUserOptions.value = []
  batchPreviewUsers.value = []
  batchPreviewTried.value = false
  await Promise.all([fetchDataTags(), fetchBatchGrantableRoles()])
  batchGrantVisible.value = true
}

async function openSetAccessModeDialog(row) {
  currentAccessModeDoc.value = row
  const currentMode = row.access_mode || 'department_public'
  accessModeForm.current_mode = currentMode
  accessModeForm.new_mode = currentMode
  setAccessModeVisible.value = true
}

async function submitSetAccessMode() {
  if (!currentAccessModeDoc.value) return
  accessModeLoading.value = true
  try {
    await documentsApi.setAccessMode(currentAccessModeDoc.value.id, {
      access_mode: accessModeForm.new_mode,
    })
    ElMessage.success('访问模式已更新')
    setAccessModeVisible.value = false
    const idx = items.value.findIndex(i => i.id === currentAccessModeDoc.value.id)
    if (idx !== -1) {
      items.value[idx].access_mode = accessModeForm.new_mode
      items.value[idx].access_mode_text = accessModeForm.new_mode === 'department_public' ? '部门内公开' : '需申请访问'
    }
  } catch (e) {
    ElMessage.error('访问模式设置失败')
  } finally {
    accessModeLoading.value = false
  }
}

async function searchBatchUsers(query) {
  if (!query || !query.trim()) { batchUserOptions.value = []; return }
  batchUserSearching.value = true
  clearTimeout(batchSearchTimer)
  batchSearchTimer = setTimeout(async () => {
    try {
      const res = await adminApi.getUsers({ page_size: 20, keyword: query.trim() })
      batchUserOptions.value = (res.items || []).filter(u => u.role_code !== 'SUPER_ADMIN' && u.role_code !== 'ADMIN')
    } catch { batchUserOptions.value = [] } finally { batchUserSearching.value = false }
  }, 300)
}

function buildBatchGrantFilters() {
  const user_filters = {}
  if (batchGrantForm.role_codes.length > 0) user_filters.role_codes = batchGrantForm.role_codes
  if (batchGrantForm.tag_ids.length > 0) user_filters.tag_ids = batchGrantForm.tag_ids
  if (batchGrantForm.user_ids.length > 0) user_filters.user_ids = batchGrantForm.user_ids
  return user_filters
}

async function previewBatchGrantUsers() {
  if (!currentGrantDoc.value) return
  const user_filters = buildBatchGrantFilters()
  if (Object.keys(user_filters).length === 0) {
    ElMessage.warning('请至少选择一种筛选条件')
    return
  }
  batchPreviewLoading.value = true
  batchPreviewTried.value = true
  try {
    const request = {
      document_ids: [currentGrantDoc.value.id],
      user_filters,
      permission_type: batchGrantForm.permission_type,
    }
    if (batchGrantForm.expires_at) {
      request.expires_at = batchGrantForm.expires_at.toISOString()
    }
    const res = await adminApi.previewBatchGrant(request)
    batchPreviewUsers.value = (res && res.users) ? res.users : []
    if (batchPreviewUsers.value.length === 0) {
      ElMessage.warning('当前条件未匹配到员工，请调整后再授权范围')
    }
  } catch { /* handled */ } finally { batchPreviewLoading.value = false }
}

async function submitBatchGrant() {
  if (!currentGrantDoc.value) return
  const user_filters = buildBatchGrantFilters()
  if (Object.keys(user_filters).length === 0) {
    ElMessage.warning('请至少选择一种授权条件')
    return
  }
  if (!batchPreviewTried.value) {
    const confirmRes = await ElMessageBox.confirm(
      '您未预览匹配员工，是否继续授权？', '提示', {
        confirmButtonText: '继续授权',
        cancelButtonText: '取消',
        type: 'warning',
      }
    ).catch(() => 'cancel')
    if (confirmRes !== 'confirm') return
  } else if (batchPreviewUsers.value.length === 0) {
    ElMessage.warning('当前条件未匹配到任何员工，请调整条件')
    return
  } else {
    const confirmRes = await ElMessageBox.confirm(
      `将为 ${batchPreviewUsers.value.length} 名员工授权访问此文档，是否确认？`,
      '请确认',
      {
        confirmButtonText: '确认授权',
        cancelButtonText: '取消',
        type: 'info',
      }
    ).catch(() => 'cancel')
    if (confirmRes !== 'confirm') return
  }
  batchGranting.value = true
  try {
    const request = {
      document_ids: [currentGrantDoc.value.id],
      user_filters,
      permission_type: batchGrantForm.permission_type,
    }
    if (batchGrantForm.expires_at) {
      request.expires_at = batchGrantForm.expires_at.toISOString()
    }
    const res = await adminApi.batchGrant(request)
    const granted = res?.granted_count || 0
    const updated = res?.updated_count || 0
    const skipped = res?.skipped_count || 0
    let msg = `授权成功：新增 ${granted} 条`
    if (updated > 0) msg += `，更新 ${updated} 条`
    if (skipped > 0) msg += `，跳过 ${skipped} 条已有授权`
    ElMessage.success(msg)
    batchGrantVisible.value = false
  } catch { /* handled */ } finally { batchGranting.value = false }
}

async function handleAction(cmd, row) {
  switch (cmd) {
    case 'favorite':
      handleFavorite(row)
      break
    case 'unfavorite':
      handleUnfavorite(row)
      break
    case 'view':
      handleView(row)
      break
    case 'download':
      handleDownload(row)
      break
    case 'apply':
      handleApply(row)
      break
    case 'grant':
      openBatchGrantDialog(row)
      break
    case 'set_access_mode':
      openSetAccessModeDialog(row)
      break
    case 'delete':
      handleDeleteDoc(row)
      break
  }
}

async function handleDeleteDoc(row) {
  try {
    await ElMessageBox.confirm(
      `确定要永久删除文档 "${row.name}" 吗？此操作不可恢复，将同时删除该文档的所有分块、访问申请和收藏记录。`,
      '确认删除文档',
      { type: 'error', confirmButtonText: '确定删除', cancelButtonText: '取消' }
    )
    await documentsApi.deleteDocument(row.id)
    ElMessage.success('文档已删除')
    fetchDocuments()
  } catch (e) {
    // cancelled
  }
}

async function handleFavorite(row) {
  try {
    await documentsApi.addFavorite(row.id)
    favoriteIds.value = new Set([...favoriteIds.value, row.id])
    ElMessage.success(`「${row.name}」已收藏`)
  } catch {
    // ignored
  }
}

async function handleUnfavorite(row) {
  try {
    await documentsApi.removeFavorite(row.id)
    const next = new Set(favoriteIds.value)
    next.delete(row.id)
    favoriteIds.value = next
    ElMessage.success(`已取消收藏「${row.name}」`)
  } catch {
    // ignore
  }
}

async function submitApply() {
  if (!applyForm.reviewer_ids || applyForm.reviewer_ids.length === 0) {
    ElMessage.warning('请至少选择一名审核员/管理员')
    return
  }
  if (!applyForm.reason.trim()) {
    ElMessage.warning('请填写申请原因')
    return
  }
  applying.value = true
  try {
    await documentsApi.applyAccess(applyForm.document_id, {
      reason: applyForm.reason,
      reviewer_ids: applyForm.reviewer_ids,
      expected_hours: applyForm.expected_hours,
    })
    ElMessage.success('申请已提交，等待审核')
    applyDialogVisible.value = false
  } catch (e) {
    // handled
  } finally {
    applying.value = false
  }
}

const isEditingTags = ref(false)

function resetEditTagsState() {
  isEditingTags.value = false
}

function cancelEditTags() {
  if (currentEditDoc.value) {
    const doc = currentEditDoc.value
    editTagsForm.tag_ids = (doc.tags || []).map(t => t.id)
  }
  isEditingTags.value = false
}

async function openEditTagsDialog(row) {
  isEditingTags.value = false
  currentEditDoc.value = row
  editTagsForm.tag_ids = (row.tags || []).map(t => t.id)
  await fetchDataTags()
  editTagsDialogVisible.value = true
}

async function submitEditTags() {
  if (!currentEditDoc.value) return
  editTagsLoading.value = true
  try {
    const data = {
      tag_ids: editTagsForm.tag_ids
    }
    await documentsApi.updateDocumentTags(currentEditDoc.value.id, data)
    ElMessage.success('标签更新成功')
    editTagsDialogVisible.value = false
    await fetchDocuments()
  } catch (e) {
    ElMessage.error('标签更新失败')
  } finally {
    editTagsLoading.value = false
  }
}
</script>

<style scoped>
.page-view {
  max-width: 1400px;
  margin: 0 auto;
  padding: 20px 24px;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding: 16px 20px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
}

.toolbar-left { display: flex; gap: 10px; align-items: center; }
.toolbar-input { width: 260px; }
.toolbar-select { width: 200px; }
.toolbar-right { display: flex; gap: 10px; }

/* 文档列表（垂直排列） */
.doc-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 200px;
}

.doc-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 60px 20px;
  color: var(--color-text-placeholder);
  font-size: 14px;
}

.doc-card {
  display: flex;
  flex-direction: row;
  align-items: center;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  transition: all 0.25s ease;
  overflow: hidden;
  padding: 14px 16px;
  gap: 16px;
}

.doc-card:hover {
  border-color: #7dd3fc;
  box-shadow: var(--shadow-lg);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  flex-shrink: 0;
}

.card-format-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: var(--radius-md);
  font-size: 11px;
  font-weight: 700;
  color: #ffffff;
  letter-spacing: 0.5px;
}

.format-text {
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

.card-status-area {
  display: none;  /* 状态标签移到 card-body 中显示 */
}

.card-fav-icon {
  cursor: default;
}

.card-body {
  flex: 1;
  min-width: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.card-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0;
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

.card-tag-detail {
  display: inline-flex;
}

.card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 12px;
  color: var(--color-text-secondary);
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.meta-item.expires-warn {
  color: var(--el-color-danger);
  font-weight: 600;
}

.card-footer {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 0;
  border-top: none;
  background: transparent;
  flex-shrink: 0;
}

.card-more {
  margin-left: auto;
}

.danger { color: var(--color-danger); }

/* 标签弹窗 */
.tag-popover { padding: 4px; }
.tag-popover .tag-row { display: flex; align-items: flex-start; gap: 10px; padding: 8px 0; border-bottom: 1px solid var(--color-border-light); }
.tag-popover .tag-row:last-child { border-bottom: none; }
.tag-label { flex-shrink: 0; color: var(--color-text-secondary); font-size: 12px; font-weight: 500; min-width: 60px; display: flex; align-items: center; gap: 4px; }
.tag-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.tag-list-inline { flex: 1; display: flex; flex-wrap: wrap; gap: 6px; line-height: 1.5; }
.inline-tag { margin: 0; }
.empty-text { color: var(--color-text-disabled); font-size: 12px; }
.tag-empty-text { padding: 12px 0; text-align: center; }
.tag-popover-footer { padding-top: 8px; text-align: right; border-top: 1px solid var(--color-border-light); margin-top: 4px; }

.pagination-wrap { display: flex; justify-content: flex-end; padding: 20px 0 0; }
.tag-display { line-height: 32px; }
.mode-hint { display: flex; align-items: flex-start; gap: 6px; color: var(--color-text-regular); background: var(--color-primary-lighter); padding: 10px 12px; border-radius: var(--radius-sm); font-size: 13px; margin-top: -8px; margin-bottom: 12px; }
.mode-hint .el-icon { margin-top: 3px; color: var(--color-primary); }
.preview-table-wrap { width: 100%; }
.preview-more-hint { text-align: center; padding: 8px; color: var(--color-text-secondary); font-size: 12px; background: var(--color-bg-hover); border: 1px solid var(--color-border); border-top: none; }
</style>