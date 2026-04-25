<template>
  <div class="user-management">
    <!-- Header -->
    <header class="header">
      <div class="container">
        <div class="header-content">
          <div class="page-title">
            <router-link to="/" class="back-link">
              ← 返回容器列表
            </router-link>
            <h1>用户管理</h1>
          </div>
          <div class="header-actions">
            <div class="user-menu">
              <span class="user-info">
                <span class="user-avatar">{{ currentUser?.username?.charAt(0).toUpperCase() }}</span>
                <span class="user-name">{{ currentUser?.username }}</span>
                <span class="user-role role-admin">管理员</span>
              </span>
              <button class="btn btn-ghost btn-sm" @click="logout" title="退出登录">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                  <polyline points="16 17 21 12 16 7"></polyline>
                  <line x1="21" y1="12" x2="9" y2="12"></line>
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <main class="main-content">
      <div class="container">
        <!-- 操作栏 -->
        <div class="action-bar">
          <button class="btn btn-primary" @click="openCreateModal">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="12" y1="5" x2="12" y2="19"></line>
              <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
            新增用户
          </button>
          <button class="btn btn-outline" @click="fetchUsers">
            刷新
          </button>
        </div>

        <!-- 加载状态 -->
        <div v-if="loading" class="loading-state">
          <div class="loading-spinner"></div>
          <p>加载中...</p>
        </div>

        <!-- 错误状态 -->
        <div v-else-if="error" class="error-state">
          <div class="error-icon">⚠️</div>
          <p>{{ error }}</p>
          <button class="btn btn-primary" @click="fetchUsers">重试</button>
        </div>

        <!-- 用户列表 -->
        <div v-else class="card">
          <div v-if="users.length === 0" class="empty-state">
            <div class="empty-icon">👥</div>
            <p>暂无用户</p>
            <button class="btn btn-primary" @click="openCreateModal">创建第一个用户</button>
          </div>

          <div v-else class="user-list">
            <table class="table">
              <thead>
                <tr>
                  <th>用户名</th>
                  <th>角色</th>
                  <th>状态</th>
                  <th>权限容器数</th>
                  <th>创建时间</th>
                  <th>最后登录</th>
                  <th class="text-right">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="user in users" :key="user.id">
                  <td>
                    <div class="user-cell">
                      <span class="user-avatar-small">{{ user.username.charAt(0).toUpperCase() }}</span>
                      <span class="user-username">{{ user.username }}</span>
                    </div>
                  </td>
                  <td>
                    <span class="badge" :class="user.role === 'admin' ? 'badge-warning' : 'badge-info'">
                      {{ user.role === 'admin' ? '管理员' : '普通用户' }}
                    </span>
                  </td>
                  <td>
                    <span class="badge" :class="user.is_active ? 'badge-success' : 'badge-secondary'">
                      {{ user.is_active ? '启用' : '禁用' }}
                    </span>
                  </td>
                  <td>
                    <span class="permission-count">{{ user.permissions?.length || 0 }} 个</span>
                  </td>
                  <td class="text-muted">{{ formatDate(user.created_at) }}</td>
                  <td class="text-muted">{{ user.last_login_at ? formatDate(user.last_login_at) : '从未登录' }}</td>
                  <td class="text-right">
                    <div class="action-buttons">
                      <button 
                        class="btn btn-ghost btn-sm action-btn"
                        @click="openPermissionModal(user)"
                        title="权限管理"
                      >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                          <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                          <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
                        </svg>
                      </button>
                      <button 
                        class="btn btn-ghost btn-sm action-btn"
                        @click="openEditModal(user)"
                        title="编辑用户"
                      >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                          <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                          <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                        </svg>
                      </button>
                      <button 
                        v-if="user.role !== 'admin' || users.length > 1"
                        class="btn btn-ghost btn-sm action-btn action-btn-danger"
                        @click="confirmDeleteUser(user)"
                        title="删除用户"
                        :disabled="deleteInProgress === user.id"
                      >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                          <polyline points="3 6 5 6 21 6"></polyline>
                          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                          <line x1="10" y1="11" x2="10" y2="17"></line>
                          <line x1="14" y1="11" x2="14" y2="17"></line>
                        </svg>
                      </button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </main>

    <!-- 创建/编辑用户模态框 -->
    <div v-if="showUserModal" class="modal-overlay" @click.self="closeUserModal">
      <div class="modal modal-medium">
        <div class="modal-header">
          <h3 class="modal-title">{{ editingUser ? '编辑用户' : '创建用户' }}</h3>
          <button class="modal-close" @click="closeUserModal">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <div v-if="userModalError" class="form-error">{{ userModalError }}</div>
          
          <form @submit.prevent="handleSubmitUser">
            <div class="form-group">
              <label class="form-label">用户名 <span class="required">*</span></label>
              <input 
                type="text" 
                v-model="userForm.username" 
                class="form-input"
                placeholder="请输入用户名"
                :disabled="userModalLoading"
                required
              />
            </div>
            
            <div class="form-group" v-if="!editingUser">
              <label class="form-label">密码 <span class="required">*</span></label>
              <input 
                :type="showPassword ? 'text' : 'password'" 
                v-model="userForm.password" 
                class="form-input"
                placeholder="请输入密码"
                :disabled="userModalLoading"
                required
              />
              <button type="button" class="toggle-password" @click="showPassword = !showPassword">
                {{ showPassword ? '隐藏' : '显示' }}
              </button>
            </div>
            
            <div class="form-group" v-if="editingUser">
              <label class="form-label">新密码（留空则不修改）</label>
              <input 
                :type="showPassword ? 'text' : 'password'" 
                v-model="userForm.password" 
                class="form-input"
                placeholder="留空表示不修改密码"
                :disabled="userModalLoading"
              />
              <button type="button" class="toggle-password" @click="showPassword = !showPassword">
                {{ showPassword ? '隐藏' : '显示' }}
              </button>
            </div>
            
            <div class="form-group">
              <label class="form-label">角色</label>
              <select v-model="userForm.role" class="form-select" :disabled="userModalLoading">
                <option value="user">普通用户</option>
                <option value="admin">管理员</option>
              </select>
            </div>
            
            <div class="form-group">
              <label class="checkbox-label">
                <input 
                  type="checkbox" 
                  v-model="userForm.is_active"
                  :disabled="userModalLoading"
                />
                <span>启用用户</span>
              </label>
            </div>
            
            <div class="modal-footer">
              <button type="button" class="btn btn-outline" @click="closeUserModal" :disabled="userModalLoading">
                取消
              </button>
              <button type="submit" class="btn btn-primary" :disabled="userModalLoading || !userForm.username">
                {{ userModalLoading ? '提交中...' : (editingUser ? '保存' : '创建') }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <!-- 权限管理模态框 -->
    <div v-if="showPermissionModal" class="modal-overlay" @click.self="closePermissionModal">
      <div class="modal modal-large">
        <div class="modal-header">
          <h3 class="modal-title">
            权限管理 - {{ permissionUser?.username }}
            <span class="badge badge-info" v-if="permissionUser?.role === 'admin'">
              管理员拥有所有权限
            </span>
          </h3>
          <button class="modal-close" @click="closePermissionModal">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <div v-if="permissionLoading" class="loading-state">
            <div class="loading-spinner"></div>
            <p>加载中...</p>
          </div>
          
          <div v-else-if="permissionUser?.role === 'admin'" class="empty-state">
            <div class="empty-icon">🔑</div>
            <p>管理员用户拥有所有容器的读写权限</p>
            <p class="text-muted">无需为管理员配置权限</p>
          </div>
          
          <div v-else>
            <div class="permission-toolbar">
              <button class="btn btn-primary btn-sm" @click="openAddPermissionModal">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="12" y1="5" x2="12" y2="19"></line>
                  <line x1="5" y1="12" x2="19" y2="12"></line>
                </svg>
                添加权限
              </button>
              <button class="btn btn-outline btn-sm" @click="refreshPermissions">
                刷新
              </button>
            </div>
            
            <div v-if="userPermissions.length === 0" class="empty-state">
              <div class="empty-icon">📦</div>
              <p>暂无权限配置</p>
              <p class="text-muted">点击"添加权限"为用户分配容器权限</p>
            </div>
            
            <div v-else class="permission-list">
              <table class="table">
                <thead>
                  <tr>
                    <th>容器ID</th>
                    <th>权限级别</th>
                    <th>创建时间</th>
                    <th class="text-right">操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="perm in userPermissions" :key="perm.id">
                    <td>
                      <span class="font-mono">{{ perm.container_id }}</span>
                    </td>
                    <td>
                      <span 
                        class="badge"
                        :class="perm.permission_level === 'read_write' ? 'badge-success' : 'badge-info'"
                      >
                        {{ perm.permission_level === 'read_write' ? '读写' : '只读' }}
                      </span>
                    </td>
                    <td class="text-muted">{{ formatDate(perm.created_at) }}</td>
                    <td class="text-right">
                      <div class="action-buttons">
                        <button 
                          class="btn btn-ghost btn-sm action-btn"
                          @click="openEditPermissionModal(perm)"
                          title="编辑权限"
                        >
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                          </svg>
                        </button>
                        <button 
                          class="btn btn-ghost btn-sm action-btn action-btn-danger"
                          @click="confirmDeletePermission(perm)"
                          title="删除权限"
                        >
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="3 6 5 6 21 6"></polyline>
                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                          </svg>
                        </button>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 添加/编辑权限模态框 -->
    <div v-if="showAddPermissionModal" class="modal-overlay" @click.self="closeAddPermissionModal">
      <div class="modal modal-small">
        <div class="modal-header">
          <h3 class="modal-title">{{ editingPermission ? '编辑权限' : '添加权限' }}</h3>
          <button class="modal-close" @click="closeAddPermissionModal">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <div v-if="permissionFormError" class="form-error">{{ permissionFormError }}</div>
          
          <form @submit.prevent="handleSubmitPermission">
            <div class="form-group" v-if="!editingPermission">
              <label class="form-label">容器ID <span class="required">*</span></label>
              <input 
                type="text" 
                v-model="permissionForm.container_id" 
                class="form-input"
                placeholder="请输入容器ID"
                :disabled="permissionFormLoading"
                required
              />
              <p class="form-hint">例如: a1b2c3d4e5f6 或完整ID</p>
            </div>
            
            <div class="form-group">
              <label class="form-label">权限级别</label>
              <select v-model="permissionForm.permission_level" class="form-select" :disabled="permissionFormLoading">
                <option value="read_only">只读（仅可查看日志）</option>
                <option value="read_write">读写（可查看、启动、停止、重启、删除）</option>
              </select>
            </div>
            
            <div class="modal-footer">
              <button type="button" class="btn btn-outline" @click="closeAddPermissionModal" :disabled="permissionFormLoading">
                取消
              </button>
              <button type="submit" class="btn btn-primary" :disabled="permissionFormLoading || (!editingPermission && !permissionForm.container_id)">
                {{ permissionFormLoading ? '提交中...' : (editingPermission ? '保存' : '添加') }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <!-- 确认删除模态框 -->
    <div v-if="showDeleteConfirm" class="modal-overlay" @click.self="closeDeleteConfirm">
      <div class="modal modal-small">
        <div class="modal-header">
          <h3 class="modal-title">确认删除</h3>
          <button class="modal-close" @click="closeDeleteConfirm">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <p>{{ deleteConfirmMessage }}</p>
          
          <div class="modal-footer">
            <button type="button" class="btn btn-outline" @click="closeDeleteConfirm" :disabled="deleteConfirmLoading">
              取消
            </button>
            <button type="button" class="btn btn-danger" @click="executeDelete" :disabled="deleteConfirmLoading">
              {{ deleteConfirmLoading ? '删除中...' : '确认删除' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Toast 提示 -->
    <div v-if="toastMessage" class="toast" :class="toastType">
      {{ toastMessage }}
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import axios from 'axios'
import { useAuth } from '../composables/useAuth'


const router = useRouter()
const route = useRoute()
const { isAdmin, currentUser, logout, currentToken } = useAuth()


if (!isAdmin.value) {
  router.push('/')
}


const users = ref([])
const loading = ref(true)
const error = ref(null)
const deleteInProgress = ref(null)


const showUserModal = ref(false)
const editingUser = ref(null)
const userModalLoading = ref(false)
const userModalError = ref('')
const showPassword = ref(false)
const userForm = ref({
  username: '',
  password: '',
  role: 'user',
  is_active: true
})


const showPermissionModal = ref(false)
const permissionUser = ref(null)
const permissionLoading = ref(false)
const userPermissions = ref([])


const showAddPermissionModal = ref(false)
const editingPermission = ref(null)
const permissionFormLoading = ref(false)
const permissionFormError = ref('')
const permissionForm = ref({
  container_id: '',
  permission_level: 'read_only'
})


const showDeleteConfirm = ref(false)
const deleteConfirmMessage = ref('')
const deleteConfirmLoading = ref(false)
let deleteCallback = null


const toastMessage = ref('')
const toastType = ref('success')
let toastTimeout = null


const fetchUsers = async () => {
  try {
    loading.value = true
    error.value = null
    
    const response = await axios.get('/api/users')
    
    if (response.data.success) {
      users.value = response.data.data
    } else {
      error.value = response.data.error || '获取用户列表失败'
    }
  } catch (err) {
    error.value = err.response?.data?.message || err.message || '获取用户列表失败'
  } finally {
    loading.value = false
  }
}


const openCreateModal = () => {
  editingUser.value = null
  userForm.value = {
    username: '',
    password: '',
    role: 'user',
    is_active: true
  }
  userModalError.value = ''
  showPassword.value = false
  showUserModal.value = true
}


const openEditModal = (user) => {
  editingUser.value = { ...user }
  userForm.value = {
    username: user.username,
    password: '',
    role: user.role,
    is_active: user.is_active
  }
  userModalError.value = ''
  showPassword.value = false
  showUserModal.value = true
}


const closeUserModal = () => {
  showUserModal.value = false
  editingUser.value = null
  userForm.value = {
    username: '',
    password: '',
    role: 'user',
    is_active: true
  }
  userModalError.value = ''
}


const handleSubmitUser = async () => {
  if (!userForm.value.username) {
    userModalError.value = '请输入用户名'
    return
  }
  
  if (!editingUser.value && !userForm.value.password) {
    userModalError.value = '请输入密码'
    return
  }
  
  try {
    userModalLoading.value = true
    userModalError.value = ''
    
    if (editingUser.value) {
      const updateData = {
        username: userForm.value.username,
        role: userForm.value.role,
        is_active: userForm.value.is_active
      }
      
      if (userForm.value.password) {
        updateData.password = userForm.value.password
      }
      
      const response = await axios.put(`/api/users/${editingUser.value.id}`, updateData)
      
      if (response.data.success) {
        showToast('用户更新成功', 'success')
        closeUserModal()
        fetchUsers()
      } else {
        userModalError.value = response.data.error || '更新用户失败'
      }
    } else {
      const response = await axios.post('/api/users', {
        username: userForm.value.username,
        password: userForm.value.password,
        role: userForm.value.role,
        is_active: userForm.value.is_active
      })
      
      if (response.data.success) {
        showToast('用户创建成功', 'success')
        closeUserModal()
        fetchUsers()
      } else {
        userModalError.value = response.data.error || '创建用户失败'
      }
    }
  } catch (err) {
    userModalError.value = err.response?.data?.message || err.message || '操作失败'
  } finally {
    userModalLoading.value = false
  }
}


const confirmDeleteUser = (user) => {
  deleteConfirmMessage.value = `确定要删除用户 "${user.username}" 吗？此操作不可撤销。`
  deleteCallback = async () => {
    await axios.delete(`/api/users/${user.id}`)
  }
  showDeleteConfirm.value = true
}


const openPermissionModal = async (user) => {
  permissionUser.value = user
  showPermissionModal.value = true
  refreshPermissions()
}


const closePermissionModal = () => {
  showPermissionModal.value = false
  permissionUser.value = null
  userPermissions.value = []
}


const refreshPermissions = async () => {
  if (!permissionUser.value) return
  
  try {
    permissionLoading.value = true
    
    const response = await axios.get(`/api/users/${permissionUser.value.id}/permissions`)
    
    if (response.data.success) {
      userPermissions.value = response.data.data
    }
  } catch (err) {
    showToast(err.response?.data?.message || err.message || '获取权限失败', 'error')
  } finally {
    permissionLoading.value = false
  }
}


const openAddPermissionModal = () => {
  editingPermission.value = null
  permissionForm.value = {
    container_id: '',
    permission_level: 'read_only'
  }
  permissionFormError.value = ''
  showAddPermissionModal.value = true
}


const openEditPermissionModal = (perm) => {
  editingPermission.value = { ...perm }
  permissionForm.value = {
    container_id: perm.container_id,
    permission_level: perm.permission_level
  }
  permissionFormError.value = ''
  showAddPermissionModal.value = true
}


const closeAddPermissionModal = () => {
  showAddPermissionModal.value = false
  editingPermission.value = null
  permissionForm.value = {
    container_id: '',
    permission_level: 'read_only'
  }
  permissionFormError.value = ''
}


const handleSubmitPermission = async () => {
  if (!editingPermission.value && !permissionForm.value.container_id) {
    permissionFormError.value = '请输入容器ID'
    return
  }
  
  try {
    permissionFormLoading.value = true
    permissionFormError.value = ''
    
    if (editingPermission.value) {
      const response = await axios.put(
        `/api/users/${permissionUser.value.id}/permissions/${editingPermission.value.container_id}`,
        {
          permission_level: permissionForm.value.permission_level
        }
      )
      
      if (response.data.success) {
        showToast('权限更新成功', 'success')
        closeAddPermissionModal()
        refreshPermissions()
      } else {
        permissionFormError.value = response.data.error || '更新权限失败'
      }
    } else {
      const response = await axios.post(
        `/api/users/${permissionUser.value.id}/permissions`,
        {
          container_id: permissionForm.value.container_id,
          permission_level: permissionForm.value.permission_level
        }
      )
      
      if (response.data.success) {
        showToast('权限添加成功', 'success')
        closeAddPermissionModal()
        refreshPermissions()
      } else {
        permissionFormError.value = response.data.error || '添加权限失败'
      }
    }
  } catch (err) {
    permissionFormError.value = err.response?.data?.message || err.message || '操作失败'
  } finally {
    permissionFormLoading.value = false
  }
}


const confirmDeletePermission = (perm) => {
  deleteConfirmMessage.value = `确定要删除容器 "${perm.container_id}" 的权限吗？`
  deleteCallback = async () => {
    await axios.delete(
      `/api/users/${permissionUser.value.id}/permissions/${perm.container_id}`
    )
  }
  showDeleteConfirm.value = true
}


const closeDeleteConfirm = () => {
  showDeleteConfirm.value = false
  deleteConfirmMessage.value = ''
  deleteCallback = null
}


const executeDelete = async () => {
  if (!deleteCallback) return
  
  try {
    deleteConfirmLoading.value = true
    
    const response = await deleteCallback()
    
    showToast('删除成功', 'success')
    closeDeleteConfirm()
    fetchUsers()
    
    if (showPermissionModal.value) {
      refreshPermissions()
    }
  } catch (err) {
    showToast(err.response?.data?.message || err.message || '删除失败', 'error')
  } finally {
    deleteConfirmLoading.value = false
  }
}


const formatDate = (timestamp) => {
  if (!timestamp) return 'N/A'
  const date = new Date(timestamp)
  return date.toLocaleString('zh-CN')
}


const showToast = (message, type = 'success') => {
  if (toastTimeout) {
    clearTimeout(toastTimeout)
  }
  toastMessage.value = message
  toastType.value = type
  toastTimeout = setTimeout(() => {
    toastMessage.value = ''
  }, 3000)
}


onMounted(() => {
  fetchUsers()
})
</script>

<style scoped>
.user-management {
  min-height: 100vh;
  background-color: var(--bg-secondary);
}

.header {
  background-color: var(--bg-primary);
  border-bottom: 1px solid var(--border-color);
  padding: 1rem 0;
}

.header-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.page-title {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.page-title h1 {
  font-size: 1.5rem;
  font-weight: 700;
  margin: 0;
}

.back-link {
  color: var(--primary-color);
  text-decoration: none;
  font-size: 0.875rem;
}

.back-link:hover {
  text-decoration: underline;
}

.header-actions {
  display: flex;
  gap: 0.75rem;
  align-items: center;
}

.main-content {
  padding: 1.5rem 0;
}

.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 1rem;
}

.card {
  background-color: var(--bg-primary);
  border-radius: 0.75rem;
  padding: 1.5rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.action-bar {
  display: flex;
  gap: 0.75rem;
  margin-bottom: 1.5rem;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem;
  color: var(--text-secondary);
}

.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem;
  text-align: center;
}

.error-icon {
  font-size: 3rem;
  margin-bottom: 1rem;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem;
  text-align: center;
  color: var(--text-secondary);
}

.empty-icon {
  font-size: 3rem;
  margin-bottom: 1rem;
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid var(--border-color);
  border-top-color: var(--primary-color);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 1rem;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.table {
  width: 100%;
  border-collapse: collapse;
}

.table th {
  text-align: left;
  padding: 0.75rem 1rem;
  font-weight: 600;
  font-size: 0.875rem;
  color: var(--text-secondary);
  border-bottom: 1px solid var(--border-color);
}

.table td {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--border-color);
  font-size: 0.875rem;
}

.table tr:last-child td {
  border-bottom: none;
}

.text-right {
  text-align: right;
}

.text-muted {
  color: var(--text-secondary);
}

.font-mono {
  font-family: 'Courier New', monospace;
  font-size: 0.75rem;
}

.badge {
  display: inline-block;
  padding: 0.125rem 0.5rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 500;
}

.badge-success {
  background-color: var(--success-color);
  color: white;
}

.badge-warning {
  background-color: var(--warning-color);
  color: white;
}

.badge-info {
  background-color: var(--primary-color);
  color: white;
}

.badge-secondary {
  background-color: var(--text-secondary);
  color: white;
}

.user-cell {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.user-avatar {
  width: 28px;
  height: 28px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 0.875rem;
}

.user-avatar-small {
  width: 24px;
  height: 24px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 0.75rem;
}

.user-username {
  font-weight: 500;
}

.user-menu {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.25rem 0.5rem;
  background-color: var(--bg-secondary);
  border-radius: 8px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.user-name {
  font-weight: 500;
  font-size: 0.875rem;
}

.user-role {
  font-size: 0.7rem;
  padding: 0.125rem 0.375rem;
  border-radius: 4px;
}

.user-role.role-admin {
  background-color: rgba(245, 158, 11, 0.1);
  color: #d97706;
}

.permission-count {
  font-size: 0.875rem;
  color: var(--text-secondary);
}

.action-buttons {
  display: flex;
  gap: 0.25rem;
  justify-content: flex-end;
}

.action-btn {
  min-width: 28px;
  padding: 0.25rem;
}

.action-btn-danger {
  color: var(--error-color);
}

.action-btn-danger:hover:not(:disabled) {
  background-color: rgba(239, 68, 68, 0.1);
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.5rem 1rem;
  border-radius: 0.375rem;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  border: none;
  background-color: var(--bg-primary);
  color: var(--text-primary);
  text-decoration: none;
  transition: all 0.2s;
  gap: 0.5rem;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-outline {
  border: 1px solid var(--border-color);
}

.btn-outline:hover:not(:disabled) {
  background-color: var(--bg-secondary);
}

.btn-ghost {
  background-color: transparent;
}

.btn-ghost:hover:not(:disabled) {
  background-color: var(--bg-secondary);
}

.btn-primary {
  background-color: var(--primary-color);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background-color: #2563eb;
}

.btn-danger {
  background-color: var(--error-color);
  color: white;
}

.btn-danger:hover:not(:disabled) {
  background-color: #dc2626;
}

.btn-sm {
  padding: 0.25rem 0.5rem;
  font-size: 0.75rem;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  padding: 1rem;
}

.modal {
  background-color: var(--bg-primary);
  border-radius: 0.5rem;
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
  max-width: 90vw;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
}

.modal-small {
  width: 400px;
}

.modal-medium {
  width: 500px;
}

.modal-large {
  width: 800px;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
}

.modal-title {
  font-size: 1.125rem;
  font-weight: 600;
  margin: 0;
}

.modal-close {
  background: none;
  border: none;
  cursor: pointer;
  padding: 0.25rem;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal-close:hover {
  color: var(--text-primary);
}

.modal-body {
  padding: 1.5rem;
  overflow-y: auto;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  padding-top: 1.5rem;
}

.form-group {
  margin-bottom: 1.25rem;
  position: relative;
}

.form-label {
  display: block;
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: 0.5rem;
}

.required {
  color: var(--error-color);
}

.form-input {
  width: 100%;
  padding: 0.75rem 1rem;
  font-size: 1rem;
  border: 2px solid #e5e7eb;
  border-radius: 8px;
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;
  box-sizing: border-box;
}

.form-input:focus {
  border-color: var(--primary-color);
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.form-input:disabled {
  background-color: var(--bg-secondary);
  cursor: not-allowed;
}

.form-select {
  width: 100%;
  padding: 0.75rem 1rem;
  font-size: 1rem;
  border: 2px solid #e5e7eb;
  border-radius: 8px;
  outline: none;
  transition: border-color 0.2s;
  background-color: var(--bg-primary);
  color: var(--text-primary);
  box-sizing: border-box;
}

.form-select:focus {
  border-color: var(--primary-color);
}

.form-hint {
  font-size: 0.75rem;
  color: var(--text-secondary);
  margin-top: 0.25rem;
}

.form-error {
  background-color: #fef2f2;
  border: 1px solid #fecaca;
  color: #dc2626;
  padding: 0.75rem 1rem;
  border-radius: 8px;
  margin-bottom: 1rem;
  font-size: 0.875rem;
}

.toggle-password {
  position: absolute;
  right: 12px;
  top: 40px;
  background: none;
  border: none;
  color: #6b7280;
  font-size: 0.75rem;
  cursor: pointer;
  padding: 4px 8px;
}

.toggle-password:hover {
  color: #374151;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  cursor: pointer;
}

.permission-toolbar {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.permission-list {
  max-height: 400px;
  overflow-y: auto;
}

.toast {
  position: fixed;
  bottom: 1.5rem;
  left: 50%;
  transform: translateX(-50%);
  padding: 0.75rem 1.5rem;
  border-radius: 0.375rem;
  font-size: 0.875rem;
  font-weight: 500;
  z-index: 3000;
  animation: slideUp 0.3s ease;
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateX(-50%) translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }
}

.toast.success {
  background-color: var(--success-color);
  color: white;
}

.toast.error {
  background-color: var(--error-color);
  color: white;
}

@media (max-width: 768px) {
  .header-content {
    flex-direction: column;
    gap: 1rem;
    align-items: flex-start;
  }
  
  .header-actions {
    width: 100%;
    flex-wrap: wrap;
  }
  
  .modal {
    max-width: 100%;
    max-height: 95vh;
  }
  
  .modal-large {
    width: 100%;
  }
  
  .modal-small {
    width: 100%;
  }
  
  .action-buttons {
    flex-wrap: wrap;
  }
}
</style>
