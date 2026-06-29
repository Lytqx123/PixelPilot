<template>
  <div class="page-view">
    <div class="page-header">
      <h3>系统设置</h3>
      <p class="page-desc">管理数据标签、部门和角色 — 所有更改将全局生效</p>
    </div>

    <!-- ========== 数据标签管理 ========== -->
    <el-card class="section-card" v-if="isSuperAdmin">
      <template #header>
        <div class="card-header">
          <el-icon><Collection /></el-icon>
          <span>数据标签管理</span>
          <el-tag size="small" effect="plain" type="info">
            {{ totalCategoryCount }} 个分类 / {{ totalDataTagCount }} 个标签
          </el-tag>
        </div>
      </template>

      <div class="tag-manage-layout">
        <!-- 左侧：标签分类列表 -->
        <div class="category-panel">
          <div class="panel-toolbar">
            <span class="panel-title">标签分类</span>
            <el-button type="primary" size="small" round @click="openCategoryCreateDialog">
              <el-icon><Plus /></el-icon>新建分类
            </el-button>
          </div>
          <div v-loading="categoryLoading" class="category-list">
            <div
              v-for="cat in categoryList"
              :key="cat.id"
              class="category-item"
              :class="{ active: selectedCategory?.id === cat.id }"
              @click="selectCategory(cat)"
            >
              <div class="cat-main">
                <el-tag :type="cat.color" size="small" effect="dark" class="cat-name-tag">
                  {{ cat.name }}
                </el-tag>
                <span class="cat-code code-text">{{ cat.code }}</span>
                <el-tag v-if="cat.is_system" size="small" type="info" effect="plain">系统</el-tag>
              </div>
              <div class="cat-meta">
                <span class="tag-count">{{ cat.tag_count }} 个标签</span>
                <div class="cat-actions" @click.stop>
                  <el-button size="small" type="primary" link @click="openCategoryEditDialog(cat)">
                    <el-icon><Edit /></el-icon>
                  </el-button>
                  <el-button
                    size="small"
                    type="danger"
                    link
                    :disabled="cat.is_system"
                    @click="handleDeleteCategory(cat)"
                  >
                    <el-icon><Delete /></el-icon>
                  </el-button>
                </div>
              </div>
            </div>
            <el-empty v-if="!categoryLoading && categoryList.length === 0" description="暂无分类" :image-size="80" />
          </div>
        </div>

        <!-- 右侧：选中分类下的标签列表 -->
        <div class="tag-panel">
          <template v-if="selectedCategory">
            <div class="panel-toolbar">
              <div class="panel-title-wrap">
                <span class="panel-title">{{ selectedCategory.name }}</span>
                <span v-if="selectedCategory.description" class="panel-desc">{{ selectedCategory.description }}</span>
              </div>
              <el-button type="primary" size="small" round @click="openDataTagCreateDialog">
                <el-icon><Plus /></el-icon>新建标签
              </el-button>
            </div>
            <el-table :data="currentCategoryTags" border stripe v-loading="tagLoading" class="admin-table">
              <el-table-column prop="name" label="标签名称" min-width="200">
                <template #default="{ row }">
                  <el-tag :type="selectedCategory.color" effect="light" size="default">{{ row.name }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="description" label="描述" min-width="180" show-overflow-tooltip>
                <template #default="{ row }">
                  <span v-if="row.description">{{ row.description }}</span>
                  <span v-else class="muted-text">—</span>
                </template>
              </el-table-column>
              <el-table-column prop="created_at" label="创建时间" width="170" align="center">
                <template #default="{ row }">
                  <span class="code-text">{{ formatTagTime(row.created_at) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="160" fixed="right" align="center">
                <template #default="{ row }">
                  <el-button size="small" type="primary" effect="plain" round @click="openDataTagEditDialog(row)">
                    <el-icon><Edit /></el-icon>编辑
                  </el-button>
                  <el-button size="small" type="danger" effect="plain" round @click="handleDeleteDataTag(row)">
                    <el-icon><Delete /></el-icon>删除
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
            <el-empty v-if="!tagLoading && currentCategoryTags.length === 0" description="该分类下暂无标签" :image-size="100" />
          </template>
          <el-empty v-else description="请从左侧选择一个标签分类" :image-size="120" />
        </div>
      </div>
    </el-card>

    <!-- ========== 标签分类 创建/编辑对话框 ========== -->
    <el-dialog
      v-model="categoryDialogVisible"
      :title="editingCategory ? '编辑标签分类' : '新建标签分类'"
      width="500px"
      destroy-on-close
      class="edit-dialog"
    >
      <el-form :model="categoryForm" label-width="90px">
        <el-form-item label="分类名称" required>
          <el-input v-model="categoryForm.name" placeholder="如：项目状态" maxlength="64" clearable />
        </el-form-item>
        <el-form-item label="分类编码" required>
          <el-input
            v-model="categoryForm.code"
            placeholder="如：project_status（英文/数字/下划线）"
            maxlength="64"
            :disabled="!!editingCategory"
            clearable
          />
        </el-form-item>
        <el-form-item label="颜色主题">
          <el-select v-model="categoryForm.color" style="width: 100%">
            <el-option label="蓝色 (primary)" value="primary" />
            <el-option label="绿色 (success)" value="success" />
            <el-option label="橙色 (warning)" value="warning" />
            <el-option label="红色 (danger)" value="danger" />
            <el-option label="灰色 (info)" value="info" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="categoryForm.description" type="textarea" :rows="2" placeholder="分类描述（可选）" maxlength="255" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button round @click="categoryDialogVisible = false">取消</el-button>
        <el-button type="primary" round :loading="categorySaving" @click="submitCategory">
          {{ editingCategory ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- ========== 数据标签值 创建/编辑对话框 ========== -->
    <el-dialog
      v-model="dataTagDialogVisible"
      :title="editingDataTag ? '编辑标签' : `新建标签 - ${selectedCategory?.name}`"
      width="460px"
      destroy-on-close
      class="edit-dialog"
    >
      <el-form :model="dataTagForm" label-width="80px">
        <el-form-item label="标签名称" required>
          <el-input v-model="dataTagForm.name" placeholder="输入标签名称" maxlength="64" clearable />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="dataTagForm.description" type="textarea" :rows="2" placeholder="标签描述（可选）" maxlength="255" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button round @click="dataTagDialogVisible = false">取消</el-button>
        <el-button type="primary" round :loading="dataTagSaving" @click="submitDataTag">
          {{ editingDataTag ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- ========== 部门管理（仅超级管理员可见） ========== -->
    <el-card class="section-card" v-if="isSuperAdmin">
      <template #header>
        <div class="card-header">
          <el-icon><OfficeBuilding /></el-icon>
          <span>部门管理</span>
          <el-tag size="small" effect="plain" type="primary">共 {{ deptListVisible.length }} 个部门</el-tag>
        </div>
      </template>

      <div class="table-toolbar">
        <el-button type="primary" round @click="openDeptCreateDialog">
          <el-icon><Plus /></el-icon>新建部门
        </el-button>
      </div>

      <el-table :data="deptListVisible" border stripe v-loading="deptLoading" class="admin-table">
        <el-table-column prop="name" label="部门名称" min-width="140" />
        <el-table-column prop="code" label="部门编码" width="130" align="center">
          <template #default="{ row }">
            <span class="code-text">{{ row.code }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.description">{{ row.description }}</span>
            <span v-else class="muted-text">—</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right" align="center">
          <template #default="{ row }">
            <el-button size="small" type="primary" effect="plain" round @click="openDeptEditDialog(row)">
              <el-icon><Edit /></el-icon>编辑
            </el-button>
            <el-button size="small" type="danger" effect="plain" round @click="handleDeleteDept(row)">
              <el-icon><Delete /></el-icon>删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- ========== 部门创建/编辑对话框 ========== -->
    <el-dialog
      v-model="deptDialogVisible"
      :title="editingDept ? '编辑部门' : '新建部门'"
      width="480px"
      destroy-on-close
      class="edit-dialog"
    >
      <el-form :model="deptForm" label-width="90px">
        <el-form-item label="部门名称" required>
          <el-input v-model="deptForm.name" placeholder="如：研发部" maxlength="128" clearable />
        </el-form-item>
        <el-form-item label="部门编码" required>
          <el-input v-model="deptForm.code" placeholder="如：RD" maxlength="64" :disabled="!!editingDept" clearable />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="deptForm.description" type="textarea" :rows="3" placeholder="部门职责描述" maxlength="255" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button round @click="deptDialogVisible = false">取消</el-button>
        <el-button type="primary" round :loading="deptSaving" @click="submitDept">
          {{ editingDept ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- ========== 角色管理（仅超级管理员可见） ========== -->
    <el-card class="section-card" v-if="isSuperAdmin">
      <template #header>
        <div class="card-header">
          <el-icon><UserFilled /></el-icon>
          <span>角色管理</span>
          <el-tag size="small" effect="plain" type="warning">共 {{ roleList.length }} 个角色</el-tag>
        </div>
      </template>

      <div class="table-toolbar">
        <el-button type="primary" round @click="openRoleCreateDialog">
          <el-icon><Plus /></el-icon>新建角色
        </el-button>
      </div>

      <el-table :data="roleList" border stripe v-loading="roleLoading" class="admin-table">
        <el-table-column prop="role_code" label="角色编码" width="160" align="center">
          <template #default="{ row }">
            <span class="code-text">{{ row.role_code }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="role_name" label="角色名称" width="140" />
        <el-table-column label="所属部门" width="130" align="center">
          <template #default="{ row }">
            <span v-if="row.is_system" class="muted-text">—</span>
            <el-tag v-else-if="row.department_name" size="small" type="info" effect="plain">
              {{ row.department_name }}
            </el-tag>
            <span v-else class="muted-text">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="职责描述" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.description">{{ row.description }}</span>
            <span v-else class="muted-text">—</span>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_system ? 'info' : 'success'" size="small" effect="dark">
              {{ row.is_system ? '系统内置' : '自定义' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="员工数" width="80" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="row.user_count > 0 ? 'primary' : 'info'" effect="plain">
              {{ row.user_count }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right" align="center">
          <template #default="{ row }">
            <el-button
              size="small"
              type="primary"
              effect="plain"
              round
              :disabled="row.is_system"
              @click="openRoleEditDialog(row)"
            >
              <el-icon><Edit /></el-icon>编辑
            </el-button>
            <el-button
              size="small"
              type="danger"
              effect="plain"
              round
              :disabled="row.is_system || row.user_count > 0"
              @click="handleDeleteRole(row)"
            >
              <el-icon><Delete /></el-icon>删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- ========== 角色创建/编辑对话框 ========== -->
    <el-dialog
      v-model="roleDialogVisible"
      :title="editingRole ? '编辑角色' : '新建角色'"
      width="520px"
      destroy-on-close
      class="edit-dialog"
    >
      <el-form :model="roleForm" label-width="90px">
        <el-form-item label="角色编码" required>
          <el-input
            v-model="roleForm.role_code"
            placeholder="大写字母开头，如 DATA_ANALYST"
            :disabled="!!editingRole"
            maxlength="64"
            show-word-limit
            clearable
            @keyup.enter="submitRole"
          />
        </el-form-item>
        <el-form-item label="角色名称" required>
          <el-input v-model="roleForm.role_name" placeholder="如：数据分析师" maxlength="64" show-word-limit clearable />
        </el-form-item>
        <el-form-item label="所属部门" :required="!editingRole || !editingRole.is_system">
          <el-select
            v-model="roleForm.department_id"
            placeholder="系统内置角色无需部门"
            style="width: 100%"
            :disabled="editingRole && editingRole.is_system"
            clearable
          >
            <el-option
              v-for="dept in deptListForRole"
              :key="dept.id"
              :label="dept.name"
              :value="dept.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="roleForm.description" type="textarea" :rows="3" placeholder="角色的职责描述" maxlength="255" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button round @click="roleDialogVisible = false">取消</el-button>
        <el-button type="primary" round :loading="roleSaving" @click="submitRole">
          {{ editingRole ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>

  </div>
</template>

<script setup>
import { reactive, ref, onMounted, computed } from 'vue'
import { adminApi } from '@/api/admin'
import { useAuthStore } from '@/stores/auth'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Collection, Plus, OfficeBuilding, Edit, Delete, UserFilled } from '@element-plus/icons-vue'

const authStore = useAuthStore()
const isSuperAdmin = computed(() => authStore.user?.role_code === 'SUPER_ADMIN')

// ========== 数据标签管理（新） ==========
const categoryLoading = ref(false)
const tagLoading = ref(false)
const categoryList = ref([])
const selectedCategory = ref(null)
const currentCategoryTags = ref([])
const categoryDialogVisible = ref(false)
const categorySaving = ref(false)
const editingCategory = ref(null)
const dataTagDialogVisible = ref(false)
const dataTagSaving = ref(false)
const editingDataTag = ref(null)

const totalCategoryCount = computed(() => categoryList.value.length)
const totalDataTagCount = computed(() => categoryList.value.reduce((sum, c) => sum + c.tag_count, 0))

const categoryForm = reactive({
  name: '',
  code: '',
  color: 'primary',
  description: '',
})

const dataTagForm = reactive({
  name: '',
  description: '',
})

function formatTagTime(isoStr) {
  if (!isoStr) return '—'
  try {
    const d = new Date(isoStr)
    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
  } catch {
    return isoStr
  }
}

async function fetchCategories() {
  categoryLoading.value = true
  try {
    const res = await adminApi.getDataTagCategories()
    categoryList.value = res.items || []
    if (categoryList.value.length > 0) {
      await selectCategory(categoryList.value[0])
    } else {
      selectedCategory.value = null
      currentCategoryTags.value = []
    }
  } catch {
    categoryList.value = []
  } finally {
    categoryLoading.value = false
  }
}

async function selectCategory(cat) {
  selectedCategory.value = cat
  await fetchCategoryTags(cat.id)
}

async function fetchCategoryTags(categoryId) {
  tagLoading.value = true
  try {
    const detail = await adminApi.getDataTagCategoryDetail(categoryId)
    currentCategoryTags.value = detail.tags || []
    const catIdx = categoryList.value.findIndex(c => c.id === categoryId)
    if (catIdx >= 0) {
      categoryList.value[catIdx].tag_count = detail.tag_count
    }
  } catch {
    currentCategoryTags.value = []
  } finally {
    tagLoading.value = false
  }
}

function openCategoryCreateDialog() {
  editingCategory.value = null
  categoryForm.name = ''
  categoryForm.code = ''
  categoryForm.color = 'primary'
  categoryForm.description = ''
  categoryDialogVisible.value = true
}

function openCategoryEditDialog(cat) {
  editingCategory.value = cat
  categoryForm.name = cat.name
  categoryForm.code = cat.code
  categoryForm.color = cat.color
  categoryForm.description = cat.description || ''
  categoryDialogVisible.value = true
}

async function submitCategory() {
  if (!categoryForm.name || !categoryForm.name.trim()) {
    ElMessage.warning('请输入分类名称')
    return
  }
  if (!editingCategory.value && (!categoryForm.code || !categoryForm.code.trim())) {
    ElMessage.warning('请输入分类编码')
    return
  }
  categorySaving.value = true
  try {
    if (editingCategory.value) {
      await adminApi.updateDataTagCategory(editingCategory.value.id, {
        name: categoryForm.name.trim(),
        color: categoryForm.color,
        description: categoryForm.description.trim() || null,
      })
      ElMessage.success('分类已更新')
    } else {
      await adminApi.createDataTagCategory({
        name: categoryForm.name.trim(),
        code: categoryForm.code.trim().toLowerCase(),
        color: categoryForm.color,
        description: categoryForm.description.trim() || null,
        sort_order: totalCategoryCount.value + 1,
      })
      ElMessage.success('分类创建成功')
    }
    categoryDialogVisible.value = false
    await fetchCategories()
  } catch {
    // handled by interceptor
  } finally {
    categorySaving.value = false
  }
}

async function handleDeleteCategory(cat) {
  try {
    await ElMessageBox.confirm(
      `确定删除标签分类 "${cat.name}" 吗？仅当分类下无标签时才可删除，系统内置分类不可删除。`,
      '确认删除',
      { type: 'warning', confirmButtonText: '确定删除', cancelButtonText: '取消' }
    )
    await adminApi.deleteDataTagCategory(cat.id)
    ElMessage.success('分类已删除')
    if (selectedCategory.value?.id === cat.id) {
      selectedCategory.value = null
      currentCategoryTags.value = []
    }
    await fetchCategories()
  } catch (e) {
    if (e === 'cancel') return
  }
}

function openDataTagCreateDialog() {
  if (!selectedCategory.value) {
    ElMessage.warning('请先选择一个分类')
    return
  }
  editingDataTag.value = null
  dataTagForm.name = ''
  dataTagForm.description = ''
  dataTagDialogVisible.value = true
}

function openDataTagEditDialog(tag) {
  editingDataTag.value = tag
  dataTagForm.name = tag.name
  dataTagForm.description = tag.description || ''
  dataTagDialogVisible.value = true
}

async function submitDataTag() {
  if (!dataTagForm.name || !dataTagForm.name.trim()) {
    ElMessage.warning('请输入标签名称')
    return
  }
  dataTagSaving.value = true
  try {
    if (editingDataTag.value) {
      await adminApi.updateDataTag(editingDataTag.value.id, {
        name: dataTagForm.name.trim(),
        description: dataTagForm.description.trim() || null,
      })
      ElMessage.success('标签已更新')
    } else {
      await adminApi.createDataTag({
        category_id: selectedCategory.value.id,
        name: dataTagForm.name.trim(),
        description: dataTagForm.description.trim() || null,
        sort_order: currentCategoryTags.value.length + 1,
      })
      ElMessage.success(`标签 "${dataTagForm.name.trim()}" 创建成功`)
    }
    dataTagDialogVisible.value = false
    await fetchCategoryTags(selectedCategory.value.id)
    const catIdx = categoryList.value.findIndex(c => c.id === selectedCategory.value.id)
    if (catIdx >= 0) {
      categoryList.value[catIdx].tag_count = currentCategoryTags.value.length
    }
  } catch {
    // handled by interceptor
  } finally {
    dataTagSaving.value = false
  }
}

async function handleDeleteDataTag(tag) {
  try {
    await ElMessageBox.confirm(
      `确定删除标签 "${tag.name}" 吗？删除后全局生效。`,
      '确认删除',
      { type: 'warning', confirmButtonText: '确定删除', cancelButtonText: '取消' }
    )
    await adminApi.deleteDataTag(tag.id)
    ElMessage.success('标签已删除')
    await fetchCategoryTags(selectedCategory.value.id)
    const catIdx = categoryList.value.findIndex(c => c.id === selectedCategory.value.id)
    if (catIdx >= 0) {
      categoryList.value[catIdx].tag_count = Math.max(0, (categoryList.value[catIdx].tag_count || 1) - 1)
    }
  } catch (e) {
    if (e === 'cancel') return
  }
}

// ========== 部门管理 ==========
const deptList = ref([])
const deptListVisible = computed(() => deptList.value.filter(d => d.code !== 'HEADQUARTERS'))
const deptListForRole = computed(() => deptList.value.filter(d => d.code !== 'HEADQUARTERS'))
const deptLoading = ref(false)
const deptDialogVisible = ref(false)
const deptSaving = ref(false)
const editingDept = ref(null)

const deptForm = reactive({
  name: '',
  code: '',
  description: '',
})

async function fetchDepartments() {
  deptLoading.value = true
  try {
    const res = await adminApi.getDepartments()
    deptList.value = res.items || []
  } catch {
    deptList.value = []
  } finally {
    deptLoading.value = false
  }
}

function openDeptCreateDialog() {
  editingDept.value = null
  deptForm.name = ''
  deptForm.code = ''
  deptForm.description = ''
  deptDialogVisible.value = true
}

function openDeptEditDialog(row) {
  editingDept.value = row
  deptForm.name = row.name
  deptForm.code = row.code
  deptForm.description = row.description || ''
  deptDialogVisible.value = true
}

async function submitDept() {
  if (!deptForm.name || !deptForm.name.trim()) {
    ElMessage.warning('请输入部门名称')
    return
  }
  if (!deptForm.code || !deptForm.code.trim()) {
    ElMessage.warning('请输入部门编码')
    return
  }
  deptSaving.value = true
  try {
    if (editingDept.value) {
      await adminApi.updateDepartment(editingDept.value.id, {
        name: deptForm.name.trim(),
        description: deptForm.description.trim() || null,
      })
      ElMessage.success('部门已更新')
    } else {
      await adminApi.createDepartment({
        name: deptForm.name.trim(),
        code: deptForm.code.trim(),
        description: deptForm.description.trim() || null,
      })
      ElMessage.success('部门创建成功')
    }
    deptDialogVisible.value = false
    await fetchDepartments()
  } catch {
    // handled by interceptor
  } finally {
    deptSaving.value = false
  }
}

async function handleDeleteDept(row) {
  try {
    await ElMessageBox.confirm(
      `确定删除部门 "${row.name}" 吗？仅当部门下无员工和角色时才可删除。`,
      '确认删除',
      { type: 'warning', confirmButtonText: '确定删除', cancelButtonText: '取消' }
    )
    await adminApi.deleteDepartment(row.id)
    ElMessage.success('部门已删除')
    await fetchDepartments()
  } catch (e) {
    if (e === 'cancel') return
  }
}

// ========== 角色管理 ==========
const roleList = ref([])
const roleLoading = ref(false)
const roleDialogVisible = ref(false)
const roleSaving = ref(false)
const editingRole = ref(null)

const roleForm = reactive({
  role_code: '',
  role_name: '',
  department_id: null,
  description: '',
})

function openRoleCreateDialog() {
  editingRole.value = null
  roleForm.role_code = ''
  roleForm.role_name = ''
  roleForm.department_id = null
  roleForm.description = ''
  roleDialogVisible.value = true
}

function openRoleEditDialog(row) {
  editingRole.value = row
  roleForm.role_code = row.role_code
  roleForm.role_name = row.role_name
  roleForm.department_id = row.department_id || null
  roleForm.description = row.description || ''
  roleDialogVisible.value = true
}

async function submitRole() {
  if (!roleForm.role_code || !roleForm.role_code.trim()) {
    ElMessage.warning('请输入角色编码（大写字母开头，可含数字和下划线）')
    return
  }
  if (!roleForm.role_name || !roleForm.role_name.trim()) {
    ElMessage.warning('请输入角色名称')
    return
  }
  if (!editingRole.value && !roleForm.department_id) {
    ElMessage.warning('请选择所属部门')
    return
  }
  if (editingRole.value && editingRole.value.is_system) {
    roleForm.department_id = null
  }
  roleSaving.value = true
  try {
    if (editingRole.value) {
      await adminApi.updateRole(editingRole.value.id, {
        role_name: roleForm.role_name.trim(),
        department_id: roleForm.department_id,
        description: roleForm.description.trim() || null,
      })
      ElMessage.success('角色已更新')
    } else {
      await adminApi.createRole({
        role_code: roleForm.role_code.trim().toUpperCase(),
        role_name: roleForm.role_name.trim(),
        department_id: roleForm.department_id,
        description: roleForm.description.trim() || null,
      })
      ElMessage.success('角色创建成功')
    }
    roleDialogVisible.value = false
    await fetchRoles()
  } catch {
    // handled by interceptor
  } finally {
    roleSaving.value = false
  }
}

async function handleDeleteRole(row) {
  try {
    await ElMessageBox.confirm(
      `确定删除角色 "${row.role_name}" (${row.role_code}) 吗？此操作不可恢复。`,
      '确认删除',
      { type: 'warning', confirmButtonText: '确定删除', cancelButtonText: '取消' }
    )
    await adminApi.deleteRole(row.id)
    ElMessage.success('角色已删除')
    await fetchRoles()
  } catch (e) {
    if (e === 'cancel') return
  }
}

async function fetchRoles() {
  roleLoading.value = true
  try {
    const res = await adminApi.getRoles()
    roleList.value = res.items || []
  } catch {
    roleList.value = []
  } finally {
    roleLoading.value = false
  }
}

onMounted(() => {
  if (isSuperAdmin.value) {
    fetchCategories()
    fetchDepartments()
    fetchRoles()
  }
})
</script>

<style scoped>
.page-view {
  max-width: 1100px;
  margin: 0 auto;
  padding: 20px 24px;
}

.page-header {
  margin-bottom: 20px;
}

.page-header h3 {
  font-size: 22px;
  font-weight: 700;
  color: #1e293b;
  margin: 0 0 6px;
  letter-spacing: -0.3px;
}

.page-desc {
  font-size: 13px;
  color: #64748b;
  margin: 0;
}

/* ========== Section Card ========== */
.section-card {
  background: #ffffff;
  border-radius: 12px;
  margin-bottom: 20px;
  overflow: hidden;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 600;
  font-size: 15px;
  color: #1e293b;
}

.card-header :deep(.el-icon) {
  color: var(--color-primary);
  font-size: 16px;
}

.card-header :deep(.el-tag) {
  margin-left: auto;
  font-weight: 400;
}

/* ========== 数据标签管理 左右布局 ========== */
.tag-manage-layout {
  display: flex;
  gap: 16px;
  min-height: 400px;
}

.category-panel {
  width: 280px;
  flex-shrink: 0;
  border-right: 1px solid #f1f5f9;
  padding-right: 16px;
}

.tag-panel {
  flex: 1;
  min-width: 0;
}

.panel-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 0 14px;
  gap: 10px;
}

.panel-title-wrap {
  display: flex;
  align-items: baseline;
  gap: 8px;
  min-width: 0;
}

.panel-title {
  font-size: 15px;
  font-weight: 600;
  color: #1e293b;
}

.panel-desc {
  font-size: 12px;
  color: #94a3b8;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.category-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 520px;
  overflow-y: auto;
}

.category-item {
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid transparent;
  cursor: pointer;
  transition: all 0.2s;
  background: #f8fafc;
}

.category-item:hover {
  background: #eff6ff;
  border-color: #bfdbfe;
}

.category-item.active {
  background: #eff6ff;
  border-color: var(--color-primary, #409eff);
  box-shadow: 0 0 0 1px var(--color-primary, #409eff) inset;
}

.cat-main {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.cat-name-tag {
  font-weight: 500;
}

.cat-code {
  font-size: 11px !important;
}

.cat-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 6px;
}

.tag-count {
  font-size: 12px;
  color: #64748b;
}

.cat-actions {
  display: flex;
  gap: 2px;
  opacity: 0;
  transition: opacity 0.15s;
}

.category-item:hover .cat-actions,
.category-item.active .cat-actions {
  opacity: 1;
}

/* ========== Table Toolbar ========== */
.table-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 2px 16px;
}

/* ========== Tables ========== */
.admin-table {
  background: #ffffff;
  border-radius: 10px;
  overflow: hidden;
}

.admin-table :deep(.el-table__header th) {
  background: #f8fafc;
  color: #475569;
  font-weight: 600;
  font-size: 13px;
}

.admin-table :deep(.el-table__body td) {
  color: #334155;
  font-size: 13px;
}

.code-text {
  font-family: 'Segoe UI', 'SF Mono', monospace;
  font-size: 12px;
  color: var(--color-primary);
  font-weight: 500;
}

.muted-text {
  color: #94a3b8;
}

/* ========== Dialogs ========== */
.edit-dialog :deep(.el-dialog__header) {
  padding: 20px 24px;
  border-bottom: 1px solid #f1f5f9;
}

.edit-dialog :deep(.el-dialog__title) {
  font-size: 16px;
  font-weight: 600;
  color: #1e293b;
}

.edit-dialog :deep(.el-dialog__body) {
  padding: 24px;
}

.edit-dialog :deep(.el-dialog__footer) {
  padding: 16px 24px;
  border-top: 1px solid #f1f5f9;
}
</style>
