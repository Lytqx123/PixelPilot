<template>
  <div class="page-view">
    <div class="toolbar">
      <div class="toolbar-left">
        <el-select
          v-model="filterDepartmentId"
          placeholder="选择部门"
          clearable
          class="toolbar-select"
          @change="onDepartmentFilter"
        >
          <el-option
            v-for="dept in departmentOptionsForCreate"
            :key="dept.id"
            :label="dept.name"
            :value="dept.id"
          />
        </el-select>
        <el-select
          v-model="filterRoleId"
          placeholder="选择角色"
          clearable
          class="toolbar-select"
          @change="onRoleFilter"
        >
          <el-option
            v-for="r in allRoleOptions"
            :key="r.id"
            :label="r.role_name"
            :value="r.id"
          />
        </el-select>
        <el-input
          v-model="keyword"
          placeholder="搜索员工ID / 姓名"
          clearable
          class="toolbar-input"
          @input="onSearch"
          prefix-icon="Search"
        />
      </div>
      <div class="toolbar-right">
        <el-button v-if="authStore.isSuperAdmin" type="primary" round @click="openCreateDialog">
          <el-icon><Plus /></el-icon>
          新建管理员
        </el-button>
        <el-button v-else type="primary" round @click="openCreateDialog">
          <el-icon><Plus /></el-icon>
          新建员工
        </el-button>
      </div>
    </div>

    <el-table :data="items" border stripe v-loading="loading" class="content-table">
      <el-table-column prop="username" label="员工ID" min-width="120" show-overflow-tooltip />
      <el-table-column prop="real_name" label="姓名" width="100" />
      <el-table-column label="性别" width="80" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.gender === '男'" size="small" type="primary" effect="plain">男</el-tag>
          <el-tag v-else-if="row.gender === '女'" size="small" type="danger" effect="plain">女</el-tag>
          <span v-else class="text-muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="部门" min-width="120" show-overflow-tooltip>
        <template #default="{ row }">
          {{ row.department_name || '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="role_name" label="角色" min-width="110" show-overflow-tooltip />
      <el-table-column label="状态" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="row.status === 1 ? 'success' : 'danger'" size="small" effect="dark">
            {{ row.status === 1 ? '正常' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" width="170" align="center">
        <template #default="{ row }">
          <span class="time-text">{{ formatTime(row.created_at) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="180" fixed="right" align="center">
        <template #default="{ row }">
          <div v-if="canEdit(row)" class="action-cell">
            <el-button size="small" type="primary" effect="plain" round @click="openDetailDialog(row)">
              <el-icon><View /></el-icon>详情
            </el-button>
            <el-dropdown trigger="click" @command="(cmd) => handleAction(cmd, row)">
              <el-button size="small" type="warning" effect="plain" round>
                <el-icon><MoreFilled /></el-icon>更多
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="edit">
                    <el-icon><Edit /></el-icon>编辑信息
                  </el-dropdown-item>
                  <el-dropdown-item :command="row.status === 1 ? 'disable' : 'enable'">
                    <el-icon><Switch /></el-icon>{{ row.status === 1 ? '禁用账号' : '启用账号' }}
                  </el-dropdown-item>
                  <el-dropdown-item divided command="delete">
                    <el-icon><Delete /></el-icon><span style="color:#f56c6c;">删除员工</span>
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
          <span v-else class="text-muted">—</span>
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
        @change="fetchUsers"
      />
    </div>

    <el-dialog v-model="detailVisible" title="员工详细信息" width="600px">
      <el-descriptions :column="2" border v-if="detailUser">
        <el-descriptions-item label="员工ID">{{ detailUser.username }}</el-descriptions-item>
        <el-descriptions-item label="姓名">{{ detailUser.real_name }}</el-descriptions-item>
        <el-descriptions-item label="性别">{{ detailUser.gender || '未设置' }}</el-descriptions-item>
        <el-descriptions-item label="部门">{{ detailUser.department_name || '未设置' }}</el-descriptions-item>
        <el-descriptions-item label="角色">{{ detailUser.role_name }}</el-descriptions-item>
        <el-descriptions-item label="电话号码">{{ detailUser.phone || '未设置' }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="detailUser.status === 1 ? 'success' : 'danger'" size="small">
            {{ detailUser.status === 1 ? '正常' : '禁用' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ detailUser.created_at || '-' }}</el-descriptions-item>
        <el-descriptions-item label="个人说明" :span="2">{{ detailUser.personal_description || '未填写' }}</el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="560px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="员工ID" prop="username">
          <el-input v-model="form.username" :disabled="!!editingUser" placeholder="请输入员工ID" />
        </el-form-item>
        <el-form-item label="密码" prop="password" v-if="!editingUser">
          <el-input v-model="form.password" type="password" placeholder="请输入密码（至少6位）" show-password />
        </el-form-item>
        <el-form-item label="姓名" prop="real_name">
          <el-input v-model="form.real_name" placeholder="请输入真实姓名" />
        </el-form-item>
        <el-form-item label="性别" prop="gender">
          <el-select v-model="form.gender" placeholder="请选择性别" style="width: 100%">
            <el-option label="男" value="男" />
            <el-option label="女" value="女" />
          </el-select>
        </el-form-item>
        <el-form-item label="电话号码">
          <el-input v-model="form.phone" placeholder="请输入电话号码（选填）" />
        </el-form-item>
        <el-form-item label="部门" prop="department_id">
          <el-select v-if="authStore.isSuperAdmin" v-model="form.department_id" placeholder="请选择所属部门" style="width: 100%">
            <el-option
              v-for="dept in departmentOptionsForCreate"
              :key="dept.id"
              :label="dept.name"
              :value="dept.id"
            />
          </el-select>
          <el-input v-else :model-value="authStore.user?.department_name || '未设置'" disabled />
        </el-form-item>
        <el-form-item label="角色" prop="role_id" v-if="!authStore.isSuperAdmin || editingUser">
          <el-select v-model="form.role_id" placeholder="请选择角色" style="width: 100%">
            <el-option v-for="r in createRoleOptions" :key="r.id" :label="r.role_name" :value="r.id" />
          </el-select>
        </el-form-item>

      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { adminApi } from '@/api/admin'
import { useAuthStore } from '@/stores/auth'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, View, MoreFilled, Edit, Switch, Delete } from '@element-plus/icons-vue'

const authStore = useAuthStore()
const ROOT_ADMIN_USERNAME = '758441925'

const loading = ref(false)
const saving = ref(false)
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const keyword = ref('')
const filterDepartmentId = ref(null)
const filterRoleId = ref(null)
let searchTimer = null

const dialogVisible = ref(false)
const editingUser = ref(null)
const formRef = ref(null)

const detailVisible = ref(false)
const detailUser = ref(null)

const form = reactive({
  username: '',
  password: '',
  real_name: '',
  gender: '',
  phone: '',
  department_id: null,
  role_id: null,
  data_scopes: [],
})

const departmentOptions = ref([])
const departmentOptionsForCreate = computed(() =>
  departmentOptions.value.filter(d => d.code !== 'HEADQUARTERS')
)

const rules = computed(() => ({
  username: [{ required: true, message: '请输入员工ID', trigger: 'blur' }],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少6位', trigger: 'blur' },
  ],
  real_name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  gender: [{ required: true, message: '请选择性别', trigger: 'change' }],
  // SUPER_ADMIN 新建管理员时角色自动赋值，非必选（前端已隐藏下拉）
  role_id: authStore.isSuperAdmin && !editingUser.value
    ? []
    : [{ required: true, message: '请选择角色', trigger: 'change' }],
  // SUPER_ADMIN 新建/编辑时必须选部门
  department_id: authStore.isSuperAdmin
    ? [{ required: true, message: '请选择所属部门', trigger: 'change' }]
    : [],
}))

const allRoleOptions = ref([])
const createRoleOptions = ref([])

const dialogTitle = computed(() => {
  if (editingUser.value) return '编辑信息'
  return authStore.isSuperAdmin ? '新建管理员' : '新建员工'
})

function canEdit(row) {
  const currentUser = authStore.user
  if (!currentUser) return false
  // 超级管理员不可操作超级管理员自身，但可操作其他
  if (row.role_code === 'SUPER_ADMIN') return false
  // 管理员互相之间不可操作
  if (authStore.isAdmin && !authStore.isSuperAdmin) {
    if (row.role_code === 'ADMIN') return false
  }
  return true
}

onMounted(() => {
  if (authStore.isSuperAdmin) {
    fetchDepartments()
  }
  fetchAvailableRoles()
})

async function fetchDepartments() {
  try {
    const res = await adminApi.getDepartments()
    if (res.items) departmentOptions.value = res.items
  } catch (e) {
    // handled
  }
}

async function buildRoleOptions(users) {
  const seen = new Map()
  for (const u of users) {
    if (!seen.has(u.role_id)) {
      seen.set(u.role_id, { id: u.role_id, role_name: u.role_name })
    }
  }
  try {
    const res = await adminApi.getAvailableRoles()
    if (Array.isArray(res)) {
      for (const r of res) {
        if (!seen.has(r.id)) seen.set(r.id, r)
      }
    }
  } catch { /* fallback */ }
  allRoleOptions.value = Array.from(seen.values())
}

async function fetchUsers() {
  loading.value = true
  try {
    const params = {
      page: page.value,
      page_size: pageSize.value,
      keyword: keyword.value || undefined,
      role_id: filterRoleId.value || undefined,
      department_id: filterDepartmentId.value || undefined,
    }
    const res = await adminApi.getUsers(params)
    if (res.items) {
      items.value = res.items
      total.value = res.total
      buildRoleOptions(items.value)
    } else if (Array.isArray(res)) {
      items.value = res
      total.value = res.length
      buildRoleOptions(items.value)
    }
  } catch (e) {
    // handled
  } finally {
    loading.value = false
  }
}

async function fetchAvailableRoles() {
  try {
    const res = await adminApi.getAvailableRoles()
    createRoleOptions.value = Array.isArray(res) ? res : []
  } catch (e) {
    // handled
  }
}

function formatTime(ts) {
  if (!ts) return '-'
  try { return new Date(ts).toLocaleString('zh-CN') } catch { return ts }
}

function onSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => { page.value = 1; fetchUsers() }, 300)
}

function onDepartmentFilter() {
  page.value = 1
  fetchUsers()
}

function onRoleFilter() {
  page.value = 1
  fetchUsers()
}

function buildDataScopes() {
  return []
}

function openCreateDialog() {
  editingUser.value = null
  form.username = ''
  form.password = ''
  form.real_name = ''
  form.gender = ''
  form.phone = ''
  form.department_id = authStore.isSuperAdmin ? null : (authStore.user?.department_id || null)
  // 超级管理员新建时自动设为 ADMIN 角色
  if (authStore.isSuperAdmin) {
    const adminRole = createRoleOptions.value.find(r => r.role_code === 'ADMIN')
    form.role_id = adminRole ? adminRole.id : null
  } else {
    form.role_id = null
  }
  form.data_scopes = []
  dialogVisible.value = true
}

function openDetailDialog(row) {
  detailUser.value = row
  detailVisible.value = true
}

function openEditDialog(row) {
  editingUser.value = row
  form.username = row.username
  form.real_name = row.real_name
  form.gender = row.gender || ''
  form.phone = row.phone || ''
  form.department_id = row.department_id
  form.role_id = row.role_id
  form.data_scopes = []
  dialogVisible.value = true
}

function handleAction(cmd, row) {
  if (cmd === 'edit') return openEditDialog(row)
  if (cmd === 'disable' || cmd === 'enable') return handleDisable(row)
  if (cmd === 'delete') return handleDelete(row)
}

async function handleDisable(row) {
  try {
    if (row.username === ROOT_ADMIN_USERNAME) { ElMessage.warning('系统超级管理员账号不可被禁用'); return }
    const action = row.status === 1 ? '禁用' : '启用'
    await ElMessageBox.confirm(`确定要${action}该账号吗？`, '确认')
    await adminApi.disableUser(row.id)
    ElMessage.success(`已${action}`)
    fetchUsers()
  } catch (e) { /* cancelled */ }
}

async function handleDelete(row) {
  try {
    if (row.username === ROOT_ADMIN_USERNAME) { ElMessage.warning('系统超级管理员账号不可被删除'); return }
    await ElMessageBox.confirm(
      `确定要永久删除员工 "${row.real_name || row.username}" 吗？此操作不可恢复。`,
      '确认删除'
    )
    await adminApi.deleteUser(row.id)
    ElMessage.success('删除成功')
    fetchUsers()
  } catch (e) { /* cancelled */ }
}

async function handleSave() {
  try {
    await formRef.value.validate()
    saving.value = true
    const data = {
      ...form,
      data_scopes: buildDataScopes(),
    }
    if (editingUser.value) {
      await adminApi.updateUser(editingUser.value.id, data)
      ElMessage.success('更新成功')
    } else {
      await adminApi.createUser(data)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchUsers()
  } catch (e) {
    if (e !== false) {
      ElMessage.error(e.message || '操作失败')
    }
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
/* ========== Table 表头美化 ========== */
.content-table :deep(.el-table__header th) {
  background: var(--color-bg-hover);
  color: var(--color-text-regular);
  font-weight: 600;
  font-size: 13px;
}

.content-table :deep(.el-table__body td) {
  color: var(--color-text-regular);
  font-size: 13px;
}

/* ========== Action Cell ========== */
.action-cell {
  display: flex;
  justify-content: center;
  gap: 8px;
}

.action-cell :deep(.el-button) {
  padding: 6px 12px;
  font-size: 12px;
}

.data-scope-tag {
  margin: 4px;
}
</style>