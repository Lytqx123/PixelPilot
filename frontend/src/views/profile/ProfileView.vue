<template>
  <div class="page-view">
    <div class="page-header">
      <h3>个人中心</h3>
      <p class="page-desc">查看和修改个人信息</p>
    </div>

    <el-card shadow="hover" class="info-card">
      <template #header>
        <div class="card-header">
          <el-icon><User /></el-icon>
          <span>个人信息</span>
        </div>
      </template>

      <el-descriptions :column="2" border class="info-desc">
        <el-descriptions-item label="员工ID">{{ user.employeeId }}</el-descriptions-item>
        <el-descriptions-item label="姓名">{{ user.realName }}</el-descriptions-item>
        <el-descriptions-item label="性别">
          {{ user.gender || '未设置' }}
          <el-tooltip content="性别由管理员设置，如需修改请联系管理员" placement="top">
            <el-icon style="margin-left: 6px; color: #94a3b8; cursor: help"><InfoFilled /></el-icon>
          </el-tooltip>
        </el-descriptions-item>
        <el-descriptions-item label="角色">{{ user.roleName }}</el-descriptions-item>
        <el-descriptions-item label="电话号码">
          <template v-if="editingPhone">
            <el-input v-model="phoneForm.phone" size="small" style="width: 200px" placeholder="请输入电话号码" />
            <el-button type="primary" size="small" @click="handleSavePhone" :loading="savingPhone" style="margin-left: 8px">保存</el-button>
            <el-button size="small" @click="editingPhone = false">取消</el-button>
          </template>
          <template v-else>
            {{ user.phone || '未设置' }}
            <el-button type="primary" link size="small" @click="startEditPhone">修改</el-button>
          </template>
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="user.status === 1 ? 'success' : 'danger'" size="small" effect="dark">
            {{ user.status === 1 ? '正常' : '禁用' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="个人说明" :span="2">
          <template v-if="editingDesc">
            <el-input
              v-model="descForm.personal_description"
              type="textarea"
              :rows="3"
              placeholder="请输入个人说明（选填）"
              maxlength="512"
              show-word-limit
            />
            <div style="margin-top: 8px; display: flex; gap: 8px">
              <el-button type="primary" size="small" @click="handleSaveDesc" :loading="savingDesc">保存</el-button>
              <el-button size="small" @click="editingDesc = false">取消</el-button>
            </div>
          </template>
          <template v-else>
            <span v-if="user.personalDescription" class="desc-text">{{ user.personalDescription }}</span>
            <span v-else class="desc-empty">暂未填写</span>
            <el-button type="primary" link size="small" style="margin-left: 8px" @click="startEditDesc">编辑</el-button>
          </template>
        </el-descriptions-item>
        <el-descriptions-item label="数据权限" :span="2">
          <el-popover placement="bottom" :width="320" trigger="click">
            <template #reference>
              <el-button size="small" type="primary" effect="plain">
                <el-icon><Collection /></el-icon>查看详情
              </el-button>
            </template>
            <div class="tag-popover">
              <div class="tag-row">
                <span class="tag-label">车型：</span>
                <div class="tag-list-inline">
                  <template v-if="uniqueScopeTags.model.length > 0">
                    <el-tag v-for="t in uniqueScopeTags.model" :key="t" size="small" type="primary" class="inline-tag">{{ t }}</el-tag>
                  </template>
                  <span v-else class="empty-text">全部车型</span>
                </div>
              </div>
              <div class="tag-row">
                <span class="tag-label">区域：</span>
                <div class="tag-list-inline">
                  <template v-if="uniqueScopeTags.region.length > 0">
                    <el-tag v-for="t in uniqueScopeTags.region" :key="t" size="small" type="success" class="inline-tag">{{ t }}</el-tag>
                  </template>
                  <span v-else class="empty-text">全部区域</span>
                </div>
              </div>
              <div class="tag-row">
                <span class="tag-label">分类：</span>
                <div class="tag-list-inline">
                  <template v-if="uniqueScopeTags.doc_type.length > 0">
                    <el-tag v-for="t in uniqueScopeTags.doc_type" :key="t" size="small" type="warning" class="inline-tag">{{ t }}</el-tag>
                  </template>
                  <span v-else class="empty-text">全部类型</span>
                </div>
              </div>
            </div>
          </el-popover>
        </el-descriptions-item>
      </el-descriptions>

      <el-divider />

      <div class="pwd-section">
        <div class="section-title">
          <el-icon><Lock /></el-icon>
          <span>修改密码</span>
        </div>
        <el-form ref="pwdFormRef" :model="pwdForm" :rules="pwdRules" label-width="100px" size="default" class="pwd-form">
          <el-form-item label="旧密码" prop="oldPassword">
            <el-input v-model="pwdForm.oldPassword" type="password" show-password placeholder="请输入旧密码" />
          </el-form-item>
          <el-form-item label="新密码" prop="newPassword">
            <el-input v-model="pwdForm.newPassword" type="password" show-password placeholder="请输入新密码（至少6位）" />
          </el-form-item>
          <el-form-item label="确认新密码" prop="confirmPassword">
            <el-input v-model="pwdForm.confirmPassword" type="password" show-password placeholder="请再次输入新密码" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="handleChangePwd" :loading="savingPwd">确认修改</el-button>
          </el-form-item>
        </el-form>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { authApi } from '@/api/auth'
import { ElMessage } from 'element-plus'
import { User, InfoFilled, Collection, Lock } from '@element-plus/icons-vue'

const authStore = useAuthStore()
const pwdFormRef = ref(null)

const user = computed(() => ({
  employeeId: authStore.user?.username || '',
  realName: authStore.realName,
  gender: authStore.user?.gender || '',
  roleName: authStore.roleName,
  phone: authStore.user?.phone || '',
  status: authStore.user?.status ?? 1,
  personalDescription: authStore.user?.personal_description || '',
}))

const uniqueScopeTags = computed(() => {
  const scopes = authStore.user?.data_scopes || []
  const modelSet = new Set()
  const regionSet = new Set()
  const docTypeSet = new Set()
  scopes.forEach(s => {
    if (s.model_tag) modelSet.add(s.model_tag)
    if (s.region_tag) regionSet.add(s.region_tag)
    if (s.doc_type_tag) docTypeSet.add(s.doc_type_tag)
  })
  return {
    model: [...modelSet],
    region: [...regionSet],
    doc_type: [...docTypeSet],
  }
})

const savingPwd = ref(false)
const pwdForm = reactive({ oldPassword: '', newPassword: '', confirmPassword: '' })

const validateConfirmPass = (_rule, value, callback) => {
  if (value !== pwdForm.newPassword) { callback(new Error('两次输入的密码不一致')) }
  else { callback() }
}

const pwdRules = {
  oldPassword: [{ required: true, message: '请输入旧密码', trigger: 'blur' }],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    { validator: validateConfirmPass, trigger: 'blur' },
  ],
}

async function handleChangePwd() {
  const valid = await pwdFormRef.value.validate().catch(() => false)
  if (!valid) return
  savingPwd.value = true
  try {
    await authApi.changePassword({ old_password: pwdForm.oldPassword, new_password: pwdForm.newPassword })
    ElMessage.success('密码修改成功')
    pwdForm.oldPassword = ''; pwdForm.newPassword = ''; pwdForm.confirmPassword = ''
    pwdFormRef.value?.resetFields()
  } catch { /* handled */ } finally { savingPwd.value = false }
}

const editingPhone = ref(false)
const savingPhone = ref(false)
const phoneForm = reactive({ phone: '' })

function startEditPhone() { phoneForm.phone = user.value.phone; editingPhone.value = true }

async function handleSavePhone() {
  savingPhone.value = true
  try {
    const res = await authApi.updatePhone({ phone: phoneForm.phone })
    authStore.user.phone = res.phone
    localStorage.setItem('user', JSON.stringify(authStore.user))
    editingPhone.value = false
    ElMessage.success('电话号码修改成功')
  } catch { /* handled */ } finally { savingPhone.value = false }
}

const editingDesc = ref(false)
const savingDesc = ref(false)
const descForm = reactive({ personal_description: '' })

function startEditDesc() { descForm.personal_description = user.value.personalDescription; editingDesc.value = true }

async function handleSaveDesc() {
  savingDesc.value = true
  try {
    const res = await authApi.updateDescription({ personal_description: descForm.personal_description })
    authStore.user.personal_description = res.personal_description
    localStorage.setItem('user', JSON.stringify(authStore.user))
    editingDesc.value = false
    ElMessage.success('个人说明修改成功')
  } catch { /* handled */ } finally { savingDesc.value = false }
}
</script>

<style scoped>
.page-desc {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin: 0;
}

.info-card {
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.info-card :deep(.el-card__body) {
  padding: 28px 32px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 600;
  font-size: 15px;
  color: var(--color-text-primary);
}

.card-header :deep(.el-icon) {
  color: var(--color-primary);
}

/* ========== Descriptions ========== */
.info-desc {
  margin-top: 4px;
}

.info-desc :deep(.el-descriptions__label) {
  width: 120px;
  min-width: 120px;
  background: var(--color-bg-hover);
  color: var(--color-text-regular);
  font-weight: 500;
}

.info-desc :deep(.el-descriptions__body) {
  table-layout: fixed;
}

.desc-text {
  color: var(--color-text-regular);
}

.desc-empty {
  color: var(--color-text-placeholder);
}

/* ========== Tag Popover ========== */
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

/* ========== Password Section ========== */
.pwd-section {
  padding-top: 8px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  color: var(--color-text-primary);
  font-weight: 600;
  margin-bottom: 16px;
}

.section-title :deep(.el-icon) {
  color: var(--color-primary);
}

.pwd-form {
  max-width: 480px;
}

.pwd-form :deep(.el-input) {
  max-width: 320px;
}
</style>
