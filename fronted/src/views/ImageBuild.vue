<template>
  <div class="image-build">
    <header class="header">
      <div class="container">
        <div class="header-content">
          <div class="page-title">
            <router-link to="/" class="back-link">
              ← 返回容器列表
            </router-link>
            <h1>镜像构建</h1>
          </div>
          <div class="header-actions">
            <div class="service-status" :class="buildServiceAvailable ? 'available' : 'unavailable'">
              <span class="status-dot"></span>
              <span class="status-text">Docker: {{ buildServiceAvailable ? '可用' : '模拟模式' }}</span>
            </div>
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

    <main class="main-content">
      <div class="container">
        <div class="action-bar">
          <button class="btn btn-primary" @click="openBuildModal">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 19l7-7 3 3-7 7-3-3z"></path>
              <path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5z"></path>
              <path d="M2 2l7.586 7.586"></path>
              <circle cx="11" cy="11" r="2"></circle>
            </svg>
            新建构建
          </button>
          <button class="btn btn-outline" @click="fetchBuilds">
            刷新
          </button>
          <div class="search-box">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="11" cy="11" r="8"></circle>
              <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
            </svg>
            <input 
              type="text" 
              v-model="searchQuery" 
              placeholder="搜索镜像标签..."
              @keyup.enter="fetchBuilds"
            />
          </div>
          <select v-model="filterStatus" class="form-input" @change="fetchBuilds">
            <option value="">全部状态</option>
            <option value="pending">待执行</option>
            <option value="building">构建中</option>
            <option value="completed">已完成</option>
            <option value="failed">失败</option>
          </select>
        </div>

        <div v-if="loading" class="loading-state">
          <div class="loading-spinner"></div>
          <p>加载中...</p>
        </div>

        <div v-else-if="error" class="error-state">
          <div class="error-icon">⚠️</div>
          <p>{{ error }}</p>
          <button class="btn btn-primary" @click="fetchBuilds">重试</button>
        </div>

        <div v-else class="build-list-container">
          <div v-if="builds.length === 0" class="empty-state">
            <div class="empty-icon">🐳</div>
            <p>暂无构建记录</p>
            <p class="text-muted">点击上方"新建构建"按钮开始构建镜像</p>
          </div>

          <div v-else class="build-list">
            <div 
              v-for="build in builds" 
              :key="build.id" 
              class="build-card"
              @click="viewBuildDetail(build)"
            >
              <div class="build-card-header">
                <div class="build-icon" :class="build.status">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M12 19l7-7 3 3-7 7-3-3z"></path>
                    <path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5z"></path>
                  </svg>
                </div>
                <div class="build-info">
                  <div class="build-tag">{{ build.tag }}</div>
                  <div class="build-meta">
                    <span class="meta-item">
                      <span class="status-badge" :class="build.status">
                        {{ getStatusText(build.status) }}
                      </span>
                    </span>
                    <span class="meta-item" v-if="build.status === 'building'">
                      进度: {{ build.progress }}% - {{ build.progress_message }}
                    </span>
                    <span class="meta-item" v-else-if="build.status === 'completed'">
                      <span v-if="build.image_size" class="build-size">
                        大小: {{ formatBytes(build.image_size) }}
                      </span>
                      <span v-if="build.layers_count" class="build-layers">
                        层数: {{ build.layers_count }}
                      </span>
                    </span>
                    <span class="meta-item" v-if="build.created_at">
                      {{ formatDateTime(build.created_at) }}
                    </span>
                  </div>
                </div>
              </div>
              <div class="build-card-footer" v-if="build.dockerfile_path">
                <div class="build-dockerfile">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                    <polyline points="14 2 14 8 20 8"></polyline>
                    <line x1="16" y1="13" x2="8" y2="13"></line>
                    <line x1="16" y1="17" x2="8" y2="17"></line>
                    <polyline points="10 9 9 9 8 9"></polyline>
                  </svg>
                  <span>Dockerfile: {{ build.dockerfile_path }}</span>
                </div>
              </div>
            </div>
          </div>

          <div v-if="totalPages > 1" class="pagination">
            <button 
              class="btn btn-outline btn-sm" 
              @click="currentPage = currentPage - 1; fetchBuilds()"
              :disabled="currentPage <= 1"
            >
              上一页
            </button>
            <span class="page-info">
              第 {{ currentPage }} 页 / 共 {{ totalPages }} 页 ({{ total }} 条记录)
            </span>
            <button 
              class="btn btn-outline btn-sm" 
              @click="currentPage = currentPage + 1; fetchBuilds()"
              :disabled="currentPage >= totalPages"
            >
              下一页
            </button>
          </div>
        </div>
      </div>
    </main>

    <div v-if="showBuildModal" class="modal-overlay" @click.self="closeBuildModal">
      <div class="modal modal-large">
        <div class="modal-header">
          <h3 class="modal-title">新建镜像构建</h3>
          <button class="modal-close" @click="closeBuildModal">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <div v-if="buildModalError" class="form-error">{{ buildModalError }}</div>
          
          <form @submit.prevent="handleBuildImage">
            <div class="form-group">
              <label class="form-label">镜像标签 <span class="required">*</span></label>
              <input 
                type="text" 
                v-model="buildForm.tag" 
                class="form-input"
                placeholder="例如: myimage:latest, registry.example.com/myimage:v1.0"
                :disabled="buildModalLoading"
                required
              />
              <p class="form-hint">输入要构建的镜像标签，包含版本号</p>
            </div>
            
            <div class="form-group">
              <label class="form-label">构建方式</label>
              <div class="build-mode-tabs">
                <button 
                  type="button" 
                  class="mode-tab" 
                  :class="{ active: buildMode === 'path' }"
                  @click="buildMode = 'path'"
                >
                  Dockerfile 路径
                </button>
                <button 
                  type="button" 
                  class="mode-tab" 
                  :class="{ active: buildMode === 'content' }"
                  @click="buildMode = 'content'"
                >
                  Dockerfile 内容
                </button>
              </div>
            </div>
            
            <template v-if="buildMode === 'path'">
              <div class="form-group">
                <label class="form-label">Dockerfile 路径 <span class="required">*</span></label>
                <input 
                  type="text" 
                  v-model="buildForm.dockerfile_path" 
                  class="form-input"
                  placeholder="例如: ./Dockerfile, ./path/to/Dockerfile.prod"
                  :disabled="buildModalLoading"
                />
                <p class="form-hint">Dockerfile 相对于构建上下文的路径</p>
              </div>
              
              <div class="form-group">
                <label class="form-label">构建上下文路径（可选）</label>
                <input 
                  type="text" 
                  v-model="buildForm.context_path" 
                  class="form-input"
                  placeholder="例如: ./, ./src"
                  :disabled="buildModalLoading"
                />
                <p class="form-hint">构建上下文目录，默认为 Dockerfile 所在目录</p>
              </div>
            </template>
            
            <template v-else>
              <div class="form-group">
                <label class="form-label">Dockerfile 内容 <span class="required">*</span></label>
                <textarea 
                  v-model="buildForm.dockerfile_content" 
                  class="form-input"
                  placeholder="例如:&#10;FROM nginx:alpine&#10;COPY ./dist /usr/share/nginx/html&#10;EXPOSE 80"
                  :disabled="buildModalLoading"
                  rows="8"
                ></textarea>
                <p class="form-hint">直接输入 Dockerfile 的内容</p>
              </div>
            </template>
            
            <div class="form-section">
              <h4>高级选项</h4>
              
              <div class="form-group">
                <label class="form-label">构建参数 (Build Args)</label>
                <div class="key-value-pairs">
                  <div v-for="(arg, index) in buildArgs" :key="index" class="key-value-row">
                    <input 
                      type="text" 
                      v-model="arg.key" 
                      class="form-input key-input"
                      placeholder="KEY"
                      :disabled="buildModalLoading"
                    />
                    <span class="separator">=</span>
                    <input 
                      type="text" 
                      v-model="arg.value" 
                      class="form-input value-input"
                      placeholder="value"
                      :disabled="buildModalLoading"
                    />
                    <button 
                      type="button" 
                      class="btn btn-ghost btn-sm remove-btn"
                      @click="removeBuildArg(index)"
                      :disabled="buildModalLoading"
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                      </svg>
                    </button>
                  </div>
                </div>
                <button 
                  type="button" 
                  class="btn btn-outline btn-sm add-arg-btn"
                  @click="addBuildArg"
                  :disabled="buildModalLoading"
                >
                  + 添加构建参数
                </button>
              </div>
              
              <div class="form-group">
                <label class="form-label">目标平台（可选）</label>
                <input 
                  type="text" 
                  v-model="buildForm.platform" 
                  class="form-input"
                  placeholder="例如: linux/amd64, linux/arm64"
                  :disabled="buildModalLoading"
                />
              </div>
              
              <div class="form-group">
                <label class="form-label">标签 (Labels)</label>
                <input 
                  type="text" 
                  v-model="buildLabelsInput" 
                  class="form-input"
                  placeholder="例如: maintainer=dev@example.com, version=1.0.0"
                  :disabled="buildModalLoading"
                />
                <p class="form-hint">用逗号分隔的键值对</p>
              </div>
              
              <div class="checkbox-group">
                <label class="checkbox-label">
                  <input 
                    type="checkbox" 
                    v-model="buildForm.pull"
                    :disabled="buildModalLoading"
                  />
                  <span>构建时拉取最新基础镜像</span>
                </label>
                <label class="checkbox-label">
                  <input 
                    type="checkbox" 
                    v-model="buildForm.no_cache"
                    :disabled="buildModalLoading"
                  />
                  <span>不使用缓存，强制重新构建所有层</span>
                </label>
              </div>
            </div>
            
            <div class="modal-footer">
              <button type="button" class="btn btn-outline" @click="closeBuildModal" :disabled="buildModalLoading">
                取消
              </button>
              <button type="submit" class="btn btn-primary" :disabled="buildModalLoading || !buildForm.tag">
                {{ buildModalLoading ? '提交中...' : '开始构建' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <div v-if="showDetailModal" class="modal-overlay modal-large" @click.self="closeDetailModal">
      <div class="modal modal-xlarge">
        <div class="modal-header">
          <h3 class="modal-title">构建详情 - {{ selectedBuild?.tag }}</h3>
          <div class="modal-actions">
            <button v-if="selectedBuild?.status === 'completed'" class="btn btn-outline btn-sm" @click="viewBuildLogs">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
                <line x1="16" y1="13" x2="8" y2="13"></line>
                <line x1="16" y1="17" x2="8" y2="17"></line>
              </svg>
              查看日志
            </button>
            <button class="modal-close" @click="closeDetailModal">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>
        </div>
        <div class="modal-body">
          <div v-if="detailLoading" class="loading-state">
            <div class="loading-spinner"></div>
            <p>加载中...</p>
          </div>
          <div v-else-if="buildDetail">
            <div class="detail-section">
              <h4>基本信息</h4>
              <div class="detail-grid">
                <div class="detail-item">
                  <span class="detail-label">状态</span>
                  <span class="status-badge" :class="buildDetail.status">
                    {{ getStatusText(buildDetail.status) }}
                  </span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">镜像标签</span>
                  <span class="detail-value">{{ buildDetail.tag }}</span>
                </div>
                <div v-if="buildDetail.target_image_id" class="detail-item">
                  <span class="detail-label">镜像 ID</span>
                  <span class="detail-value">{{ buildDetail.target_image_id }}</span>
                </div>
                <div v-if="buildDetail.image_size" class="detail-item">
                  <span class="detail-label">镜像大小</span>
                  <span class="detail-value">{{ formatBytes(buildDetail.image_size) }}</span>
                </div>
                <div v-if="buildDetail.layers_count" class="detail-item">
                  <span class="detail-label">层数</span>
                  <span class="detail-value">{{ buildDetail.layers_count }}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">创建时间</span>
                  <span class="detail-value">{{ formatDateTime(buildDetail.created_at) }}</span>
                </div>
                <div v-if="buildDetail.completed_at" class="detail-item">
                  <span class="detail-label">完成时间</span>
                  <span class="detail-value">{{ formatDateTime(buildDetail.completed_at) }}</span>
                </div>
              </div>
            </div>

            <div v-if="buildDetail.dockerfile_path || buildDetail.dockerfile_content" class="detail-section">
              <h4>Dockerfile</h4>
              <div v-if="buildDetail.dockerfile_path" class="detail-item-full">
                <span class="detail-label">路径:</span>
                <span class="detail-value">{{ buildDetail.dockerfile_path }}</span>
              </div>
              <div v-if="buildDetail.dockerfile_content" class="dockerfile-content">
                <pre><code>{{ buildDetail.dockerfile_content }}</code></pre>
              </div>
            </div>

            <div v-if="buildDetail.build_args" class="detail-section">
              <h4>构建参数</h4>
              <div class="key-value-list">
                <div v-for="(value, key) in buildDetail.build_args" :key="key" class="key-value-item">
                  <span class="arg-key">{{ key }}</span>
                  <span class="arg-separator">=</span>
                  <span class="arg-value">{{ value }}</span>
                </div>
              </div>
            </div>

            <div v-if="buildDetail.error_message" class="detail-section">
              <h4>错误信息</h4>
              <div class="error-box">
                <pre>{{ buildDetail.error_message }}</pre>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="showLogsModal" class="modal-overlay modal-large" @click.self="closeLogsModal">
      <div class="modal modal-full">
        <div class="modal-header">
          <h3 class="modal-title">构建日志 - {{ selectedBuild?.tag }}</h3>
          <button class="modal-close" @click="closeLogsModal">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        <div class="modal-body logs-body">
          <div v-if="logsLoading" class="loading-state">
            <div class="loading-spinner"></div>
            <p>加载日志中...</p>
          </div>
          <div v-else-if="buildLogs" class="logs-container">
            <div v-if="buildLogs.log_entries && buildLogs.log_entries.length > 0" class="structured-logs">
              <div 
                v-for="(entry, index) in buildLogs.log_entries" 
                :key="index" 
                class="log-entry"
                :class="entry.stream"
              >
                <span class="log-timestamp" v-if="entry.timestamp">{{ formatLogTimestamp(entry.timestamp) }}</span>
                <span class="log-stream">{{ entry.stream || 'info' }}</span>
                <span class="log-message">{{ entry.text || entry.message }}</span>
              </div>
            </div>
            <div v-else-if="buildLogs.logs" class="raw-logs">
              <pre><code>{{ buildLogs.logs }}</code></pre>
            </div>
            <div v-else class="empty-state">
              <p>暂无日志</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="showDeleteConfirm" class="modal-overlay" @click.self="closeDeleteConfirm">
      <div class="modal modal-small">
        <div class="modal-header">
          <h3 class="modal-title">确认删除</h3>
        </div>
        <div class="modal-body">
          <p>确定要删除构建记录 "<strong>{{ deletingBuild?.tag }}</strong>" 吗？</p>
          
          <div class="modal-footer">
            <button type="button" class="btn btn-outline" @click="closeDeleteConfirm" :disabled="deleteConfirmLoading">
              取消
            </button>
            <button type="button" class="btn btn-danger" @click="executeDeleteBuild" :disabled="deleteConfirmLoading">
              {{ deleteConfirmLoading ? '删除中...' : '确认删除' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="toastMessage" class="toast" :class="toastType">
      {{ toastMessage }}
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../composables/useAuth'
import { buildApi } from '../api/containerApi'


const router = useRouter()
const { isAdmin, currentUser, logout } = useAuth()


if (!isAdmin.value) {
  router.push('/')
}


const buildServiceAvailable = ref(false)

const builds = ref([])
const loading = ref(true)
const error = ref(null)
const searchQuery = ref('')
const filterStatus = ref('')
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const totalPages = ref(0)

const selectedBuild = ref(null)
const buildDetail = ref(null)
const buildLogs = ref(null)
const detailLoading = ref(false)
const logsLoading = ref(false)

const buildMode = ref('path')
const showBuildModal = ref(false)
const buildModalLoading = ref(false)
const buildModalError = ref('')
const buildForm = ref({
  tag: '',
  dockerfile_path: '',
  dockerfile_content: '',
  context_path: '',
  build_args: {},
  platform: '',
  cache_from: [],
  labels: {},
  pull: false,
  no_cache: false
})

const buildArgs = ref([{ key: '', value: '' }])
const buildLabelsInput = ref('')

const showDetailModal = ref(false)
const showLogsModal = ref(false)
const showDeleteConfirm = ref(false)
const deletingBuild = ref(null)
const deleteConfirmLoading = ref(false)

const toastMessage = ref('')
const toastType = ref('success')
let toastTimeout = null


const fetchBuildServiceStatus = async () => {
  try {
    const result = await buildApi.getBuildServiceStatus()
    if (result.success) {
      buildServiceAvailable.value = result.data?.available ?? false
    }
  } catch (err) {
    console.error('获取构建服务状态失败:', err)
  }
}


const fetchBuilds = async () => {
  try {
    loading.value = true
    error.value = null
    
    const params = {
      page: currentPage.value,
      page_size: pageSize.value
    }
    
    if (searchQuery.value) {
      params.search = searchQuery.value
    }
    if (filterStatus.value) {
      params.status = filterStatus.value
    }
    
    const result = await buildApi.getBuilds(params)
    
    if (result.success) {
      builds.value = result.data?.builds || []
      total.value = result.data?.total || 0
      totalPages.value = result.data?.total_pages || 1
    } else {
      error.value = result.message || '获取构建列表失败'
    }
  } catch (err) {
    error.value = err.message || '获取构建列表失败'
  } finally {
    loading.value = false
  }
}


const getStatusText = (status) => {
  const map = {
    pending: '待执行',
    building: '构建中',
    completed: '已完成',
    failed: '失败',
    cancelled: '已取消'
  }
  return map[status] || status
}


const formatDateTime = (dateStr) => {
  if (!dateStr) return 'N/A'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}


const formatBytes = (bytes) => {
  if (bytes === 0 || !bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}


const formatLogTimestamp = (timestamp) => {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  return date.toLocaleTimeString('zh-CN')
}


const openBuildModal = () => {
  buildMode.value = 'path'
  buildForm.value = {
    tag: '',
    dockerfile_path: '',
    dockerfile_content: '',
    context_path: '',
    build_args: {},
    platform: '',
    cache_from: [],
    labels: {},
    pull: false,
    no_cache: false
  }
  buildArgs.value = [{ key: '', value: '' }]
  buildLabelsInput.value = ''
  buildModalError.value = ''
  showBuildModal.value = true
}


const closeBuildModal = () => {
  showBuildModal.value = false
  buildForm.value = {
    tag: '',
    dockerfile_path: '',
    dockerfile_content: '',
    context_path: '',
    build_args: {},
    platform: '',
    cache_from: [],
    labels: {},
    pull: false,
    no_cache: false
  }
  buildArgs.value = [{ key: '', value: '' }]
  buildLabelsInput.value = ''
  buildModalError.value = ''
}


const addBuildArg = () => {
  buildArgs.value.push({ key: '', value: '' })
}


const removeBuildArg = (index) => {
  if (buildArgs.value.length > 1) {
    buildArgs.value.splice(index, 1)
  }
}


const handleBuildImage = async () => {
  if (!buildForm.value.tag) {
    buildModalError.value = '请输入镜像标签'
    return
  }
  
  if (buildMode.value === 'path' && !buildForm.value.dockerfile_path) {
    buildModalError.value = '请输入 Dockerfile 路径'
    return
  }
  
  if (buildMode.value === 'content' && !buildForm.value.dockerfile_content) {
    buildModalError.value = '请输入 Dockerfile 内容'
    return
  }
  
  try {
    buildModalLoading.value = true
    buildModalError.value = ''
    
    const data = {
      tag: buildForm.value.tag
    }
    
    if (buildMode.value === 'path') {
      data.dockerfile_path = buildForm.value.dockerfile_path
      if (buildForm.value.context_path) {
        data.context_path = buildForm.value.context_path
      }
    } else {
      data.dockerfile_content = buildForm.value.dockerfile_content
    }
    
    const buildArgsObj = {}
    for (const arg of buildArgs.value) {
      if (arg.key.trim()) {
        buildArgsObj[arg.key.trim()] = arg.value
      }
    }
    if (Object.keys(buildArgsObj).length > 0) {
      data.build_args = buildArgsObj
    }
    
    if (buildForm.value.platform) {
      data.platform = buildForm.value.platform
    }
    
    if (buildLabelsInput.value.trim()) {
      const labels = {}
      const pairs = buildLabelsInput.value.split(',')
      for (const pair of pairs) {
        const [key, value] = pair.split('=')
        if (key && value) {
          labels[key.trim()] = value.trim()
        }
      }
      if (Object.keys(labels).length > 0) {
        data.labels = labels
      }
    }
    
    if (buildForm.value.pull) {
      data.pull = true
    }
    if (buildForm.value.no_cache) {
      data.no_cache = true
    }
    
    const result = await buildApi.buildImage(data)
    
    if (result.success) {
      showToast('构建任务已提交', 'success')
      closeBuildModal()
      fetchBuilds()
    } else {
      buildModalError.value = result.message || '提交构建任务失败'
    }
  } catch (err) {
    buildModalError.value = err.message || '提交构建任务失败'
  } finally {
    buildModalLoading.value = false
  }
}


const viewBuildDetail = async (build) => {
  selectedBuild.value = build
  detailLoading.value = true
  showDetailModal.value = true
  
  try {
    const result = await buildApi.getBuildDetail(build.id)
    
    if (result.success) {
      buildDetail.value = result.data
    }
  } catch (err) {
    console.error('获取构建详情失败:', err)
  } finally {
    detailLoading.value = false
  }
}


const closeDetailModal = () => {
  showDetailModal.value = false
  buildDetail.value = null
  selectedBuild.value = null
}


const viewBuildLogs = async () => {
  if (!selectedBuild.value) return
  
  logsLoading.value = true
  showLogsModal.value = true
  
  try {
    const result = await buildApi.getBuildLogs(selectedBuild.value.id)
    
    if (result.success) {
      buildLogs.value = result.data
    }
  } catch (err) {
    console.error('获取构建日志失败:', err)
  } finally {
    logsLoading.value = false
  }
}


const closeLogsModal = () => {
  showLogsModal.value = false
  buildLogs.value = null
}


const confirmDeleteBuild = (build) => {
  deletingBuild.value = build
  showDeleteConfirm.value = true
}


const closeDeleteConfirm = () => {
  showDeleteConfirm.value = false
  deletingBuild.value = null
}


const executeDeleteBuild = async () => {
  if (!deletingBuild.value) return
  
  try {
    deleteConfirmLoading.value = true
    
    const result = await buildApi.deleteBuild(deletingBuild.value.id)
    
    if (result.success) {
      showToast('构建记录删除成功', 'success')
      closeDeleteConfirm()
      fetchBuilds()
    } else {
      showToast(result.message || '删除失败', 'error')
    }
  } catch (err) {
    showToast(err.message || '删除失败', 'error')
  } finally {
    deleteConfirmLoading.value = false
  }
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
  fetchBuildServiceStatus()
  fetchBuilds()
})


let refreshInterval
const startAutoRefresh = () => {
  refreshInterval = setInterval(() => {
    const hasRunningBuilds = builds.value.some(s => s.status === 'pending' || s.status === 'building')
    if (hasRunningBuilds) {
      fetchBuilds()
    }
  }, 5000)
}

const stopAutoRefresh = () => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
}

watch(builds, (newBuilds) => {
  const hasRunning = newBuilds.some(s => s.status === 'pending' || s.status === 'building')
  if (hasRunning && !refreshInterval) {
    startAutoRefresh()
  } else if (!hasRunning && refreshInterval) {
    stopAutoRefresh()
  }
}, { deep: true })
</script>

<style scoped>
.image-build {
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

.service-status {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.375rem 0.75rem;
  border-radius: 8px;
  font-size: 0.75rem;
}

.service-status.available {
  background-color: rgba(16, 185, 129, 0.1);
  color: #10b981;
}

.service-status.unavailable {
  background-color: rgba(245, 158, 11, 0.1);
  color: #d97706;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: currentColor;
}

.main-content {
  padding: 1.5rem 0;
}

.container {
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 1rem;
}

.action-bar {
  display: flex;
  gap: 0.75rem;
  margin-bottom: 1.5rem;
  align-items: center;
  flex-wrap: wrap;
}

.search-box {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background-color: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  padding: 0.5rem 0.75rem;
  flex: 1;
  min-width: 200px;
}

.search-box input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  color: var(--text-primary);
  font-size: 0.875rem;
}

.search-box input::placeholder {
  color: var(--text-secondary);
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

.build-list-container {
  background-color: var(--bg-primary);
  border-radius: 0.75rem;
  padding: 1.5rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.build-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.build-card {
  background-color: var(--bg-secondary);
  border-radius: 0.75rem;
  border: 1px solid var(--border-color);
  padding: 1.25rem;
  cursor: pointer;
  transition: all 0.2s;
}

.build-card:hover {
  border-color: var(--primary-color);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
}

.build-card-header {
  display: flex;
  gap: 1rem;
  align-items: center;
}

.build-icon {
  width: 40px;
  height: 40px;
  border-radius: 0.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.build-icon.pending {
  background-color: rgba(156, 163, 175, 0.1);
  color: #9ca3af;
}

.build-icon.building {
  background-color: rgba(59, 130, 246, 0.1);
  color: #3b82f6;
}

.build-icon.completed {
  background-color: rgba(34, 197, 94, 0.1);
  color: #22c55e;
}

.build-icon.failed {
  background-color: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}

.build-info {
  flex: 1;
  min-width: 0;
}

.build-tag {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 0.5rem;
  word-break: break-all;
  font-family: 'Courier New', monospace;
}

.build-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.status-badge {
  display: inline-block;
  padding: 0.125rem 0.5rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 500;
}

.status-badge.pending {
  background-color: rgba(156, 163, 175, 0.1);
  color: #9ca3af;
}

.status-badge.building {
  background-color: rgba(59, 130, 246, 0.1);
  color: #3b82f6;
}

.status-badge.completed {
  background-color: rgba(34, 197, 94, 0.1);
  color: #22c55e;
}

.status-badge.failed {
  background-color: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}

.build-size,
.build-layers {
  font-weight: 500;
  color: var(--text-primary);
}

.build-card-footer {
  margin-top: 0.75rem;
  padding-top: 0.75rem;
  border-top: 1px solid var(--border-color);
}

.build-dockerfile {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.75rem;
  color: var(--text-secondary);
  font-family: 'Courier New', monospace;
}

.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  margin-top: 1.5rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border-color);
}

.page-info {
  font-size: 0.875rem;
  color: var(--text-secondary);
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
  width: 800px;
  max-height: 85vh;
}

.modal-xlarge {
  width: 1000px;
  max-height: 85vh;
}

.modal-full {
  width: 90vw;
  max-height: 90vh;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
}

.modal-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
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

.logs-body {
  padding: 0;
  overflow: hidden;
}

.logs-container {
  height: 100%;
  overflow-y: auto;
  padding: 1.5rem;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  padding-top: 1rem;
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

.form-error {
  background-color: #fef2f2;
  border: 1px solid #fecaca;
  color: #dc2626;
  padding: 0.75rem 1rem;
  border-radius: 8px;
  margin-bottom: 1rem;
  font-size: 0.875rem;
}

.form-section {
  margin-top: 1.5rem;
  padding-top: 1.5rem;
  border-top: 1px solid var(--border-color);
}

.form-section h4 {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 1rem 0;
}

.build-mode-tabs {
  display: flex;
  gap: 0.5rem;
}

.mode-tab {
  padding: 0.5rem 1rem;
  border: 1px solid var(--border-color);
  background-color: var(--bg-primary);
  border-radius: 0.375rem;
  cursor: pointer;
  font-size: 0.875rem;
  transition: all 0.2s;
}

.mode-tab:hover {
  border-color: var(--primary-color);
}

.mode-tab.active {
  background-color: var(--primary-color);
  color: white;
  border-color: var(--primary-color);
}

.key-value-pairs {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.key-value-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.key-input {
  flex: 1;
  max-width: 200px;
}

.value-input {
  flex: 2;
}

.separator {
  color: var(--text-secondary);
  font-weight: 600;
}

.remove-btn {
  color: var(--error-color);
}

.remove-btn:hover:not(:disabled) {
  background-color: rgba(239, 68, 68, 0.1);
}

.add-arg-btn {
  margin-top: 0.5rem;
}

.checkbox-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  cursor: pointer;
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

.detail-section {
  margin-bottom: 1.5rem;
}

.detail-section h4 {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 1rem 0;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border-color);
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.detail-item-full {
  display: flex;
  gap: 0.5rem;
}

.detail-label {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.detail-value {
  font-size: 0.875rem;
  color: var(--text-primary);
  font-family: 'Courier New', monospace;
  word-break: break-all;
}

.dockerfile-content {
  background-color: var(--bg-secondary);
  border-radius: 0.375rem;
  padding: 1rem;
  overflow-x: auto;
}

.dockerfile-content pre {
  margin: 0;
}

.dockerfile-content code {
  font-size: 0.875rem;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-all;
}

.key-value-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.key-value-item {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.375rem 0.75rem;
  background-color: var(--bg-secondary);
  border-radius: 0.25rem;
}

.arg-key {
  font-family: 'Courier New', monospace;
  font-size: 0.875rem;
  color: var(--primary-color);
  font-weight: 600;
}

.arg-separator {
  color: var(--text-secondary);
}

.arg-value {
  font-family: 'Courier New', monospace;
  font-size: 0.875rem;
  color: var(--text-primary);
}

.error-box {
  background-color: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 0.375rem;
  padding: 1rem;
}

.error-box pre {
  margin: 0;
  font-size: 0.875rem;
  color: #dc2626;
  white-space: pre-wrap;
  word-break: break-all;
}

.structured-logs {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.log-entry {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  padding: 0.25rem 0.5rem;
  border-radius: 0.25rem;
  font-family: 'Courier New', monospace;
  font-size: 0.875rem;
}

.log-entry.stdout {
  background-color: rgba(34, 197, 94, 0.05);
}

.log-entry.stderr {
  background-color: rgba(239, 68, 68, 0.05);
}

.log-timestamp {
  color: var(--text-secondary);
  font-size: 0.75rem;
  flex-shrink: 0;
}

.log-stream {
  padding: 0.125rem 0.375rem;
  border-radius: 0.125rem;
  font-size: 0.625rem;
  font-weight: 600;
  flex-shrink: 0;
}

.log-entry.stdout .log-stream {
  background-color: rgba(34, 197, 94, 0.1);
  color: #22c55e;
}

.log-entry.stderr .log-stream {
  background-color: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}

.log-message {
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-all;
}

.raw-logs {
  background-color: var(--bg-secondary);
  border-radius: 0.375rem;
  padding: 1rem;
}

.raw-logs pre {
  margin: 0;
}

.raw-logs code {
  font-size: 0.875rem;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-all;
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
  
  .action-bar {
    flex-direction: column;
    align-items: stretch;
  }
  
  .search-box {
    min-width: 100%;
  }
  
  .modal {
    max-width: 100%;
    max-height: 95vh;
  }
  
  .modal-medium,
  .modal-large,
  .modal-xlarge,
  .modal-full {
    width: 100%;
  }
  
  .build-mode-tabs {
    flex-wrap: wrap;
  }
  
  .key-value-row {
    flex-wrap: wrap;
  }
}
</style>
