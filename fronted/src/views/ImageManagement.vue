<template>
  <AppLayout
    :currentUser="currentUser"
    :page-title="'镜像管理'"
    @refresh="fetchImages"
    @logout="logout"
  >
        <div class="action-bar">
          <button class="btn btn-primary" @click="openPullModal">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
              <polyline points="17 8 12 3 7 8"></polyline>
              <line x1="12" y1="3" x2="12" y2="15"></line>
            </svg>
            拉取镜像
          </button>
          <button class="btn btn-outline" @click="fetchImages">
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
              placeholder="搜索镜像名称、标签..."
              @keyup.enter="fetchImages"
            />
          </div>
        </div>

        <div v-if="loading" class="loading-state">
          <div class="loading-spinner"></div>
          <p>加载中...</p>
        </div>

        <div v-else-if="error" class="error-state">
          <div class="error-icon">⚠️</div>
          <p>{{ error }}</p>
          <button class="btn btn-primary" @click="fetchImages">重试</button>
        </div>

        <div v-else class="image-list-container">
          <div v-if="images.length === 0" class="empty-state">
            <div class="empty-icon">🖼️</div>
            <p>暂无镜像</p>
            <p class="text-muted">点击上方"拉取镜像"按钮来拉取新镜像</p>
          </div>

          <div v-else class="image-list">
            <div 
              v-for="image in images" 
              :key="image.id" 
              class="image-card"
            >
              <div class="image-card-header">
                <div class="image-icon">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M20 7h-9l-2-2H4a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2z"></path>
                    <circle cx="18" cy="13" r="2"></circle>
                    <path d="M10 13h4"></path>
                    <path d="M6 13h2"></path>
                  </svg>
                </div>
                <div class="image-info">
                  <div class="image-name">
                    <span class="primary-name">{{ image.repo_tags?.[0]?.split(':')[0] || '<none>' }}</span>
                    <span class="badge badge-primary" v-if="image.repo_tags?.length > 0">
                      {{ image.repo_tags[0].split(':')[1] || 'latest' }}
                    </span>
                    <span class="badge badge-secondary" v-if="image.repo_tags?.length > 1">
                      +{{ image.repo_tags.length - 1 }} 标签
                    </span>
                  </div>
                  <div class="image-meta">
                    <span class="meta-item">
                      <span class="meta-label">ID:</span>
                      <span class="meta-value">{{ image.short_id }}</span>
                    </span>
                    <span class="meta-item">
                      <span class="meta-label">大小:</span>
                      <span class="meta-value">{{ formatBytes(image.size) }}</span>
                    </span>
                    <span class="meta-item" v-if="image.created">
                      <span class="meta-label">创建时间:</span>
                      <span class="meta-value">{{ formatDate(image.created) }}</span>
                    </span>
                  </div>
                </div>
              </div>
              <div class="image-card-footer">
                <div class="action-buttons">
                  <button 
                    class="btn btn-ghost btn-sm action-btn"
                    @click="viewImageDetail(image)"
                    title="查看详情"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                      <circle cx="12" cy="12" r="3"></circle>
                    </svg>
                    详情
                  </button>
                  <button 
                    class="btn btn-ghost btn-sm action-btn"
                    @click="viewImageHistory(image)"
                    title="查看历史"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <circle cx="12" cy="12" r="10"></circle>
                      <polyline points="12 6 12 12 16 14"></polyline>
                    </svg>
                    历史
                  </button>
                  <button 
                    class="btn btn-ghost btn-sm action-btn"
                    @click="openTagModal(image)"
                    title="标签管理"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"></path>
                      <line x1="7" y1="7" x2="7.01" y2="7"></line>
                    </svg>
                    标签
                  </button>
                  <button 
                    class="btn btn-ghost btn-sm action-btn"
                    @click="openPushModal(image)"
                    title="推送镜像"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                      <polyline points="17 8 12 3 7 8"></polyline>
                      <line x1="12" y1="3" x2="12" y2="15"></line>
                    </svg>
                    推送
                  </button>
                  <button 
                    class="btn btn-ghost btn-sm action-btn action-btn-danger"
                    @click="confirmDeleteImage(image)"
                    title="删除镜像"
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

          <div v-if="totalPages > 1" class="pagination">
            <button 
              class="btn btn-outline btn-sm" 
              @click="currentPage = currentPage - 1; fetchImages()"
              :disabled="currentPage <= 1"
            >
              上一页
            </button>
            <span class="page-info">
              第 {{ currentPage }} 页 / 共 {{ totalPages }} 页 ({{ total }} 个镜像)
            </span>
            <button 
              class="btn btn-outline btn-sm" 
              @click="currentPage = currentPage + 1; fetchImages()"
              :disabled="currentPage >= totalPages"
            >
              下一页
            </button>
          </div>
        </div>

    <div v-if="showPullModal" class="modal-overlay" @click.self="closePullModal">
      <div class="modal modal-medium">
        <div class="modal-header">
          <h3 class="modal-title">拉取镜像</h3>
          <button class="modal-close" @click="closePullModal">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <div v-if="pullModalError" class="form-error">{{ pullModalError }}</div>
          
          <form @submit.prevent="handlePullImage">
            <div class="form-group">
              <label class="form-label">镜像名称 <span class="required">*</span></label>
              <input 
                type="text" 
                v-model="pullForm.image" 
                class="form-input"
                placeholder="例如: nginx, ubuntu, registry.example.com/my-image"
                :disabled="pullModalLoading"
                required
              />
              <p class="form-hint">输入要拉取的镜像名称，可以包含标签，如 nginx:1.21</p>
            </div>
            
            <div class="form-group">
              <label class="form-label">标签（可选）</label>
              <input 
                type="text" 
                v-model="pullForm.tag" 
                class="form-input"
                placeholder="例如: latest, 1.21, alpine"
                :disabled="pullModalLoading"
              />
              <p class="form-hint">如果在镜像名称中已指定标签，可忽略此项</p>
            </div>
            
            <div class="form-group">
              <label class="form-label">目标平台（可选）</label>
              <input 
                type="text" 
                v-model="pullForm.platform" 
                class="form-input"
                placeholder="例如: linux/amd64, linux/arm64"
                :disabled="pullModalLoading"
              />
            </div>
            
            <div class="form-group">
              <label class="form-label">使用仓库配置（可选）</label>
              <select 
                v-model="pullForm.registry_id" 
                class="form-input"
                :disabled="pullModalLoading || registries.length === 0"
              >
                <option :value="null">不使用私有仓库</option>
                <option v-for="reg in registries" :key="reg.id" :value="reg.id">
                  {{ reg.name }} ({{ reg.registry_type }})
                </option>
              </select>
              <p class="form-hint" v-if="registries.length === 0">
                暂无已配置的私有仓库，<router-link to="/registries" class="link">点击配置</router-link>
              </p>
            </div>
            
            <div class="modal-footer">
              <button type="button" class="btn btn-outline" @click="closePullModal" :disabled="pullModalLoading">
                取消
              </button>
              <button type="submit" class="btn btn-primary" :disabled="pullModalLoading || !pullForm.image">
                {{ pullModalLoading ? '拉取中...' : '拉取镜像' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <div v-if="showDetailModal" class="modal-overlay modal-large" @click.self="closeDetailModal">
      <div class="modal modal-large">
        <div class="modal-header">
          <h3 class="modal-title">镜像详情</h3>
          <button class="modal-close" @click="closeDetailModal">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <div v-if="detailLoading" class="loading-state">
            <div class="loading-spinner"></div>
            <p>加载中...</p>
          </div>
          <div v-else-if="imageDetail">
            <div class="detail-section">
              <h4>基本信息</h4>
              <div class="detail-grid">
                <div class="detail-item">
                  <span class="detail-label">ID</span>
                  <span class="detail-value">{{ imageDetail.short_id || imageDetail.id }}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">创建时间</span>
                  <span class="detail-value">{{ formatDate(imageDetail.created) }}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">大小</span>
                  <span class="detail-value">{{ formatBytes(imageDetail.size) }}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">虚拟大小</span>
                  <span class="detail-value">{{ formatBytes(imageDetail.virtual_size) }}</span>
                </div>
              </div>
            </div>

            <div class="detail-section" v-if="imageDetail.tags && imageDetail.tags.length > 0">
              <h4>标签</h4>
              <div class="tag-list">
                <span v-for="tag in imageDetail.tags" :key="tag" class="badge badge-info">
                  {{ tag }}
                </span>
              </div>
            </div>

            <div class="detail-section" v-if="imageDetail.layers && imageDetail.layers.length > 0">
              <h4>镜像层 ({{ imageDetail.layers.length }} 层)</h4>
              <div class="layer-list">
                <div v-for="(layer, index) in imageDetail.layers" :key="layer.id || index" class="layer-item">
                  <div class="layer-header">
                    <span class="layer-index">#{{ imageDetail.layers.length - index }}</span>
                    <span class="layer-id">{{ layer.short_id || layer.id }}</span>
                    <span class="layer-size">{{ formatBytes(layer.size) }}</span>
                  </div>
                  <div class="layer-command" v-if="layer.command">
                    <code>{{ layer.command }}</code>
                  </div>
                </div>
              </div>
            </div>

            <div class="detail-section" v-if="imageDetail.config">
              <h4>配置信息</h4>
              <div class="config-json">
                <pre>{{ JSON.stringify(imageDetail.config, null, 2) }}</pre>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="showHistoryModal" class="modal-overlay modal-large" @click.self="closeHistoryModal">
      <div class="modal modal-large">
        <div class="modal-header">
          <h3 class="modal-title">镜像历史</h3>
          <button class="modal-close" @click="closeHistoryModal">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <div v-if="historyLoading" class="loading-state">
            <div class="loading-spinner"></div>
            <p>加载中...</p>
          </div>
          <div v-else-if="imageHistory && imageHistory.length > 0">
            <div class="history-list">
              <div v-for="(item, index) in imageHistory" :key="item.id || index" class="history-item">
                <div class="history-header">
                  <span class="history-index">#{{ imageHistory.length - index }}</span>
                  <span class="history-id">{{ item.short_id || item.id }}</span>
                  <span class="history-size">{{ formatBytes(item.size) }}</span>
                  <span class="history-date" v-if="item.created">{{ formatDate(item.created) }}</span>
                </div>
                <div class="history-command" v-if="item.created_by">
                  <code>{{ item.created_by }}</code>
                </div>
                <div class="history-comment" v-if="item.comment">
                  <p>{{ item.comment }}</p>
                </div>
              </div>
            </div>
          </div>
          <div v-else class="empty-state">
            <p>暂无历史记录</p>
          </div>
        </div>
      </div>
    </div>

    <div v-if="showTagModal" class="modal-overlay" @click.self="closeTagModal">
      <div class="modal modal-medium">
        <div class="modal-header">
          <h3 class="modal-title">标签管理</h3>
          <button class="modal-close" @click="closeTagModal">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <div v-if="tagModalError" class="form-error">{{ tagModalError }}</div>
          
          <div class="form-section">
            <h4>现有标签</h4>
            <div v-if="selectedImage?.repo_tags?.length > 0" class="existing-tags">
              <div v-for="tag in selectedImage.repo_tags" :key="tag" class="tag-item">
                <span class="badge badge-info">{{ tag }}</span>
                <button 
                  class="btn btn-ghost btn-sm action-btn-danger"
                  @click="removeTag(tag)"
                  :disabled="tagModalLoading"
                  title="删除此标签"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                  </svg>
                </button>
              </div>
            </div>
            <div v-else class="text-muted">
              暂无标签
            </div>
          </div>

          <div class="form-section">
            <h4>添加新标签</h4>
            <form @submit.prevent="handleAddTag">
              <div class="form-group">
                <label class="form-label">目标仓库/镜像名 <span class="required">*</span></label>
                <input 
                  type="text" 
                  v-model="tagForm.repository" 
                  class="form-input"
                  placeholder="例如: myimage, registry.example.com/myimage"
                  :disabled="tagModalLoading"
                  required
                />
              </div>
              
              <div class="form-group">
                <label class="form-label">标签 <span class="required">*</span></label>
                <input 
                  type="text" 
                  v-model="tagForm.new_tag" 
                  class="form-input"
                  placeholder="例如: latest, v1.0, stable"
                  :disabled="tagModalLoading"
                  required
                />
              </div>
              
              <div class="modal-footer">
                <button type="button" class="btn btn-outline" @click="closeTagModal" :disabled="tagModalLoading">
                  关闭
                </button>
                <button type="submit" class="btn btn-primary" :disabled="tagModalLoading || !tagForm.repository || !tagForm.new_tag">
                  {{ tagModalLoading ? '添加中...' : '添加标签' }}
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>

    <div v-if="showPushModal" class="modal-overlay" @click.self="closePushModal">
      <div class="modal modal-medium">
        <div class="modal-header">
          <h3 class="modal-title">推送镜像</h3>
          <button class="modal-close" @click="closePushModal">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <div v-if="pushModalError" class="form-error">{{ pushModalError }}</div>
          
          <form @submit.prevent="handlePushImage">
            <div class="form-group">
              <label class="form-label">源镜像</label>
              <div class="form-readonly">
                {{ pushForm.image }}
              </div>
            </div>
            
            <div class="form-group">
              <label class="form-label">目标镜像 <span class="required">*</span></label>
              <input 
                type="text" 
                v-model="pushForm.target_image" 
                class="form-input"
                placeholder="例如: registry.example.com/myimage:latest"
                :disabled="pushModalLoading"
                required
              />
              <p class="form-hint">输入完整的目标镜像地址，包含仓库地址和标签</p>
            </div>
            
            <div class="form-group">
              <label class="form-label">使用仓库配置</label>
              <select 
                v-model="pushForm.registry_id" 
                class="form-input"
                :disabled="pushModalLoading || registries.length === 0"
              >
                <option :value="null">不使用私有仓库</option>
                <option v-for="reg in registries" :key="reg.id" :value="reg.id">
                  {{ reg.name }} ({{ reg.registry_type }})
                </option>
              </select>
              <p class="form-hint" v-if="registries.length === 0">
                暂无已配置的私有仓库，<router-link to="/registries" class="link">点击配置</router-link>
              </p>
            </div>
            
            <div class="modal-footer">
              <button type="button" class="btn btn-outline" @click="closePushModal" :disabled="pushModalLoading">
                取消
              </button>
              <button type="submit" class="btn btn-primary" :disabled="pushModalLoading || !pushForm.target_image">
                {{ pushModalLoading ? '推送中...' : '推送镜像' }}
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
          <p>确定要删除镜像 "<strong>{{ deletingImage?.repo_tags?.[0] || deletingImage?.short_id }}</strong>" 吗？</p>
          
          <div class="checkbox-group">
            <label class="checkbox-label">
              <input 
                type="checkbox" 
                v-model="deleteForm.force"
                :disabled="deleteConfirmLoading"
              />
              <span>强制删除（即使有容器在使用）</span>
            </label>
            <label class="checkbox-label">
              <input 
                type="checkbox" 
                v-model="deleteForm.noprune"
                :disabled="deleteConfirmLoading"
              />
              <span>保留未使用的父镜像</span>
            </label>
          </div>
          
          <div class="modal-footer">
            <button type="button" class="btn btn-outline" @click="closeDeleteConfirm" :disabled="deleteConfirmLoading">
              取消
            </button>
            <button type="button" class="btn btn-danger" @click="executeDeleteImage" :disabled="deleteConfirmLoading">
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
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '../components/AppLayout.vue'
import { useAuth } from '../composables/useAuth'
import { imageApi, registryApi } from '../api/containerApi'


const router = useRouter()
const { isAdmin, currentUser, logout } = useAuth()


if (!isAdmin.value) {
  router.push('/')
}


const images = ref([])
const registries = ref([])
const loading = ref(true)
const error = ref(null)
const searchQuery = ref('')
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const totalPages = ref(0)

const selectedImage = ref(null)
const imageDetail = ref(null)
const imageHistory = ref([])
const detailLoading = ref(false)
const historyLoading = ref(false)

const showPullModal = ref(false)
const pullModalLoading = ref(false)
const pullModalError = ref('')
const pullForm = ref({
  image: '',
  tag: '',
  platform: '',
  registry_id: null
})

const showDetailModal = ref(false)
const showHistoryModal = ref(false)

const showTagModal = ref(false)
const tagModalLoading = ref(false)
const tagModalError = ref('')
const tagForm = ref({
  repository: '',
  new_tag: ''
})

const showPushModal = ref(false)
const pushModalLoading = ref(false)
const pushModalError = ref('')
const pushForm = ref({
  image: '',
  target_image: '',
  registry_id: null
})

const showDeleteConfirm = ref(false)
const deletingImage = ref(null)
const deleteConfirmLoading = ref(false)
const deleteForm = ref({
  force: false,
  noprune: false
})

const toastMessage = ref('')
const toastType = ref('success')
let toastTimeout = null


const fetchImages = async () => {
  try {
    loading.value = true
    error.value = null
    
    const params = {
      all: false,
      page: currentPage.value,
      page_size: pageSize.value
    }
    
    if (searchQuery.value) {
      params.search = searchQuery.value
    }
    
    const result = await imageApi.getImages(params)
    
    if (result.success) {
      images.value = result.data || []
      total.value = result.total || 0
      totalPages.value = result.total_pages || 1
    } else {
      error.value = result.message || '获取镜像列表失败'
    }
  } catch (err) {
    error.value = err.message || '获取镜像列表失败'
  } finally {
    loading.value = false
  }
}


const fetchRegistries = async () => {
  try {
    const result = await registryApi.getRegistries()
    if (result.success) {
      registries.value = result.data || []
    }
  } catch (err) {
    console.error('获取仓库列表失败:', err)
  }
}


const openPullModal = () => {
  pullForm.value = {
    image: '',
    tag: '',
    platform: '',
    registry_id: null
  }
  pullModalError.value = ''
  showPullModal.value = true
}


const closePullModal = () => {
  showPullModal.value = false
  pullForm.value = {
    image: '',
    tag: '',
    platform: '',
    registry_id: null
  }
  pullModalError.value = ''
}


const handlePullImage = async () => {
  if (!pullForm.value.image) {
    pullModalError.value = '请输入镜像名称'
    return
  }
  
  try {
    pullModalLoading.value = true
    pullModalError.value = ''
    
    const data = {
      image: pullForm.value.image
    }
    
    if (pullForm.value.tag) {
      data.tag = pullForm.value.tag
    }
    if (pullForm.value.platform) {
      data.platform = pullForm.value.platform
    }
    if (pullForm.value.registry_id) {
      data.registry_id = pullForm.value.registry_id
    }
    
    const result = await imageApi.pullImage(data)
    
    if (result.success) {
      showToast('镜像拉取成功', 'success')
      closePullModal()
      fetchImages()
    } else {
      pullModalError.value = result.message || '拉取失败'
    }
  } catch (err) {
    pullModalError.value = err.message || '拉取失败'
  } finally {
    pullModalLoading.value = false
  }
}


const viewImageDetail = async (image) => {
  selectedImage.value = image
  detailLoading.value = true
  showDetailModal.value = true
  
  try {
    const result = await imageApi.getImageInfo(image.id || image.repo_tags?.[0])
    
    if (result.success) {
      imageDetail.value = result.data
    }
  } catch (err) {
    console.error('获取镜像详情失败:', err)
  } finally {
    detailLoading.value = false
  }
}


const closeDetailModal = () => {
  showDetailModal.value = false
  imageDetail.value = null
  selectedImage.value = null
}


const viewImageHistory = async (image) => {
  selectedImage.value = image
  historyLoading.value = true
  showHistoryModal.value = true
  
  try {
    const result = await imageApi.getImageHistory(image.id || image.repo_tags?.[0])
    
    if (result.success) {
      imageHistory.value = result.data || []
    }
  } catch (err) {
    console.error('获取镜像历史失败:', err)
  } finally {
    historyLoading.value = false
  }
}


const closeHistoryModal = () => {
  showHistoryModal.value = false
  imageHistory.value = []
  selectedImage.value = null
}


const openTagModal = (image) => {
  selectedImage.value = image
  tagForm.value = {
    repository: image.repo_tags?.[0]?.split(':')[0] || '',
    new_tag: ''
  }
  tagModalError.value = ''
  showTagModal.value = true
}


const closeTagModal = () => {
  showTagModal.value = false
  selectedImage.value = null
  tagForm.value = {
    repository: '',
    new_tag: ''
  }
  tagModalError.value = ''
}


const handleAddTag = async () => {
  if (!tagForm.value.repository || !tagForm.value.new_tag) {
    tagModalError.value = '请填写仓库/镜像名和标签'
    return
  }
  
  try {
    tagModalLoading.value = true
    tagModalError.value = ''
    
    const data = {
      new_tag: tagForm.value.new_tag,
      repository: tagForm.value.repository
    }
    
    const result = await imageApi.addTag(
      selectedImage.value.id || selectedImage.value.repo_tags?.[0],
      data
    )
    
    if (result.success) {
      showToast('标签添加成功', 'success')
      closeTagModal()
      fetchImages()
    } else {
      tagModalError.value = result.message || '添加标签失败'
    }
  } catch (err) {
    tagModalError.value = err.message || '添加标签失败'
  } finally {
    tagModalLoading.value = false
  }
}


const removeTag = async (tag) => {
  if (!confirm(`确定要删除标签 "${tag}" 吗？`)) {
    return
  }
  
  try {
    tagModalLoading.value = true
    
    const result = await imageApi.removeTag(
      selectedImage.value.id || selectedImage.value.repo_tags?.[0],
      tag
    )
    
    if (result.success) {
      showToast('标签删除成功', 'success')
      fetchImages()
    } else {
      showToast(result.message || '删除标签失败', 'error')
    }
  } catch (err) {
    showToast(err.message || '删除标签失败', 'error')
  } finally {
    tagModalLoading.value = false
  }
}


const openPushModal = (image) => {
  selectedImage.value = image
  pushForm.value = {
    image: image.repo_tags?.[0] || image.short_id,
    target_image: image.repo_tags?.[0] || '',
    registry_id: null
  }
  pushModalError.value = ''
  showPushModal.value = true
}


const closePushModal = () => {
  showPushModal.value = false
  selectedImage.value = null
  pushForm.value = {
    image: '',
    target_image: '',
    registry_id: null
  }
  pushModalError.value = ''
}


const handlePushImage = async () => {
  if (!pushForm.value.target_image) {
    pushModalError.value = '请输入目标镜像地址'
    return
  }
  
  try {
    pushModalLoading.value = true
    pushModalError.value = ''
    
    const data = {
      image: pushForm.value.image,
      target_image: pushForm.value.target_image
    }
    
    if (pushForm.value.registry_id) {
      data.registry_id = pushForm.value.registry_id
    }
    
    const result = await imageApi.pushImage(data)
    
    if (result.success) {
      showToast('镜像推送成功', 'success')
      closePushModal()
    } else {
      pushModalError.value = result.message || '推送失败'
    }
  } catch (err) {
    pushModalError.value = err.message || '推送失败'
  } finally {
    pushModalLoading.value = false
  }
}


const confirmDeleteImage = (image) => {
  deletingImage.value = image
  deleteForm.value = {
    force: false,
    noprune: false
  }
  showDeleteConfirm.value = true
}


const closeDeleteConfirm = () => {
  showDeleteConfirm.value = false
  deletingImage.value = null
}


const executeDeleteImage = async () => {
  if (!deletingImage.value) return
  
  try {
    deleteConfirmLoading.value = true
    
    const params = {}
    if (deleteForm.value.force) {
      params.force = true
    }
    if (deleteForm.value.noprune) {
      params.noprune = true
    }
    
    const result = await imageApi.deleteImage(
      deletingImage.value.id || deletingImage.value.repo_tags?.[0],
      params
    )
    
    if (result.success) {
      showToast('镜像删除成功', 'success')
      closeDeleteConfirm()
      fetchImages()
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
  const date = new Date(timestamp * 1000)
  return date.toLocaleString('zh-CN')
}


const formatBytes = (bytes) => {
  if (bytes === 0 || !bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
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
  fetchImages()
  fetchRegistries()
})
</script>

<style scoped>
.image-management {
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

.link {
  color: var(--primary-color);
  text-decoration: underline;
  cursor: pointer;
}

.link:hover {
  text-decoration: none;
}

.image-list-container {
  background-color: var(--bg-primary);
  border-radius: 0.75rem;
  padding: 1.5rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.image-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(450px, 1fr));
  gap: 1rem;
}

.image-card {
  background-color: var(--bg-secondary);
  border-radius: 0.75rem;
  border: 1px solid var(--border-color);
  overflow: hidden;
  transition: box-shadow 0.2s, border-color 0.2s;
}

.image-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  border-color: var(--primary-color);
}

.image-card-header {
  display: flex;
  padding: 1.25rem;
  gap: 1rem;
}

.image-icon {
  width: 48px;
  height: 48px;
  border-radius: 0.5rem;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.image-info {
  flex: 1;
  min-width: 0;
}

.image-name {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
  flex-wrap: wrap;
}

.primary-name {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
  word-break: break-all;
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

.image-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.meta-label {
  color: var(--text-secondary);
}

.meta-value {
  color: var(--text-primary);
  font-family: 'Courier New', monospace;
}

.image-card-footer {
  padding: 0.75rem 1.25rem;
  background-color: var(--bg-primary);
  border-top: 1px solid var(--border-color);
}

.action-buttons {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
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

.form-readonly {
  padding: 0.75rem 1rem;
  background-color: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  font-family: 'Courier New', monospace;
  font-size: 0.875rem;
  color: var(--text-primary);
  word-break: break-all;
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
  margin-bottom: 1.5rem;
}

.form-section h4 {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 1rem 0;
}

.existing-tags {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.tag-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5rem 0.75rem;
  background-color: var(--bg-secondary);
  border-radius: 0.375rem;
}

.checkbox-group {
  margin: 1rem 0;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  cursor: pointer;
  margin-bottom: 0.5rem;
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

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.layer-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.layer-item {
  padding: 0.75rem;
  background-color: var(--bg-secondary);
  border-radius: 0.375rem;
}

.layer-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.5rem;
}

.layer-index {
  font-size: 0.75rem;
  color: var(--text-secondary);
  font-weight: 600;
}

.layer-id {
  font-family: 'Courier New', monospace;
  font-size: 0.75rem;
  color: var(--text-primary);
}

.layer-size {
  margin-left: auto;
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.layer-command {
  background-color: var(--bg-primary);
  padding: 0.5rem;
  border-radius: 0.25rem;
  overflow-x: auto;
}

.layer-command code {
  font-size: 0.75rem;
  color: var(--text-secondary);
  white-space: nowrap;
}

.config-json {
  background-color: var(--bg-secondary);
  padding: 1rem;
  border-radius: 0.375rem;
  overflow-x: auto;
  max-height: 300px;
  overflow-y: auto;
}

.config-json pre {
  margin: 0;
  font-size: 0.75rem;
  color: var(--text-secondary);
  white-space: pre-wrap;
  word-break: break-all;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.history-item {
  padding: 1rem;
  background-color: var(--bg-secondary);
  border-radius: 0.375rem;
}

.history-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.5rem;
  flex-wrap: wrap;
}

.history-index {
  font-size: 0.75rem;
  color: var(--text-secondary);
  font-weight: 600;
}

.history-id {
  font-family: 'Courier New', monospace;
  font-size: 0.75rem;
  color: var(--text-primary);
}

.history-size {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.history-date {
  margin-left: auto;
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.history-command {
  background-color: var(--bg-primary);
  padding: 0.5rem;
  border-radius: 0.25rem;
  overflow-x: auto;
}

.history-command code {
  font-size: 0.75rem;
  color: var(--text-secondary);
  white-space: nowrap;
}

.history-comment {
  margin-top: 0.5rem;
  padding-left: 0.5rem;
  border-left: 2px solid var(--primary-color);
}

.history-comment p {
  margin: 0;
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.delete-info {
  color: var(--text-secondary);
  font-size: 0.875rem;
  margin-top: 0.5rem;
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
  
  .image-list {
    grid-template-columns: 1fr;
  }
  
  .modal {
    max-width: 100%;
    max-height: 95vh;
  }
  
  .modal-medium {
    width: 100%;
  }
  
  .modal-large {
    width: 100%;
  }
  
  .modal-small {
    width: 100%;
  }
  
  .action-bar {
    flex-direction: column;
    align-items: stretch;
  }
  
  .search-box {
    min-width: 100%;
  }
}
</style>
