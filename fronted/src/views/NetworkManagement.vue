<template>
  <AppLayout
    :currentUser="currentUser"
    :page-title="'网络管理'"
    @refresh="fetchNetworks"
    @logout="logout"
  >
    <div class="action-bar">
      <button class="btn btn-primary" @click="openCreateModal">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="12" y1="8" x2="12" y2="16"></line>
          <line x1="8" y1="12" x2="16" y2="12"></line>
        </svg>
        创建网络
      </button>
      <button class="btn btn-outline" @click="fetchNetworks">
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
          placeholder="搜索网络名称、ID..."
          @keyup.enter="fetchNetworks"
        />
      </div>
      <div class="filter-select">
        <select v-model="filterDriver" @change="fetchNetworks" class="form-input filter-select-input">
          <option value="">所有驱动</option>
          <option value="bridge">bridge</option>
          <option value="host">host</option>
          <option value="overlay">overlay</option>
          <option value="macvlan">macvlan</option>
          <option value="none">none</option>
        </select>
      </div>
    </div>

    <div v-if="loading" class="loading-state">
      <div class="loading-spinner"></div>
      <p>加载中...</p>
    </div>

    <div v-else-if="error" class="error-state">
      <div class="error-icon">⚠️</div>
      <p>{{ error }}</p>
      <button class="btn btn-primary" @click="fetchNetworks">重试</button>
    </div>

    <div v-else class="network-list-container">
      <div v-if="networks.length === 0" class="empty-state">
        <div class="empty-icon">🌐</div>
        <p>暂无网络</p>
        <p class="text-muted">点击上方"创建网络"按钮来创建新网络</p>
      </div>

      <div v-else class="network-list">
        <div 
          v-for="network in networks" 
          :key="network.id" 
          class="network-card"
          :class="{ 'card-default': network.is_default }"
        >
          <div class="network-card-header">
            <div class="network-icon">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="5" r="3"></circle>
                <circle cx="6" cy="12" r="3"></circle>
                <circle cx="18" cy="12" r="3"></circle>
                <circle cx="12" cy="19" r="3"></circle>
                <line x1="9.5" y1="7" x2="8.5" y2="9.5"></line>
                <line x1="14.5" y1="7" x2="15.5" y2="9.5"></line>
                <line x1="8.5" y1="14.5" x2="9.5" y2="17"></line>
                <line x1="15.5" y1="14.5" x2="14.5" y2="17"></line>
              </svg>
            </div>
            <div class="network-info">
              <div class="network-name">
                <span class="primary-name">{{ network.name }}</span>
                <span class="badge badge-default" v-if="network.is_default">
                  默认
                </span>
                <span 
                  class="badge" 
                  :class="'badge-' + getDriverBadgeClass(network.driver)"
                >
                  {{ network.driver }}
                </span>
                <span class="badge badge-secondary" v-if="network.internal">
                  内部
                </span>
                <span class="badge badge-secondary" v-if="network.enable_ipv6">
                  IPv6
                </span>
              </div>
              <div class="network-meta">
                <span class="meta-item">
                  <span class="meta-label">ID:</span>
                  <span class="meta-value">{{ network.id ? network.id.substring(0, 12) : '-' }}</span>
                </span>
                <span class="meta-item" v-if="network.subnet">
                  <span class="meta-label">子网:</span>
                  <span class="meta-value">{{ network.subnet }}</span>
                </span>
                <span class="meta-item" v-if="network.gateway">
                  <span class="meta-label">网关:</span>
                  <span class="meta-value">{{ network.gateway }}</span>
                </span>
                <span class="meta-item">
                  <span class="meta-label">容器:</span>
                  <span class="meta-value">{{ network.container_count || 0 }}</span>
                </span>
                <span class="meta-item" v-if="network.created">
                  <span class="meta-label">创建时间:</span>
                  <span class="meta-value">{{ formatDate(network.created) }}</span>
                </span>
              </div>
            </div>
          </div>
          <div class="network-card-footer">
            <div class="action-buttons">
              <button 
                class="btn btn-ghost btn-sm action-btn"
                @click="viewNetworkDetail(network)"
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
                @click="openConnectModal(network)"
                title="连接容器"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>
                  <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>
                </svg>
                连接
              </button>
              <button 
                v-if="!network.is_default"
                class="btn btn-ghost btn-sm action-btn action-btn-danger"
                @click="confirmDeleteNetwork(network)"
                title="删除网络"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="3 6 5 6 21 6"></polyline>
                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                </svg>
                删除
              </button>
            </div>
          </div>
        </div>

        <div v-if="totalPages > 1" class="pagination">
          <button 
            class="btn btn-outline btn-sm" 
            @click="currentPage = currentPage - 1; fetchNetworks()"
            :disabled="currentPage <= 1"
          >
            上一页
          </button>
          <span class="page-info">
            第 {{ currentPage }} 页 / 共 {{ totalPages }} 页 ({{ total }} 个网络)
          </span>
          <button 
            class="btn btn-outline btn-sm" 
            @click="currentPage = currentPage + 1; fetchNetworks()"
            :disabled="currentPage >= totalPages"
          >
            下一页
          </button>
        </div>
      </div>
    </div>

    <div v-if="showCreateModal" class="modal-overlay" @click.self="closeCreateModal">
      <div class="modal modal-medium">
        <div class="modal-header">
          <h3 class="modal-title">创建网络</h3>
          <button class="modal-close" @click="closeCreateModal">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <div v-if="createModalError" class="form-error">{{ createModalError }}</div>
          
          <form @submit.prevent="handleCreateNetwork">
            <div class="form-group">
              <label class="form-label">网络名称 <span class="required">*</span></label>
              <input 
                type="text" 
                v-model="createForm.name" 
                class="form-input"
                placeholder="例如: my-network"
                :disabled="createModalLoading"
                required
              />
            </div>
            
            <div class="form-group">
              <label class="form-label">网络驱动 <span class="required">*</span></label>
              <select 
                v-model="createForm.driver" 
                class="form-input"
                :disabled="createModalLoading"
              >
                <option value="bridge">bridge (默认桥接网络)</option>
                <option value="host">host (主机网络)</option>
                <option value="overlay">overlay (跨主机网络)</option>
                <option value="macvlan">macvlan (虚拟局域网)</option>
                <option value="none">none (无网络)</option>
              </select>
              <p class="form-hint">选择网络驱动类型，不同驱动有不同的网络特性</p>
            </div>
            
            <div class="form-section" v-if="createForm.driver === 'bridge' || createForm.driver === 'macvlan'">
              <h4>IPAM 配置（可选）</h4>
              <div class="form-group">
                <label class="form-label">子网</label>
                <input 
                  type="text" 
                  v-model="createForm.subnet" 
                  class="form-input"
                  placeholder="例如: 172.20.0.0/16"
                  :disabled="createModalLoading"
                />
                <p class="form-hint">指定网络子网，如不指定则由 Docker 自动分配</p>
              </div>
              <div class="form-group">
                <label class="form-label">IP 范围</label>
                <input 
                  type="text" 
                  v-model="createForm.iprange" 
                  class="form-input"
                  placeholder="例如: 172.20.10.0/24"
                  :disabled="createModalLoading"
                />
                <p class="form-hint">指定容器可分配的 IP 范围</p>
              </div>
              <div class="form-group">
                <label class="form-label">网关</label>
                <input 
                  type="text" 
                  v-model="createForm.gateway" 
                  class="form-input"
                  placeholder="例如: 172.20.0.1"
                  :disabled="createModalLoading"
                />
              </div>
            </div>
            
            <div class="form-section">
              <h4>高级选项</h4>
              <div class="checkbox-group">
                <label class="checkbox-label">
                  <input 
                    type="checkbox" 
                    v-model="createForm.internal"
                    :disabled="createModalLoading"
                  />
                  <span>内部网络（禁止外部访问）</span>
                </label>
                <label class="checkbox-label">
                  <input 
                    type="checkbox" 
                    v-model="createForm.enable_ipv6"
                    :disabled="createModalLoading"
                  />
                  <span>启用 IPv6</span>
                </label>
                <label class="checkbox-label">
                  <input 
                    type="checkbox" 
                    v-model="createForm.check_duplicate"
                    :disabled="createModalLoading"
                  />
                  <span>检查网络名称重复</span>
                </label>
              </div>
            </div>
            
            <div class="form-group">
              <label class="form-label">标签（可选）</label>
              <input 
                type="text" 
                v-model="createForm.labelsInput" 
                class="form-input"
                placeholder="例如: key1=value1,key2=value2"
                :disabled="createModalLoading"
              />
              <p class="form-hint">使用逗号分隔多个键值对</p>
            </div>
            
            <div class="modal-footer">
              <button type="button" class="btn btn-outline" @click="closeCreateModal" :disabled="createModalLoading">
                取消
              </button>
              <button type="submit" class="btn btn-primary" :disabled="createModalLoading || !createForm.name">
                {{ createModalLoading ? '创建中...' : '创建网络' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <div v-if="showDetailModal" class="modal-overlay modal-large" @click.self="closeDetailModal">
      <div class="modal modal-large">
        <div class="modal-header">
          <h3 class="modal-title">网络详情</h3>
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
          <div v-else-if="networkDetail">
            <div class="detail-section">
              <h4>基本信息</h4>
              <div class="detail-grid">
                <div class="detail-item">
                  <span class="detail-label">ID</span>
                  <span class="detail-value">{{ networkDetail.id }}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">名称</span>
                  <span class="detail-value">{{ networkDetail.name }}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">驱动类型</span>
                  <span class="detail-value">{{ networkDetail.driver }}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">作用域</span>
                  <span class="detail-value">{{ networkDetail.scope || 'N/A' }}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">子网</span>
                  <span class="detail-value">{{ networkDetail.subnet || 'N/A' }}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">网关</span>
                  <span class="detail-value">{{ networkDetail.gateway || 'N/A' }}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">连接容器数</span>
                  <span class="detail-value">{{ networkDetail.container_count || 0 }}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">创建时间</span>
                  <span class="detail-value">{{ formatDate(networkDetail.created) || 'N/A' }}</span>
                </div>
              </div>
            </div>

            <div class="detail-section">
              <h4>网络配置</h4>
              <div class="detail-grid">
                <div class="detail-item">
                  <span class="detail-label">内部网络</span>
                  <span class="detail-value">{{ networkDetail.internal ? '是' : '否' }}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">启用 IPv6</span>
                  <span class="detail-value">{{ networkDetail.enable_ipv6 ? '是' : '否' }}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">可附加</span>
                  <span class="detail-value">{{ networkDetail.attachable ? '是' : '否' }}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">Ingress</span>
                  <span class="detail-value">{{ networkDetail.ingress ? '是' : '否' }}</span>
                </div>
              </div>
            </div>

            <div class="detail-section" v-if="networkDetail.labels && Object.keys(networkDetail.labels).length > 0">
              <h4>标签</h4>
              <div class="tag-list">
                <span v-for="(value, key) in networkDetail.labels" :key="key" class="badge badge-info">
                  {{ key }}={{ value }}
                </span>
              </div>
            </div>

            <div class="detail-section" v-if="networkDetail.ipam">
              <h4>IPAM 配置</h4>
              <div class="config-json">
                <pre>{{ JSON.stringify(networkDetail.ipam, null, 2) }}</pre>
              </div>
            </div>

            <div class="detail-section" v-if="networkDetail.containers && networkDetail.containers.length > 0">
              <h4>连接的容器 ({{ networkDetail.containers.length }})</h4>
              <div class="container-list">
                <div v-for="container in networkDetail.containers" :key="container.container_id" class="container-item">
                  <div class="container-header">
                    <span class="container-name">{{ container.container_name }}</span>
                    <button 
                      class="btn btn-ghost btn-sm action-btn action-btn-danger"
                      @click="disconnectContainerFromNetwork(container)"
                      title="断开连接"
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>
                        <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>
                      </svg>
                      断开
                    </button>
                  </div>
                  <div class="container-meta">
                    <span class="meta-item">
                      <span class="meta-label">ID:</span>
                      <span class="meta-value">{{ container.container_id?.substring(0, 12) }}</span>
                    </span>
                    <span class="meta-item" v-if="container.ip_address">
                      <span class="meta-label">IPv4:</span>
                      <span class="meta-value">{{ container.ip_address }}</span>
                    </span>
                    <span class="meta-item" v-if="container.ipv6_address">
                      <span class="meta-label">IPv6:</span>
                      <span class="meta-value">{{ container.ipv6_address }}</span>
                    </span>
                    <span class="meta-item" v-if="container.mac_address">
                      <span class="meta-label">MAC:</span>
                      <span class="meta-value">{{ container.mac_address }}</span>
                    </span>
                  </div>
                  <div class="container-meta" v-if="container.network_aliases && container.network_aliases.length > 0">
                    <span class="meta-label">网络别名:</span>
                    <span class="badge badge-secondary" v-for="alias in container.network_aliases" :key="alias">
                      {{ alias }}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            <div v-else class="empty-state" style="padding: 1rem;">
              <p>暂无连接的容器</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="showConnectModal" class="modal-overlay" @click.self="closeConnectModal">
      <div class="modal modal-medium">
        <div class="modal-header">
          <h3 class="modal-title">连接容器到网络</h3>
          <button class="modal-close" @click="closeConnectModal">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <div v-if="connectModalError" class="form-error">{{ connectModalError }}</div>
          
          <form @submit.prevent="handleConnectContainer">
            <div class="form-group">
              <label class="form-label">目标网络</label>
              <div class="form-readonly">
                {{ selectedNetwork?.name }} ({{ selectedNetwork?.driver }})
              </div>
            </div>
            
            <div class="form-group">
              <label class="form-label">选择容器 <span class="required">*</span></label>
              <select 
                v-model="connectForm.container_id" 
                class="form-input"
                :disabled="connectModalLoading || containers.length === 0"
              >
                <option value="">请选择容器</option>
                <option v-for="container in containers" :key="container.id" :value="container.id">
                  {{ container.names?.[0] || container.id.substring(0, 12) }} ({{ container.state }})
                </option>
              </select>
              <p v-if="containers.length === 0" class="form-hint">
                暂无可用容器，请先启动容器
              </p>
            </div>
            
            <div class="form-section">
              <h4>高级选项（可选）</h4>
              <div class="form-group">
                <label class="form-label">指定 IP 地址</label>
                <input 
                  type="text" 
                  v-model="connectForm.ip_address" 
                  class="form-input"
                  placeholder="例如: 172.20.0.10"
                  :disabled="connectModalLoading"
                />
              </div>
              <div class="form-group">
                <label class="form-label">指定 IPv6 地址</label>
                <input 
                  type="text" 
                  v-model="connectForm.ipv6_address" 
                  class="form-input"
                  placeholder="例如: 2001:db8::10"
                  :disabled="connectModalLoading"
                />
              </div>
              <div class="form-group">
                <label class="form-label">网络别名</label>
                <input 
                  type="text" 
                  v-model="connectForm.aliasesInput" 
                  class="form-input"
                  placeholder="例如: alias1,alias2"
                  :disabled="connectModalLoading"
                />
                <p class="form-hint">使用逗号分隔多个别名</p>
              </div>
            </div>
            
            <div class="modal-footer">
              <button type="button" class="btn btn-outline" @click="closeConnectModal" :disabled="connectModalLoading">
                取消
              </button>
              <button type="submit" class="btn btn-primary" :disabled="connectModalLoading || !connectForm.container_id">
                {{ connectModalLoading ? '连接中...' : '连接容器' }}
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
          <p>确定要删除网络 "<strong>{{ deletingNetwork?.name }}</strong>" 吗？</p>
          
          <div class="delete-info" v-if="deletingNetwork?.container_count > 0">
            ⚠️ 该网络当前连接了 {{ deletingNetwork.container_count }} 个容器
          </div>
          
          <div class="checkbox-group">
            <label class="checkbox-label">
              <input 
                type="checkbox" 
                v-model="deleteForm.force"
                :disabled="deleteConfirmLoading"
              />
              <span>强制删除（断开所有连接的容器）</span>
            </label>
          </div>
          
          <div class="modal-footer">
            <button type="button" class="btn btn-outline" @click="closeDeleteConfirm" :disabled="deleteConfirmLoading">
              取消
            </button>
            <button type="button" class="btn btn-danger" @click="executeDeleteNetwork" :disabled="deleteConfirmLoading">
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
import { networkApi, containerApi } from '../api/containerApi'

const router = useRouter()
const { isAdmin, currentUser, logout } = useAuth()

if (!isAdmin.value) {
  router.push('/')
}

const networks = ref([])
const containers = ref([])
const loading = ref(true)
const error = ref(null)
const searchQuery = ref('')
const filterDriver = ref('')
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const totalPages = ref(0)

const selectedNetwork = ref(null)
const networkDetail = ref(null)
const detailLoading = ref(false)

const showCreateModal = ref(false)
const createModalLoading = ref(false)
const createModalError = ref('')
const createForm = ref({
  name: '',
  driver: 'bridge',
  subnet: '',
  iprange: '',
  gateway: '',
  internal: false,
  enable_ipv6: false,
  check_duplicate: true,
  labelsInput: ''
})

const showDetailModal = ref(false)

const showConnectModal = ref(false)
const connectModalLoading = ref(false)
const connectModalError = ref('')
const connectForm = ref({
  container_id: '',
  ip_address: '',
  ipv6_address: '',
  aliasesInput: ''
})

const showDeleteConfirm = ref(false)
const deletingNetwork = ref(null)
const deleteConfirmLoading = ref(false)
const deleteForm = ref({
  force: false
})

const toastMessage = ref('')
const toastType = ref('success')
let toastTimeout = null

const getDriverBadgeClass = (driver) => {
  const classes = {
    'bridge': 'primary',
    'host': 'info',
    'overlay': 'warning',
    'macvlan': 'secondary',
    'none': 'danger'
  }
  return classes[driver] || 'secondary'
}

const fetchNetworks = async () => {
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
    
    if (filterDriver.value) {
      params.driver = filterDriver.value
    }
    
    const result = await networkApi.getNetworks(params)
    
    if (result.success) {
      networks.value = result.data || []
      total.value = result.total || 0
      totalPages.value = result.total_pages || 1
    } else {
      error.value = result.message || '获取网络列表失败'
    }
  } catch (err) {
    error.value = err.message || '获取网络列表失败'
  } finally {
    loading.value = false
  }
}

const fetchContainers = async () => {
  try {
    const result = await containerApi.getContainers({ all: true })
    if (result.success) {
      containers.value = result.data || []
    }
  } catch (err) {
    console.error('获取容器列表失败:', err)
  }
}

const openCreateModal = () => {
  createForm.value = {
    name: '',
    driver: 'bridge',
    subnet: '',
    iprange: '',
    gateway: '',
    internal: false,
    enable_ipv6: false,
    check_duplicate: true,
    labelsInput: ''
  }
  createModalError.value = ''
  showCreateModal.value = true
}

const closeCreateModal = () => {
  showCreateModal.value = false
  createForm.value = {
    name: '',
    driver: 'bridge',
    subnet: '',
    iprange: '',
    gateway: '',
    internal: false,
    enable_ipv6: false,
    check_duplicate: true,
    labelsInput: ''
  }
  createModalError.value = ''
}

const handleCreateNetwork = async () => {
  if (!createForm.value.name) {
    createModalError.value = '请输入网络名称'
    return
  }
  
  try {
    createModalLoading.value = true
    createModalError.value = ''
    
    const data = {
      name: createForm.value.name,
      driver: createForm.value.driver,
      check_duplicate: createForm.value.check_duplicate,
      internal: createForm.value.internal,
      enable_ipv6: createForm.value.enable_ipv6
    }
    
    if (createForm.value.subnet || createForm.value.iprange || createForm.value.gateway) {
      data.ipam = {
        driver: 'default',
        config: []
      }
      
      const ipamConfig = {}
      if (createForm.value.subnet) ipamConfig.subnet = createForm.value.subnet
      if (createForm.value.iprange) ipamConfig.iprange = createForm.value.iprange
      if (createForm.value.gateway) ipamConfig.gateway = createForm.value.gateway
      
      if (Object.keys(ipamConfig).length > 0) {
        data.ipam.config.push(ipamConfig)
      }
    }
    
    if (createForm.value.labelsInput) {
      data.labels = {}
      const labelPairs = createForm.value.labelsInput.split(',')
      for (const pair of labelPairs) {
        const [key, value] = pair.split('=')
        if (key && value) {
          data.labels[key.trim()] = value.trim()
        }
      }
    }
    
    const result = await networkApi.createNetwork(data)
    
    if (result.success) {
      showToast('网络创建成功', 'success')
      closeCreateModal()
      fetchNetworks()
    } else {
      createModalError.value = result.message || '创建失败'
    }
  } catch (err) {
    createModalError.value = err.message || '创建失败'
  } finally {
    createModalLoading.value = false
  }
}

const viewNetworkDetail = async (network) => {
  selectedNetwork.value = network
  detailLoading.value = true
  showDetailModal.value = true
  
  try {
    const result = await networkApi.getNetworkInfo(network.id)
    
    if (result.success) {
      networkDetail.value = result.data
    }
  } catch (err) {
    console.error('获取网络详情失败:', err)
  } finally {
    detailLoading.value = false
  }
}

const closeDetailModal = () => {
  showDetailModal.value = false
  networkDetail.value = null
  selectedNetwork.value = null
}

const openConnectModal = (network) => {
  selectedNetwork.value = network
  connectForm.value = {
    container_id: '',
    ip_address: '',
    ipv6_address: '',
    aliasesInput: ''
  }
  connectModalError.value = ''
  fetchContainers()
  showConnectModal.value = true
}

const closeConnectModal = () => {
  showConnectModal.value = false
  selectedNetwork.value = null
  connectForm.value = {
    container_id: '',
    ip_address: '',
    ipv6_address: '',
    aliasesInput: ''
  }
  connectModalError.value = ''
}

const handleConnectContainer = async () => {
  if (!connectForm.value.container_id) {
    connectModalError.value = '请选择容器'
    return
  }
  
  try {
    connectModalLoading.value = true
    connectModalError.value = ''
    
    const data = {
      container_id: connectForm.value.container_id
    }
    
    if (connectForm.value.ip_address) {
      data.ip_address = connectForm.value.ip_address
    }
    if (connectForm.value.ipv6_address) {
      data.ipv6_address = connectForm.value.ipv6_address
    }
    if (connectForm.value.aliasesInput) {
      data.network_aliases = connectForm.value.aliasesInput.split(',').map(a => a.trim()).filter(a => a)
    }
    
    const result = await networkApi.connectContainer(selectedNetwork.value.id, data)
    
    if (result.success) {
      showToast('容器连接成功', 'success')
      closeConnectModal()
      fetchNetworks()
      if (showDetailModal.value) {
        viewNetworkDetail(selectedNetwork.value)
      }
    } else {
      connectModalError.value = result.message || '连接失败'
    }
  } catch (err) {
    connectModalError.value = err.message || '连接失败'
  } finally {
    connectModalLoading.value = false
  }
}

const disconnectContainerFromNetwork = async (container) => {
  if (!confirm(`确定要将容器 "${container.container_name}" 从网络断开吗？`)) {
    return
  }
  
  try {
    const result = await networkApi.disconnectContainer(selectedNetwork.value.id, {
      container_id: container.container_id,
      force: true
    })
    
    if (result.success) {
      showToast('容器已断开连接', 'success')
      fetchNetworks()
      viewNetworkDetail(selectedNetwork.value)
    } else {
      showToast(result.message || '断开连接失败', 'error')
    }
  } catch (err) {
    showToast(err.message || '断开连接失败', 'error')
  }
}

const confirmDeleteNetwork = (network) => {
  deletingNetwork.value = network
  deleteForm.value = {
    force: false
  }
  showDeleteConfirm.value = true
}

const closeDeleteConfirm = () => {
  showDeleteConfirm.value = false
  deletingNetwork.value = null
}

const executeDeleteNetwork = async () => {
  if (!deletingNetwork.value) return
  
  try {
    deleteConfirmLoading.value = true
    
    const params = {}
    if (deleteForm.value.force) {
      params.force = true
    }
    
    const result = await networkApi.deleteNetwork(deletingNetwork.value.id, params)
    
    if (result.success) {
      showToast('网络删除成功', 'success')
      closeDeleteConfirm()
      fetchNetworks()
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
  try {
    let date
    if (typeof timestamp === 'number') {
      date = new Date(timestamp * 1000)
    } else {
      date = new Date(timestamp)
    }
    return date.toLocaleString('zh-CN')
  } catch {
    return timestamp
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
  fetchNetworks()
})
</script>

<style scoped>
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

.filter-select {
  min-width: 150px;
}

.filter-select-input {
  padding: 0.5rem 0.75rem;
  font-size: 0.875rem;
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

.network-list-container {
  background-color: var(--bg-primary);
  border-radius: 0.75rem;
  padding: 1.5rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.network-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(500px, 1fr));
  gap: 1rem;
}

.network-card {
  background-color: var(--bg-secondary);
  border-radius: 0.75rem;
  border: 1px solid var(--border-color);
  overflow: hidden;
  transition: box-shadow 0.2s, border-color 0.2s;
}

.network-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  border-color: var(--primary-color);
}

.network-card.card-default {
  border-left: 3px solid #10b981;
}

.network-card-header {
  display: flex;
  padding: 1.25rem;
  gap: 1rem;
}

.network-icon {
  width: 48px;
  height: 48px;
  border-radius: 0.5rem;
  background: linear-gradient(135deg, #0ea5e9 0%, #06b6d4 100%);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.network-info {
  flex: 1;
  min-width: 0;
}

.network-name {
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

.badge-warning {
  background-color: rgba(245, 158, 11, 0.1);
  color: #d97706;
}

.badge-danger {
  background-color: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}

.badge-default {
  background-color: rgba(16, 185, 129, 0.1);
  color: #10b981;
}

.network-meta {
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

.network-card-footer {
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

.container-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.container-item {
  padding: 1rem;
  background-color: var(--bg-secondary);
  border-radius: 0.375rem;
}

.container-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.5rem;
}

.container-name {
  font-weight: 600;
  color: var(--text-primary);
}

.container-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  margin-top: 0.5rem;
  font-size: 0.75rem;
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
  .network-list {
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
  
  .filter-select {
    width: 100%;
  }
}
</style>
