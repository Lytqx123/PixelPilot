<template>
  <div class="upload-view">
    <div class="upload-header">
      <h3>文档上传</h3>
      <p class="upload-desc">支持常规文档与工程图纸两类文件，上传后需等待审核入库</p>
    </div>

    <!-- 上传类型切换 -->
    <div class="upload-type-tabs">
      <div
        class="type-tab"
        :class="{ active: uploadType === 'regular' }"
        @click="switchType('regular')"
      >
        <div class="type-tab-icon">
          <el-icon :size="22"><Document /></el-icon>
        </div>
        <div class="type-tab-content">
          <span class="type-tab-title">常规文档</span>
          <small>PDF · DOCX · XLSX · MD · TXT · 图片（OCR）</small>
        </div>
        <div v-if="uploadType === 'regular'" class="type-tab-check">
          <el-icon color="var(--color-primary)"><CircleCheckFilled /></el-icon>
        </div>
      </div>
      <div
        class="type-tab"
        :class="{ active: uploadType === 'cad' }"
        @click="switchType('cad')"
      >
        <div class="type-tab-icon">
          <el-icon :size="22"><DataBoard /></el-icon>
        </div>
        <div class="type-tab-content">
          <span class="type-tab-title">工程图纸</span>
          <small>DWG · DXF（支持大文件）</small>
        </div>
        <div v-if="uploadType === 'cad'" class="type-tab-check">
          <el-icon color="var(--color-primary)"><CircleCheckFilled /></el-icon>
        </div>
      </div>
    </div>

    <!-- 上传区域 -->
    <div class="upload-card">
      <div class="upload-zone" @click="triggerUpload" @dragover.prevent @drop.prevent="handleDrop">
        <input
          ref="fileInput"
          type="file"
          :accept="currentAccept"
          style="display: none"
          @change="handleFileSelect"
        />

        <div v-if="!selectedFile" class="zone-placeholder">
          <el-icon :size="52" color="#7dd3fc"><UploadFilled /></el-icon>
          <p class="zone-title">拖拽文件到此处，或<span class="zone-link">点击选择</span></p>
          <p class="zone-hint">
            {{ uploadType === 'regular'
              ? '支持 PDF、DOCX、XLSX、MD、TXT、CSV、PNG、JPG（图片自动 OCR）'
              : '支持 DWG、DXF 工程图纸格式' }}
          </p>
          <p class="zone-limit">单文件最大 {{ uploadType === 'regular' ? '50MB' : '200MB' }}</p>
        </div>

        <div v-else class="zone-file-preview">
          <div class="file-info">
            <el-icon :size="32" color="var(--color-primary)"><Document /></el-icon>
            <div class="file-detail">
              <span class="file-name">{{ selectedFile.name }}</span>
              <span class="file-size">{{ formatSize(selectedFile.size) }}</span>
            </div>
            <el-button circle text :icon="Close" @click.stop="clearFile" />
          </div>
        </div>
      </div>

      <!-- 数据标签选择（动态分类，可多选） -->
      <div class="tag-section">
        <div class="tag-section-title">
          <el-icon><CollectionTag /></el-icon>
          <span>数据标签（分类后便于检索）</span>
        </div>
        <div v-if="tagCategories.length === 0" class="tag-empty">
          <span>暂无数据标签，请先在系统设置中配置</span>
        </div>
        <div v-else class="tag-grid">
          <div v-for="cat in tagCategories" :key="cat.id" class="tag-group">
            <label>
              <span class="tag-group-dot" :style="{ backgroundColor: getTagColor(cat.color) }"></span>
              {{ cat.name }}
            </label>
            <el-select
              v-model="selectedTagIds"
              :placeholder="`选择${cat.name}（可多选）`"
              multiple
              clearable
              collapse-tags
              collapse-tags-tooltip
              style="width: 100%"
            >
              <el-option
                v-for="t in cat.tags"
                :key="t.id"
                :label="t.name"
                :value="t.id"
              />
            </el-select>
          </div>
        </div>
      </div>

      <!-- 审核员选择 -->
      <div class="reviewer-section">
        <div class="reviewer-section-title">
          <el-icon><UserFilled /></el-icon>
          <span>选择审核员</span>
          <span class="required-mark">*</span>
        </div>
        <el-select
          v-model="selectedReviewerId"
          placeholder="请选择本部门的审核员"
          style="width: 100%"
          :disabled="isPrivileged"
        >
          <el-option
            v-for="reviewer in availableReviewers"
            :key="reviewer.id"
            :label="reviewer.label"
            :value="reviewer.id"
          >
            <span style="float: left">{{ reviewer.name }}</span>
            <span style="float: right; color: var(--el-text-color-secondary); font-size: 13px">
              {{ reviewer.role_name }}
            </span>
          </el-option>
        </el-select>
      </div>

      <div class="upload-actions">
        <el-button
          type="primary"
          size="large"
          :loading="uploading"
          :disabled="!selectedFile"
          @click="handleUpload"
        >
          <el-icon><Upload /></el-icon> 上传并提交审核
        </el-button>
        <el-button size="large" @click="$router.push('/documents')">返回列表</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { documentsApi } from '@/api/documents'
import { adminApi } from '@/api/admin'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'
import { Document, DataBoard, UploadFilled, Upload, Close, CircleCheckFilled, CollectionTag, UserFilled } from '@element-plus/icons-vue'

const router = useRouter()
const authStore = useAuthStore()
const fileInput = ref(null)
const uploading = ref(false)
const selectedFile = ref(null)
const uploadType = ref('regular')
const selectedReviewerId = ref(null)
const availableReviewers = ref([])
const tagCategories = ref([])
const selectedTagIds = ref([])

const isPrivileged = computed(() => authStore.isReviewer || authStore.isAdmin)

const regularAccept = '.pdf,.docx,.xlsx,.md,.txt,.csv,.png,.jpg,.jpeg'
const cadAccept = '.dwg,.dxf'

const currentAccept = computed(() => uploadType.value === 'regular' ? regularAccept : cadAccept)

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

onMounted(async () => {
  try {
    const res = await documentsApi.getAllDataTags()
    tagCategories.value = res || []
  } catch {
    // handled
  }
  
  if (!isPrivileged.value) {
    try {
      const res = await adminApi.getReviewers()
      availableReviewers.value = (res?.items || []).map(r => ({
        id: r.id,
        name: r.real_name || r.username,
        label: `${r.real_name || r.username}（${r.role_name || r.role_code}）`,
        role_name: r.role_name || r.role_code,
      }))
    } catch {
      // handled
    }
  }
})

function switchType(type) {
  uploadType.value = type
  selectedFile.value = null
  if (fileInput.value) fileInput.value.value = ''
}

function triggerUpload() {
  fileInput.value?.click()
}

function handleFileSelect(e) {
  const file = e.target.files?.[0]
  if (file) validateAndSet(file)
}

function handleDrop(e) {
  const file = e.dataTransfer?.files?.[0]
  if (file) validateAndSet(file)
}

function validateAndSet(file) {
  const ext = file.name.split('.').pop()?.toLowerCase()
  const allowed = uploadType.value === 'regular'
    ? ['pdf', 'docx', 'xlsx', 'md', 'txt', 'csv', 'png', 'jpg', 'jpeg']
    : ['dwg', 'dxf']

  if (!allowed.includes(ext)) {
    ElMessage.error(`不支持的文件格式：.${ext}`)
    return
  }

  const maxSize = (uploadType.value === 'regular' ? 50 : 200) * 1024 * 1024
  if (file.size > maxSize) {
    ElMessage.error(`文件大小超过 ${uploadType.value === 'regular' ? '50MB' : '200MB'} 限制`)
    return
  }

  selectedFile.value = file
}

function clearFile() {
  selectedFile.value = null
  if (fileInput.value) fileInput.value.value = ''
}

async function handleUpload() {
  if (!selectedFile.value) {
    ElMessage.warning('请选择文件')
    return
  }

  if (!isPrivileged.value && !selectedReviewerId.value) {
    ElMessage.warning('请选择审核员')
    return
  }

  uploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value)
    formData.append('tag_ids', JSON.stringify(selectedTagIds.value || []))
    formData.append('upload_type', uploadType.value)
    if (selectedReviewerId.value) {
      formData.append('reviewer_id', selectedReviewerId.value)
    }

    const res = await documentsApi.uploadDocument(formData)
    ElMessage.success(res.message || '上传成功')
    router.push('/documents')
  } catch {
    // handled by interceptor
  } finally {
    uploading.value = false
  }
}

function formatSize(bytes) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  let size = bytes
  while (size >= 1024 && i < units.length - 1) {
    size /= 1024
    i++
  }
  return size.toFixed(1) + ' ' + units[i]
}
</script>

<style scoped>
.upload-view {
  max-width: 900px;
  margin: 0 auto;
  padding: 20px 0;
}

.upload-header {
  margin-bottom: 28px;
}

.upload-header h3 {
  font-size: 22px;
  font-weight: 700;
  color: #1e293b;
  margin: 0 0 8px;
  letter-spacing: -0.3px;
}

.upload-desc {
  font-size: 13px;
  color: #64748b;
  margin: 0;
}

/* 类型切换 */
.upload-type-tabs {
  display: flex;
  gap: 14px;
  margin-bottom: 24px;
}

.type-tab {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px 20px;
  background: #ffffff;
  border: 2px solid #e2e8f0;
  border-radius: 14px;
  cursor: pointer;
  color: #64748b;
  transition: all 0.25s ease;
  position: relative;
}

.type-tab:hover {
  border-color: #7dd3fc;
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(14, 165, 233, 0.08);
}

.type-tab.active {
  border-color: var(--color-primary);
  background: linear-gradient(135deg, #f0f9ff, #ffffff);
  box-shadow: 0 6px 20px rgba(14, 165, 233, 0.12);
}

.type-tab-icon {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f1f5f9;
  border-radius: 12px;
  color: #64748b;
  flex-shrink: 0;
  transition: all 0.25s ease;
}

.type-tab.active .type-tab-icon {
  background: var(--color-primary);
  color: #ffffff;
  box-shadow: 0 4px 12px rgba(14, 165, 233, 0.2);
}

.type-tab-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
}

.type-tab-title {
  font-size: 15px;
  font-weight: 600;
  color: #334155;
}

.type-tab.active .type-tab-title {
  color: var(--color-primary-active);
}

.type-tab small {
  font-size: 12px;
  color: #94a3b8;
  line-height: 1.4;
}

.type-tab-check {
  flex-shrink: 0;
}

/* 上传卡片 */
.upload-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  padding: 32px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.upload-zone {
  border: 2px dashed #cbd5e1;
  border-radius: 16px;
  padding: 48px 24px;
  text-align: center;
  cursor: pointer;
  transition: all 0.25s ease;
  margin-bottom: 28px;
  background: #f8fafc;
}

.upload-zone:hover {
  border-color: #38bdf8;
  background: #f0f9ff;
  transform: scale(1.005);
}

.zone-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}

.zone-title {
  font-size: 15px;
  color: #475569;
  margin: 0;
  font-weight: 500;
}

.zone-link {
  color: var(--color-primary);
  cursor: pointer;
  font-weight: 600;
  text-decoration: none;
  border-bottom: 1px dashed #7dd3fc;
  padding-bottom: 1px;
}

.zone-hint {
  font-size: 12px;
  color: #94a3b8;
  margin: 0;
  line-height: 1.6;
  max-width: 500px;
}

.zone-limit {
  font-size: 11px;
  color: #cbd5e1;
  margin: 4px 0 0;
  padding: 4px 12px;
  background: #ffffff;
  border-radius: 8px;
}

.zone-file-preview {
  padding: 0;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 18px 22px;
  background: linear-gradient(135deg, #f0f9ff, #e0f2fe);
  border: 1px solid #7dd3fc;
  border-radius: 14px;
}

.file-detail {
  flex: 1;
  display: flex;
  flex-direction: column;
  text-align: left;
}

.file-name {
  font-size: 15px;
  color: #1e293b;
  font-weight: 600;
}

.file-size {
  font-size: 12px;
  color: #64748b;
  margin-top: 4px;
}

/* 标签区 */
.tag-section {
  padding: 20px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  margin-bottom: 24px;
}

.tag-section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: #475569;
  margin-bottom: 14px;
}

.tag-empty {
  text-align: center;
  padding: 20px;
  color: #94a3b8;
  font-size: 13px;
}

.tag-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
}

.tag-group {
  min-width: 0;
}

.tag-group label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #64748b;
  margin-bottom: 8px;
  font-weight: 500;
}

.tag-group-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

/* 审核员选择 */
.reviewer-section {
  padding: 20px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  margin-bottom: 24px;
}

.reviewer-section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: #475569;
  margin-bottom: 14px;
}

.required-mark {
  color: #ef4444;
  font-size: 14px;
}

/* 操作区 */
.upload-actions {
  display: flex;
  gap: 12px;
  padding-top: 20px;
  border-top: 1px solid #f1f5f9;
  justify-content: flex-end;
}

.upload-actions :deep(.el-button) {
  padding: 12px 28px;
  font-size: 14px;
  font-weight: 500;
  border-radius: 10px;
}
</style>
