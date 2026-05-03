<template>
  <AppLayout
    :currentUser="currentUser"
    :page-title="'镜像仓库配置'"
    @refresh="fetchRegistries"
    @logout="logout"
  >
        <div class="action-bar">
          <button class="btn btn-primary" @click="openCreateModal">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="12" y1="5" x2="12" y2="19"></line>
              <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
            新增仓库
          </button>
          <button class="btn btn-outline" @click="fetchRegistries">
            刷新
          </button>
        </div>

        <div v-if="loading" class="loading-state">
          <div class="loading-spinner"></div>
          <p>加载中...</p>
        </div>

        <div v-else-if="error" class="error-state">
          <div class="error-icon">⚠️</div>
          <p>{{ error }}</p>
          <button class="btn btn-primary" @click="fetchRegistries">重试</button>
        </div>

        <div v-else class="registry-list-container">
          <div v-if="registries.length === 0" class="empty-state">
            <div class="empty-icon">🔒</div>
            <p>暂无镜像仓库配置</p>
            <p class="text-muted">配置私有仓库后可以拉取和推送私有镜像</p>
            <div class="registry-types-info">
              <h4>支持的仓库类型:</h4>
              <div class="type-badges">
                <span class="badge badge-info">Docker Hub</span>
                <span class="badge badge-info">Harbor</span>
                <span class="badge badge-info">Quay</span>
                <span class="badge badge-info">AWS ECR</span>
                <span class="badge badge-info">阿里云 ACR</span>
                <span class="badge badge-info">GitHub CR</span>
                <span class="badge badge-info">GitLab CR</span>
              </div>
            </div>
            <button class="btn btn-primary" @click="openCreateModal">添加仓库配置</button>
          </div>

          <div v-else class="registry-list">
            <div 
              v-for="registry in registries" 
              :key="registry.id" 
              class="registry-card"
              :class="{ 'registry-card-inactive': !registry.is_active }"
            >
              <div class="registry-card-header">
                <div class="registry-icon" :class="getRegistryTypeClass(registry.registry_type)">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect>
                    <line x1="8" y1="21" x2="16" y2="21"></line>
                    <line x1="12" y1="17" x2="12" y2="21"></line>
                  </svg>
                </div>
                <div class="registry-info">
                  <h3 class="registry-name">
                    {{ registry.name }}
                    <span v-if="registry.is_default" class="badge badge-primary">默认</span>
                    <span v-if="!registry.is_active" class="badge badge-secondary">已禁用</span>
                  </h3>
                  <p class="registry-type">
                    <span class="type-label">{{ getRegistryTypeName(registry.registry_type) }}</span>
                  </p>
                  <p class="registry-host" v-if="registry.host">
                    <span class="host-label">地址:</span>
                    <span class="host-value">{{ registry.host }}</span>
                  </p>
                  <p class="registry-namespace" v-if="registry.namespace">
                    <span class="namespace-label">命名空间:</span>
                    <span class="namespace-value">{{ registry.namespace }}</span>
                  </p>
                  <p class="registry-username" v-if="registry.username">
                    <span class="username-label">用户名:</span>
                    <span class="username-value">{{ registry.username }}</span>
                  </p>
                  <p class="registry-description" v-if="registry.description">
                    {{ registry.description }}
                  </p>
                  <p class="registry-meta">
                    创建时间: {{ formatDate(registry.created_at) }}
                    <span v-if="registry.updated_at && registry.updated_at !== registry.created_at">
                      | 更新时间: {{ formatDate(registry.updated_at) }}
                    </span>
                  </p>
                </div>
              </div>
              <div class="registry-card-footer">
                <div class="action-buttons">
                  <button 
                    class="btn btn-ghost btn-sm action-btn"
                    @click="openEditModal(registry)"
                    title="编辑仓库"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                    </svg>
                    编辑
                  </button>
                  <button 
                    class="btn btn-ghost btn-sm action-btn action-btn-danger"
                    @click="confirmDeleteRegistry(registry)"
                    title="删除仓库"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <polyline points="3 6 5 6 21 6"></polyline>
                      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                      <line x1="10" y1="11" x2="10" y2="17"></line>
                      <line x1="14" y1="11" x2="14" y2="17"></line>
                    </svg>
                    删除
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

    <div v-if="showRegistryModal" class="modal-overlay" @click.self="closeRegistryModal">
      <div class="modal modal-large">
        <div class="modal-header">
          <h3 class="modal-title">{{ editingRegistry ? '编辑仓库配置' : '添加仓库配置' }}</h3>
          <button class="modal-close" @click="closeRegistryModal">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <div v-if="registryModalError" class="form-error">{{ registryModalError }}</div>
          
          <form @submit.prevent="handleSubmitRegistry">
            <div class="form-section">
              <h4>基本信息</h4>
              
              <div class="form-row">
                <div class="form-group">
                  <label class="form-label">仓库名称 <span class="required">*</span></label>
                  <input 
                    type="text" 
                    v-model="registryForm.name" 
                    class="form-input"
                    placeholder="例如: Docker Hub, Harbor Private"
                    :disabled="registryModalLoading"
                    required
                  />
                </div>
                
                <div class="form-group">
                  <label class="form-label">仓库类型 <span class="required">*</span></label>
                  <select 
                    v-model="registryForm.registry_type" 
                    class="form-input"
                    :disabled="registryModalLoading"
                    required
                  >
                    <option value="docker_hub">Docker Hub</option>
                    <option value="harbor">Harbor</option>
                    <option value="quay">Quay</option>
                    <option value="aws_ecr">AWS ECR</option>
                    <option value="aliyun_acr">阿里云 ACR</option>
                    <option value="github_container_registry">GitHub Container Registry</option>
                    <option value="gitlab_container_registry">GitLab Container Registry</option>
                    <option value="other">其他</option>
                  </select>
                </div>
              </div>
              
              <div class="form-row">
                <div class="form-group">
                  <label class="form-label">仓库地址</label>
                  <input 
                    type="text" 
                    v-model="registryForm.host" 
                    class="form-input"
                    placeholder="例如: registry.example.com"
                    :disabled="registryModalLoading"
                  />
                  <p class="form-hint">
                    Docker Hub 可不填；私有仓库请填写地址，如 <code>harbor.example.com</code>
                  </p>
                </div>
                
                <div class="form-group">
                  <label class="form-label">命名空间/项目</label>
                  <input 
                    type="text" 
                    v-model="registryForm.namespace" 
                    class="form-input"
                    placeholder="例如: library, my-project"
                    :disabled="registryModalLoading"
                  />
                  <p class="form-hint">可选，例如 Harbor 的项目名</p>
                </div>
              </div>
              
              <div class="form-group">
                <label class="form-label">描述</label>
                <textarea 
                  v-model="registryForm.description" 
                  class="form-input"
                  placeholder="仓库描述（可选）"
                  :disabled="registryModalLoading"
                  rows="2"
                ></textarea>
              </div>
            </div>

            <div class="form-section" v-if="!isAwsEcrType && !isAliyunAcrType">
              <h4>认证信息</h4>
              
              <div class="form-row">
                <div class="form-group">
                  <label class="form-label">用户名</label>
                  <input 
                    type="text" 
                    v-model="registryForm.username" 
                    class="form-input"
                    placeholder="用户名"
                    :disabled="registryModalLoading"
                  />
                </div>
                
                <div class="form-group">
                  <label class="form-label">密码/Token</label>
                  <input 
                    type="password" 
                    v-model="registryForm.password" 
                    class="form-input"
                    placeholder="密码或访问令牌"
                    :disabled="registryModalLoading"
                  />
                  <p class="form-hint">Docker Hub 建议使用 Personal Access Token</p>
                </div>
              </div>
            </div>

            <div class="form-section" v-if="isAwsEcrType">
              <h4>AWS 认证信息</h4>
              
              <div class="form-row">
                <div class="form-group">
                  <label class="form-label">Access Key ID</label>
                  <input 
                    type="text" 
                    v-model="registryForm.aws_access_key_id" 
                    class="form-input"
                    placeholder="AKIA..."
                    :disabled="registryModalLoading"
                  />
                </div>
                
                <div class="form-group">
                  <label class="form-label">Secret Access Key</label>
                  <input 
                    type="password" 
                    v-model="registryForm.aws_secret_access_key" 
                    class="form-input"
                    placeholder="Secret Key"
                    :disabled="registryModalLoading"
                  />
                </div>
              </div>
              
              <div class="form-group">
                <label class="form-label">AWS 区域</label>
                <input 
                  type="text" 
                  v-model="registryForm.aws_region" 
                  class="form-input"
                  placeholder="例如: us-east-1, cn-north-1"
                  :disabled="registryModalLoading"
                />
              </div>
            </div>

            <div class="form-section" v-if="isAliyunAcrType">
              <h4>阿里云认证信息</h4>
              
              <div class="form-row">
                <div class="form-group">
                  <label class="form-label">Access Key ID</label>
                  <input 
                    type="text" 
                    v-model="registryForm.aliyun_access_key_id" 
                    class="form-input"
                    placeholder="阿里云 AccessKey ID"
                    :disabled="registryModalLoading"
                  />
                </div>
                
                <div class="form-group">
                  <label class="form-label">Access Key Secret</label>
                  <input 
                    type="password" 
                    v-model="registryForm.aliyun_access_key_secret" 
                    class="form-input"
                    placeholder="阿里云 AccessKey Secret"
                    :disabled="registryModalLoading"
                  />
                </div>
              </div>
              
              <div class="form-group">
                <label class="form-label">阿里云区域</label>
                <input 
                  type="text" 
                  v-model="registryForm.aliyun_region" 
                  class="form-input"
                  placeholder="例如: cn-hangzhou, cn-beijing"
                  :disabled="registryModalLoading"
                />
              </div>
            </div>

            <div class="form-section">
              <h4>高级选项</h4>
              
              <div class="checkbox-group">
                <label class="checkbox-label">
                  <input 
                    type="checkbox" 
                    v-model="registryForm.is_secure"
                    :disabled="registryModalLoading"
                  />
                  <span>使用 HTTPS（安全连接）</span>
                </label>
                <label class="checkbox-label">
                  <input 
                    type="checkbox" 
                    v-model="registryForm.is_default"
                    :disabled="registryModalLoading"
                  />
                  <span>设为默认仓库</span>
                </label>
                <label class="checkbox-label">
                  <input 
                    type="checkbox" 
                    v-model="registryForm.is_active"
                    :disabled="registryModalLoading"
                  />
                  <span>启用此仓库</span>
                </label>
              </div>
            </div>
            
            <div class="modal-footer">
              <button type="button" class="btn btn-outline" @click="closeRegistryModal" :disabled="registryModalLoading">
                取消
              </button>
              <button type="submit" class="btn btn-primary" :disabled="registryModalLoading || !registryForm.name || !registryForm.registry_type">
                {{ registryModalLoading ? '提交中...' : (editingRegistry ? '保存' : '创建') }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <div v-if="showDeleteConfirm" class="modal-overlay" @click.self="closeDeleteConfirm">
      <div class="modal modal-small">
        <div class="modal-header">
          <h3 class="modal-title">确认删除</h3>
        </div>
        <div class="modal-body">
          <p>确定要删除仓库 "<strong>{{ deletingRegistry?.name }}</strong>" 吗？</p>
          <p class="delete-info">此操作不可撤销。</p>
          
          <div class="modal-footer">
            <button type="button" class="btn btn-outline" @click="closeDeleteConfirm" :disabled="deleteConfirmLoading">
              取消
            </button>
            <button type="button" class="btn btn-danger" @click="executeDeleteRegistry" :disabled="deleteConfirmLoading">
              {{ deleteConfirmLoading ? '删除中...' : '确认删除' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="toastMessage" class="toast" :class="toastType">
      {{ toastMessage }}
    </div>
  </AppLayout>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '../components/AppLayout.vue'
import { useAuth } from '../composables/useAuth'
import { registryApi } from '../api/containerApi'


const router = useRouter()
const { isAdmin, currentUser, logout } = useAuth()


if (!isAdmin.value) {
  router.push('/')
}


const registries = ref([])
const loading = ref(true)
const error = ref(null)

const showRegistryModal = ref(false)
const editingRegistry = ref(null)
const registryModalLoading = ref(false)
const registryModalError = ref('')
const registryForm = ref({
  name: '',
  registry_type: 'docker_hub',
  host: '',
  namespace: '',
  username: '',
  password: '',
  aws_access_key_id: '',
  aws_secret_access_key: '',
  aws_region: '',
  aliyun_access_key_id: '',
  aliyun_access_key_secret: '',
  aliyun_region: '',
  is_secure: true,
  is_default: false,
  is_active: true,
  description: '',
  config_json: null
})

const showDeleteConfirm = ref(false)
const deletingRegistry = ref(null)
const deleteConfirmLoading = ref(false)

const toastMessage = ref('')
const toastType = ref('success')
let toastTimeout = null


const isAwsEcrType = computed(() => {
  return registryForm.value.registry_type === 'aws_ecr'
})

const isAliyunAcrType = computed(() => {
  return registryForm.value.registry_type === 'aliyun_acr'
})


const registryTypeNames = {
  docker_hub: 'Docker Hub',
  harbor: 'Harbor',
  quay: 'Quay',
  aws_ecr: 'AWS ECR',
  aliyun_acr: '阿里云 ACR',
  github_container_registry: 'GitHub Container Registry',
  gitlab_container_registry: 'GitLab Container Registry',
  other: '其他'
}


const getRegistryTypeName = (type) => {
  return registryTypeNames[type] || type
}


const getRegistryTypeClass = (type) => {
  const classes = {
    docker_hub: 'docker-hub',
    harbor: 'harbor',
    quay: 'quay',
    aws_ecr: 'aws-ecr',
    aliyun_acr: 'aliyun-acr',
    github_container_registry: 'github-cr',
    gitlab_container_registry: 'gitlab-cr',
    other: 'other'
  }
  return classes[type] || 'default'
}


const fetchRegistries = async () => {
  try {
    loading.value = true
    error.value = null
    
    const result = await registryApi.getRegistries()
    
    if (result.success) {
      registries.value = result.data || []
    } else {
      error.value = result.message || '获取仓库列表失败'
    }
  } catch (err) {
    error.value = err.message || '获取仓库列表失败'
  } finally {
    loading.value = false
  }
}


const openCreateModal = () => {
  editingRegistry.value = null
  registryForm.value = {
    name: '',
    registry_type: 'docker_hub',
    host: '',
    namespace: '',
    username: '',
    password: '',
    aws_access_key_id: '',
    aws_secret_access_key: '',
    aws_region: '',
    aliyun_access_key_id: '',
    aliyun_access_key_secret: '',
    aliyun_region: '',
    is_secure: true,
    is_default: false,
    is_active: true,
    description: '',
    config_json: null
  }
  registryModalError.value = ''
  showRegistryModal.value = true
}


const openEditModal = (registry) => {
  editingRegistry.value = { ...registry }
  registryForm.value = {
    name: registry.name,
    registry_type: registry.registry_type,
    host: registry.host || '',
    namespace: registry.namespace || '',
    username: registry.username || '',
    password: '',
    aws_access_key_id: registry.aws_access_key_id || '',
    aws_secret_access_key: '',
    aws_region: registry.aws_region || '',
    aliyun_access_key_id: registry.aliyun_access_key_id || '',
    aliyun_access_key_secret: '',
    aliyun_region: registry.aliyun_region || '',
    is_secure: registry.is_secure,
    is_default: registry.is_default,
    is_active: registry.is_active,
    description: registry.description || '',
    config_json: registry.config_json
  }
  registryModalError.value = ''
  showRegistryModal.value = true
}


const closeRegistryModal = () => {
  showRegistryModal.value = false
  editingRegistry.value = null
  registryForm.value = {
    name: '',
    registry_type: 'docker_hub',
    host: '',
    namespace: '',
    username: '',
    password: '',
    aws_access_key_id: '',
    aws_secret_access_key: '',
    aws_region: '',
    aliyun_access_key_id: '',
    aliyun_access_key_secret: '',
    aliyun_region: '',
    is_secure: true,
    is_default: false,
    is_active: true,
    description: '',
    config_json: null
  }
  registryModalError.value = ''
}


const handleSubmitRegistry = async () => {
  if (!registryForm.value.name) {
    registryModalError.value = '请输入仓库名称'
    return
  }
  
  if (!registryForm.value.registry_type) {
    registryModalError.value = '请选择仓库类型'
    return
  }
  
  try {
    registryModalLoading.value = true
    registryModalError.value = ''
    
    const data = {
      name: registryForm.value.name,
      registry_type: registryForm.value.registry_type,
      is_secure: registryForm.value.is_secure,
      is_default: registryForm.value.is_default,
      is_active: registryForm.value.is_active
    }
    
    if (registryForm.value.host) {
      data.host = registryForm.value.host
    }
    if (registryForm.value.namespace) {
      data.namespace = registryForm.value.namespace
    }
    if (registryForm.value.description) {
      data.description = registryForm.value.description
    }
    
    if (registryForm.value.registry_type === 'aws_ecr') {
      if (registryForm.value.aws_access_key_id) {
        data.aws_access_key_id = registryForm.value.aws_access_key_id
      }
      if (registryForm.value.aws_secret_access_key) {
        data.aws_secret_access_key = registryForm.value.aws_secret_access_key
      }
      if (registryForm.value.aws_region) {
        data.aws_region = registryForm.value.aws_region
      }
    } else if (registryForm.value.registry_type === 'aliyun_acr') {
      if (registryForm.value.aliyun_access_key_id) {
        data.aliyun_access_key_id = registryForm.value.aliyun_access_key_id
      }
      if (registryForm.value.aliyun_access_key_secret) {
        data.aliyun_access_key_secret = registryForm.value.aliyun_access_key_secret
      }
      if (registryForm.value.aliyun_region) {
        data.aliyun_region = registryForm.value.aliyun_region
      }
    } else {
      if (registryForm.value.username) {
        data.username = registryForm.value.username
      }
      if (registryForm.value.password) {
        data.password = registryForm.value.password
      }
    }
    
    if (editingRegistry.value) {
      const result = await registryApi.updateRegistry(editingRegistry.value.id, data)
      
      if (result.success) {
        showToast('仓库配置更新成功', 'success')
        closeRegistryModal()
        fetchRegistries()
      } else {
        registryModalError.value = result.message || '更新失败'
      }
    } else {
      const result = await registryApi.createRegistry(data)
      
      if (result.success) {
        showToast('仓库配置创建成功', 'success')
        closeRegistryModal()
        fetchRegistries()
      } else {
        registryModalError.value = result.message || '创建失败'
      }
    }
  } catch (err) {
    registryModalError.value = err.message || '操作失败'
  } finally {
    registryModalLoading.value = false
  }
}


const confirmDeleteRegistry = (registry) => {
  deletingRegistry.value = registry
  showDeleteConfirm.value = true
}


const closeDeleteConfirm = () => {
  showDeleteConfirm.value = false
  deletingRegistry.value = null
}


const executeDeleteRegistry = async () => {
  if (!deletingRegistry.value) return
  
  try {
    deleteConfirmLoading.value = true
    
    const result = await registryApi.deleteRegistry(deletingRegistry.value.id)
    
    if (result.success) {
      showToast('仓库配置删除成功', 'success')
      closeDeleteConfirm()
      fetchRegistries()
    } else {
      showToast(result.message || '删除失败', 'error')
    }
  } catch (err) {
    showToast(err.message || '删除失败', 'error')
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
  fetchRegistries()
})
</script>

<style scoped>
.registry-management {
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

.action-bar {
  display: flex;
  gap: 0.75rem;
  margin-bottom: 1.5rem;
}

.loading-state,
.error-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem;
  text-align: center;
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

.empty-icon {
  font-size: 3rem;
  margin-bottom: 1rem;
}

.text-muted {
  color: var(--text-secondary);
}

.registry-types-info {
  margin: 1.5rem 0;
  padding: 1rem;
  background-color: var(--bg-secondary);
  border-radius: 0.5rem;
}

.registry-types-info h4 {
  margin: 0 0 0.75rem 0;
  font-size: 0.875rem;
  color: var(--text-secondary);
}

.type-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  justify-content: center;
}

.registry-list-container {
  background-color: var(--bg-primary);
  border-radius: 0.75rem;
  padding: 1.5rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.registry-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.registry-card {
  background-color: var(--bg-secondary);
  border-radius: 0.75rem;
  border: 1px solid var(--border-color);
  overflow: hidden;
  transition: box-shadow 0.2s, border-color 0.2s;
}

.registry-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  border-color: var(--primary-color);
}

.registry-card-inactive {
  opacity: 0.6;
}

.registry-card-inactive:hover {
  border-color: var(--border-color);
}

.registry-card-header {
  display: flex;
  padding: 1.25rem;
  gap: 1rem;
}

.registry-icon {
  width: 56px;
  height: 56px;
  border-radius: 0.75rem;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.registry-icon.docker-hub {
  background: linear-gradient(135deg, #2496ed 0%, #0db7ed 100%);
  color: white;
}

.registry-icon.harbor {
  background: linear-gradient(135deg, #60b932 0%, #2e8b57 100%);
  color: white;
}

.registry-icon.quay {
  background: linear-gradient(135deg, #ee0000 0%, #cc0000 100%);
  color: white;
}

.registry-icon.aws-ecr {
  background: linear-gradient(135deg, #ff9900 0%, #ec7211 100%);
  color: white;
}

.registry-icon.aliyun-acr {
  background: linear-gradient(135deg, #ff6a00 0%, #ff8c00 100%);
  color: white;
}

.registry-icon.github-cr {
  background: linear-gradient(135deg, #24292e 0%, #0d1117 100%);
  color: white;
}

.registry-icon.gitlab-cr {
  background: linear-gradient(135deg, #fc6d26 0%, #e24329 100%);
  color: white;
}

.registry-icon.other,
.registry-icon.default {
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  color: white;
}

.registry-info {
  flex: 1;
  min-width: 0;
}

.registry-name {
  font-size: 1.125rem;
  font-weight: 600;
  margin: 0 0 0.25rem 0;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.badge {
  display: inline-block;
  padding: 0.125rem 0.5rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 500;
}

.badge-primary {
  background-color: rgba(99, 102, 241, 0.1);
  color: #6366f1;
}

.badge-secondary {
  background-color: var(--bg-primary);
  color: var(--text-secondary);
}

.badge-info {
  background-color: rgba(14, 165, 233, 0.1);
  color: #0ea5e9;
}

.registry-type {
  margin: 0 0 0.5rem 0;
  font-size: 0.875rem;
}

.type-label {
  background-color: var(--bg-primary);
  color: var(--text-secondary);
  padding: 0.125rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
}

.registry-host,
.registry-namespace,
.registry-username,
.registry-description {
  margin: 0.25rem 0;
  font-size: 0.875rem;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.host-value,
.namespace-value,
.username-value {
  font-family: 'Courier New', monospace;
  color: var(--text-primary);
}

.registry-meta {
  font-size: 0.75rem;
  color: var(--text-secondary);
  margin: 0.5rem 0 0 0;
}

.registry-card-footer {
  padding: 0.75rem 1.25rem;
  background-color: var(--bg-primary);
  border-top: 1px solid var(--border-color);
}

.action-buttons {
  display: flex;
  gap: 0.5rem;
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
  width: 550px;
}

.modal-large {
  width: 700px;
  max-height: 85vh;
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
  padding-top: 1rem;
}

.form-section {
  margin-bottom: 1.5rem;
  padding-bottom: 1.5rem;
  border-bottom: 1px solid var(--border-color);
}

.form-section:last-child {
  border-bottom: none;
  margin-bottom: 0;
  padding-bottom: 0;
}

.form-section h4 {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 1rem 0;
}

.form-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
}

.form-group {
  margin-bottom: 1rem;
  position: relative;
}

.form-row .form-group {
  margin-bottom: 0;
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
  font-family: inherit;
  resize: vertical;
  min-height: 44px;
}

.form-input:focus {
  border-color: var(--primary-color);
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.form-input:disabled {
  background-color: var(--bg-secondary);
  cursor: not-allowed;
}

.form-hint {
  font-size: 0.75rem;
  color: var(--text-secondary);
  margin-top: 0.25rem;
  line-height: 1.5;
}

.form-hint code {
  font-family: 'Courier New', monospace;
  background-color: var(--bg-secondary);
  padding: 0.125rem 0.375rem;
  border-radius: 4px;
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

.checkbox-group {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  cursor: pointer;
}

.delete-info {
  color: var(--text-secondary);
  font-size: 0.875rem;
  margin-top: 0.5rem;
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

.action-btn {
  min-width: auto;
  padding: 0.375rem 0.75rem;
}

.action-btn-danger {
  color: var(--error-color);
}

.action-btn-danger:hover:not(:disabled) {
  background-color: rgba(239, 68, 68, 0.1);
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

.toast.info {
  background-color: var(--primary-color);
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
  
  .registry-card-header {
    flex-direction: column;
    gap: 1rem;
  }
  
  .modal {
    max-width: 100%;
    max-height: 95vh;
  }
  
  .modal-large {
    width: 100%;
  }
  
  .form-row {
    grid-template-columns: 1fr;
  }
}
</style>
