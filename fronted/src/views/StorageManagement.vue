<template>
  <AppLayout
    :currentUser="currentUser"
    :page-title="'存储管理'"
    @refresh="fetchVolumes"
    @logout="logout"
  >
    <div class="tabs">
          <button 
            class="tab-btn" 
            :class="{ active: activeTab === 'volumes' }"
            @click="activeTab = 'volumes'"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
              <polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
              <line x1="12" y1="22.08" x2="12" y2="12"></line>
            </svg>
            Volume 管理 ({{ totalVolumes }})
          </button>
          <button 
            class="tab-btn" 
            :class="{ active: activeTab === 'bind-mounts' }"
            @click="activeTab = 'bind-mounts'; fetchBindMounts()"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
              <polyline points="14 2 14 8 20 8"></polyline>
              <line x1="16" y1="13" x2="8" y2="13"></line>
              <line x1="16" y1="17" x2="8" y2="17"></line>
              <polyline points="10 9 9 9 8 9"></polyline>
            </svg>
            绑定挂载 ({{ totalBindMounts }})
          </button>
          <button 
            class="tab-btn" 
            :class="{ active: activeTab === 'usage' }"
            @click="activeTab = 'usage'; fetchStorageUsage()"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="12" y1="1" x2="12" y2="23"></line>
              <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path>
            </svg>
            存储使用分析
          </button>
        </div>

        <div v-if="activeTab === 'volumes'" class="tab-content">
          <div class="action-bar">
            <button class="btn btn-primary" @click="openCreateVolumeModal">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="8" x2="12" y2="16"></line>
                <line x1="8" y1="12" x2="16" y2="12"></line>
              </svg>
              创建 Volume
            </button>
            <button class="btn btn-outline" @click="fetchVolumes">
              刷新
            </button>
            <div class="search-box">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="11" cy="11" r="8"></circle>
                <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
              </svg>
              <input 
                type="text" 
                v-model="volumeSearchQuery" 
                placeholder="搜索 Volume 名称、ID..."
                @keyup.enter="fetchVolumes"
              />
            </div>
            <div class="filter-select">
              <select v-model="volumeFilterUnused" @change="fetchVolumes" class="form-input filter-select-input">
                <option value="">所有 Volume</option>
                <option value="unused">未使用</option>
                <option value="used">已使用</option>
              </select>
            </div>
          </div>

          <div v-if="volumesLoading" class="loading-state">
            <div class="loading-spinner"></div>
            <p>加载中...</p>
          </div>

          <div v-else-if="volumesError" class="error-state">
            <div class="error-icon">⚠️</div>
            <p>{{ volumesError }}</p>
            <button class="btn btn-primary" @click="fetchVolumes">重试</button>
          </div>

          <div v-else class="volume-list-container">
            <div v-if="volumes.length === 0" class="empty-state">
              <div class="empty-icon">💾</div>
              <p>暂无 Volume</p>
              <p class="text-muted">点击上方"创建 Volume"按钮来创建新 Volume</p>
            </div>

            <div v-else class="volume-list">
              <div 
                v-for="volume in volumes" 
                :key="volume.id" 
                class="volume-card"
                :class="{ 'card-unused': volume.is_unused }"
              >
                <div class="volume-card-header">
                  <div class="volume-icon">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
                    </svg>
                  </div>
                  <div class="volume-info">
                    <div class="volume-name">
                      <span class="primary-name">{{ volume.name }}</span>
                      <span 
                        class="badge" 
                        :class="volume.is_unused ? 'badge-warning' : 'badge-success'"
                      >
                        {{ volume.is_unused ? '未使用' : '已使用' }}
                      </span>
                      <span class="badge badge-info">
                        {{ volume.driver }}
                      </span>
                    </div>
                    <div class="volume-meta">
                      <span class="meta-item">
                        <span class="meta-label">ID:</span>
                        <span class="meta-value">{{ volume.id ? volume.id.substring(0, 12) : '-' }}</span>
                      </span>
                      <span class="meta-item">
                        <span class="meta-label">容器:</span>
                        <span class="meta-value">{{ volume.container_count || 0 }}</span>
                      </span>
                      <span class="meta-item" v-if="volume.created">
                        <span class="meta-label">创建时间:</span>
                        <span class="meta-value">{{ formatDate(volume.created) }}</span>
                      </span>
                    </div>
                  </div>
                </div>
                <div class="volume-card-footer">
                  <div class="action-buttons">
                    <button 
                      class="btn btn-ghost btn-sm action-btn"
                      @click="viewVolumeDetail(volume)"
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
                      @click="openBackupModal(volume)"
                      title="备份 Volume"
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M19 21H5a2 2 0 0 1-2-2v-9a2 2 0 0 1 2-2h11a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2z"></path>
                        <path d="M17 8V6a5 5 0 0 0-10 0v2"></path>
                        <line x1="12" y1="12" x2="12" y2="18"></line>
                        <line x1="9" y1="15" x2="15" y2="15"></line>
                      </svg>
                      备份
                    </button>
                    <button 
                      class="btn btn-ghost btn-sm action-btn"
                      @click="openRestoreModal(volume)"
                      title="恢复 Volume 备份"
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="1 4 1 10 7 10"></polyline>
                        <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"></path>
                      </svg>
                      恢复
                    </button>
                    <button 
                      class="btn btn-ghost btn-sm action-btn action-btn-danger"
                      @click="confirmDeleteVolume(volume)"
                      title="删除 Volume"
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
            </div>

            <div v-if="volumeTotalPages > 1" class="pagination">
              <button 
                class="btn btn-outline btn-sm" 
                @click="volumeCurrentPage = volumeCurrentPage - 1; fetchVolumes()"
                :disabled="volumeCurrentPage <= 1"
              >
                上一页
              </button>
              <span class="page-info">
                第 {{ volumeCurrentPage }} 页 / 共 {{ volumeTotalPages }} 页 ({{ volumeTotal }} 个 Volume)
              </span>
              <button 
                class="btn btn-outline btn-sm" 
                @click="volumeCurrentPage = volumeCurrentPage + 1; fetchVolumes()"
                :disabled="volumeCurrentPage >= volumeTotalPages"
              >
                下一页
              </button>
            </div>
          </div>
        </div>

        <div v-if="activeTab === 'bind-mounts'" class="tab-content">
          <div class="action-bar">
            <button class="btn btn-outline" @click="fetchBindMounts">
              刷新
            </button>
            <div class="search-box">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="11" cy="11" r="8"></circle>
                <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
              </svg>
              <input 
                type="text" 
                v-model="bindMountSearchQuery" 
                placeholder="搜索容器名称、路径..."
              />
            </div>
          </div>

          <div v-if="bindMountsLoading" class="loading-state">
            <div class="loading-spinner"></div>
            <p>加载中...</p>
          </div>

          <div v-else class="bind-mounts-container">
            <div v-if="filteredBindMounts.length === 0" class="empty-state">
              <div class="empty-icon">📁</div>
              <p>暂无绑定挂载</p>
              <p class="text-muted">绑定挂载是将主机目录直接挂载到容器中的方式</p>
            </div>

            <div v-else class="bind-mounts-table">
              <table>
                <thead>
                  <tr>
                    <th>容器</th>
                    <th>状态</th>
                    <th>源路径（主机）</th>
                    <th>目标路径（容器）</th>
                    <th>权限</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(mount, index) in filteredBindMounts" :key="index">
                    <td>
                      <div class="container-cell">
                        <span class="container-name">{{ mount.container_name }}</span>
                        <span class="container-id">{{ mount.container_id?.substring(0, 12) }}</span>
                      </div>
                    </td>
                    <td>
                      <span 
                        class="badge" 
                        :class="mount.container_status === 'running' ? 'badge-success' : 'badge-secondary'"
                      >
                        {{ mount.container_status || 'unknown' }}
                      </span>
                    </td>
                    <td class="path-cell">
                      <code>{{ mount.source }}</code>
                    </td>
                    <td class="path-cell">
                      <code>{{ mount.destination }}</code>
                    </td>
                    <td>
                      <span 
                        class="badge" 
                        :class="mount.rw ? 'badge-primary' : 'badge-warning'"
                      >
                        {{ mount.rw ? '读写' : '只读' }}
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div v-if="activeTab === 'usage'" class="tab-content">
          <div class="action-bar">
            <button class="btn btn-outline" @click="fetchStorageUsage">
              刷新
            </button>
            <button 
              v-if="storageUsage?.unused_volumes > 0" 
              class="btn btn-warning" 
              @click="showCleanupSuggestions = true"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
              </svg>
              有 {{ storageUsage?.unused_volumes }} 个未使用 Volume
            </button>
          </div>

          <div v-if="storageUsageLoading" class="loading-state">
            <div class="loading-spinner"></div>
            <p>加载中...</p>
          </div>

          <div v-else-if="storageUsage" class="usage-container">
            <div class="usage-summary">
              <div class="usage-card">
                <div class="usage-icon usage-icon-primary">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
                  </svg>
                </div>
                <div class="usage-info">
                  <div class="usage-value">{{ storageUsage.total_volumes || 0 }}</div>
                  <div class="usage-label">总 Volume 数</div>
                </div>
              </div>

              <div class="usage-card">
                <div class="usage-icon usage-icon-warning">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="12" y1="16" x2="12" y2="12"></line>
                    <line x1="12" y1="8" x2="12.01" y2="8"></line>
                  </svg>
                </div>
                <div class="usage-info">
                  <div class="usage-value">{{ storageUsage.unused_volumes || 0 }}</div>
                  <div class="usage-label">未使用 Volume</div>
                </div>
              </div>

              <div class="usage-card">
                <div class="usage-icon usage-icon-success">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="12" y1="1" x2="12" y2="23"></line>
                    <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path>
                  </svg>
                </div>
                <div class="usage-info">
                  <div class="usage-value">{{ formatBytes(storageUsage.total_size || 0) }}</div>
                  <div class="usage-label">总存储空间</div>
                </div>
              </div>

              <div class="usage-card">
                <div class="usage-icon usage-icon-danger">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="3 6 5 6 21 6"></polyline>
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                  </svg>
                </div>
                <div class="usage-info">
                  <div class="usage-value">{{ formatBytes(storageUsage.unused_size || 0) }}</div>
                  <div class="usage-label">可回收空间</div>
                </div>
              </div>
            </div>

            <div class="usage-section">
              <h3 class="section-title">Volume 空间使用详情</h3>
              <div class="volume-usage-list">
                <div 
                  v-for="volume in sortedVolumes" 
                  :key="volume.name" 
                  class="volume-usage-item"
                  :class="{ 'item-unused': volume.is_unused }"
                >
                  <div class="volume-usage-header">
                    <div class="volume-usage-name">
                      <span class="name">{{ volume.name }}</span>
                      <span 
                        class="badge" 
                        :class="volume.is_unused ? 'badge-warning' : 'badge-success'"
                      >
                        {{ volume.is_unused ? '未使用' : '已使用' }}
                      </span>
                    </div>
                    <div class="volume-usage-meta">
                      <span class="meta-item">
                        <span class="meta-label">容器:</span>
                        <span class="meta-value">{{ volume.container_count || 0 }}</span>
                      </span>
                      <span class="meta-item">
                        <span class="meta-label">驱动:</span>
                        <span class="meta-value">{{ volume.driver }}</span>
                      </span>
                    </div>
                  </div>
                  <div class="volume-usage-bar-container">
                    <div class="usage-bar">
                      <div 
                        class="usage-bar-fill"
                        :style="{ width: getUsagePercent(volume.used_size, volume.size) + '%' }"
                        :class="{ 
                          'bar-warning': getUsagePercent(volume.used_size, volume.size) > 70,
                          'bar-danger': getUsagePercent(volume.used_size, volume.size) > 90
                        }"
                      ></div>
                    </div>
                    <div class="usage-bar-text">
                      <span>{{ formatBytes(volume.used_size || 0) }} / {{ formatBytes(volume.size || 0) }}</span>
                      <span>{{ getUsagePercent(volume.used_size, volume.size) }}%</span>
                    </div>
                  </div>
                  <div class="volume-usage-path" v-if="volume.mountpoint">
                    <span class="path-label">挂载点:</span>
                    <code>{{ volume.mountpoint }}</code>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="storageUsage.cleanup_suggestions && storageUsage.cleanup_suggestions.length > 0" class="usage-section">
              <h3 class="section-title">清理建议</h3>
              <div class="suggestions-list">
                <div 
                  v-for="(suggestion, index) in storageUsage.cleanup_suggestions" 
                  :key="index" 
                  class="suggestion-item"
                  :class="'risk-' + (suggestion.risk_level || 'low')"
                >
                  <div class="suggestion-icon">
                    <svg v-if="suggestion.type === 'unused_volume'" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <polyline points="3 6 5 6 21 6"></polyline>
                      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                    </svg>
                    <svg v-else width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <circle cx="12" cy="12" r="10"></circle>
                      <line x1="12" y1="16" x2="12" y2="12"></line>
                      <line x1="12" y1="8" x2="12.01" y2="8"></line>
                    </svg>
                  </div>
                  <div class="suggestion-content">
                    <div class="suggestion-name">{{ suggestion.name }}</div>
                    <div class="suggestion-reason">{{ suggestion.reason }}</div>
                  </div>
                  <div class="suggestion-actions">
                    <span class="size-badge">{{ formatBytes(suggestion.size || 0) }}</span>
                    <span 
                      class="risk-badge"
                      :class="'risk-' + (suggestion.risk_level || 'low')"
                    >
                      {{ getRiskLabel(suggestion.risk_level) }}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

    <div v-if="showCreateVolumeModal" class="modal-overlay" @click.self="closeCreateVolumeModal">
      <div class="modal modal-medium">
        <div class="modal-header">
          <h3 class="modal-title">创建 Volume</h3>
          <button class="modal-close" @click="closeCreateVolumeModal">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <div v-if="createVolumeError" class="form-error">{{ createVolumeError }}</div>
          
          <form @submit.prevent="handleCreateVolume">
            <div class="form-group">
              <label class="form-label">Volume 名称 <span class="required">*</span></label>
              <input 
                type="text" 
                v-model="createVolumeForm.name" 
                class="form-input"
                placeholder="例如: my-data-volume"
                :disabled="createVolumeLoading"
                required
              />
            </div>
            
            <div class="form-group">
              <label class="form-label">驱动类型</label>
              <select 
                v-model="createVolumeForm.driver" 
                class="form-input"
                :disabled="createVolumeLoading"
              >
                <option value="local">local (本地存储)</option>
              </select>
            </div>
            
            <div class="form-section">
              <h4>标签（可选）</h4>
              <div class="form-group">
                <input 
                  type="text" 
                  v-model="createVolumeForm.labelsInput" 
                  class="form-input"
                  placeholder="例如: project=myapp,env=production"
                  :disabled="createVolumeLoading"
                />
                <p class="form-hint">使用逗号分隔多个键值对</p>
              </div>
            </div>
            
            <div class="modal-footer">
              <button type="button" class="btn btn-outline" @click="closeCreateVolumeModal" :disabled="createVolumeLoading">
                取消
              </button>
              <button type="submit" class="btn btn-primary" :disabled="createVolumeLoading || !createVolumeForm.name">
                {{ createVolumeLoading ? '创建中...' : '创建 Volume' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <div v-if="showVolumeDetailModal" class="modal-overlay modal-large" @click.self="closeVolumeDetailModal">
      <div class="modal modal-large">
        <div class="modal-header">
          <h3 class="modal-title">Volume 详情</h3>
          <button class="modal-close" @click="closeVolumeDetailModal">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <div v-if="volumeDetailLoading" class="loading-state">
            <div class="loading-spinner"></div>
            <p>加载中...</p>
          </div>
          <div v-else-if="volumeDetail">
            <div class="detail-section">
              <h4>基本信息</h4>
              <div class="detail-grid">
                <div class="detail-item">
                  <span class="detail-label">ID</span>
                  <span class="detail-value">{{ volumeDetail.id }}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">名称</span>
                  <span class="detail-value">{{ volumeDetail.name }}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">驱动类型</span>
                  <span class="detail-value">{{ volumeDetail.driver }}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">作用域</span>
                  <span class="detail-value">{{ volumeDetail.scope || 'N/A' }}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">挂载点</span>
                  <span class="detail-value">{{ volumeDetail.mountpoint || 'N/A' }}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">容器数</span>
                  <span class="detail-value">{{ volumeDetail.container_count || 0 }}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">创建时间</span>
                  <span class="detail-value">{{ formatDate(volumeDetail.created) || 'N/A' }}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">使用状态</span>
                  <span class="detail-value">
                    <span class="badge" :class="volumeDetail.is_unused ? 'badge-warning' : 'badge-success'">
                      {{ volumeDetail.is_unused ? '未使用' : '已使用' }}
                    </span>
                  </span>
                </div>
              </div>
            </div>

            <div v-if="volumeDetail.mounts && volumeDetail.mounts.length > 0" class="detail-section">
              <h4>挂载信息 ({{ volumeDetail.mounts.length }})</h4>
              <div class="mounts-list">
                <div v-for="(mount, index) in volumeDetail.mounts" :key="index" class="mount-item">
                  <div class="mount-header">
                    <span class="container-name">{{ mount.container_name }}</span>
                    <span 
                      class="badge" 
                      :class="mount.container_status === 'running' ? 'badge-success' : 'badge-secondary'"
                    >
                      {{ mount.container_status || 'unknown' }}
                    </span>
                  </div>
                  <div class="mount-paths">
                    <div class="path-item">
                      <span class="path-label">目标路径:</span>
                      <code>{{ mount.destination }}</code>
                    </div>
                    <div class="path-item">
                      <span class="path-label">权限:</span>
                      <span class="badge" :class="mount.rw ? 'badge-primary' : 'badge-warning'">
                        {{ mount.rw ? '读写' : '只读' }}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="volumeDetail.labels && Object.keys(volumeDetail.labels).length > 0" class="detail-section">
              <h4>标签</h4>
              <div class="tag-list">
                <span v-for="(value, key) in volumeDetail.labels" :key="key" class="badge badge-info">
                  {{ key }}={{ value }}
                </span>
              </div>
            </div>

            <div v-if="volumeDetail.options && Object.keys(volumeDetail.options).length > 0" class="detail-section">
              <h4>驱动选项</h4>
              <div class="config-json">
                <pre>{{ JSON.stringify(volumeDetail.options, null, 2) }}</pre>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="showBackupModal" class="modal-overlay" @click.self="closeBackupModal">
      <div class="modal modal-medium">
        <div class="modal-header">
          <h3 class="modal-title">备份 Volume</h3>
          <button class="modal-close" @click="closeBackupModal">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <div v-if="backupError" class="form-error">{{ backupError }}</div>
          <div v-else-if="backupResult" class="backup-success">
            <div class="success-icon">✅</div>
            <p>备份成功！</p>
            <div class="backup-info">
              <div class="backup-info-item">
                <span class="backup-info-label">Volume:</span>
                <span class="backup-info-value">{{ backupResult.volume_name }}</span>
              </div>
              <div class="backup-info-item">
                <span class="backup-info-label">备份路径:</span>
                <span class="backup-info-value">{{ backupResult.backup_path }}</span>
              </div>
              <div class="backup-info-item">
                <span class="backup-info-label">文件大小:</span>
                <span class="backup-info-value">{{ formatBytes(backupResult.backup_size || 0) }}</span>
              </div>
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-outline" @click="closeBackupModal">
                确定
              </button>
              <button type="button" class="btn btn-primary" @click="openRestoreModalFromBackup">
                恢复此备份
              </button>
            </div>
          </div>
          <div v-else>
            <div class="backup-info-preview">
              <p>即将备份 Volume:</p>
              <strong>{{ backupVolume?.name }}</strong>
            </div>
            
            <form @submit.prevent="handleBackupVolume">
              <div class="form-group">
                <label class="form-label">压缩方式</label>
                <select 
                  v-model="backupForm.compression" 
                  class="form-input"
                  :disabled="backupLoading"
                >
                  <option value="gzip">gzip (推荐，压缩率高)</option>
                  <option value="tar">tar (无压缩，速度快)</option>
                  <option value="none">不压缩</option>
                </select>
              </div>
              
              <div class="form-group">
                <label class="form-label">备份路径（可选）</label>
                <input 
                  type="text" 
                  v-model="backupForm.backup_path" 
                  class="form-input"
                  placeholder="留空则自动生成路径"
                  :disabled="backupLoading"
                />
                <p class="form-hint">留空则自动保存到 /tmp/volume_backups/ 目录</p>
              </div>
              
              <div class="modal-footer">
                <button type="button" class="btn btn-outline" @click="closeBackupModal" :disabled="backupLoading">
                  取消
                </button>
                <button type="submit" class="btn btn-primary" :disabled="backupLoading">
                  {{ backupLoading ? '备份中...' : '开始备份' }}
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>

    <div v-if="showRestoreModal" class="modal-overlay" @click.self="closeRestoreModal">
      <div class="modal modal-medium">
        <div class="modal-header">
          <h3 class="modal-title">恢复 Volume</h3>
          <button class="modal-close" @click="closeRestoreModal">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <div v-if="restoreError" class="form-error">{{ restoreError }}</div>
          <div v-else-if="restoreResult" class="backup-success">
            <div class="success-icon">✅</div>
            <p>恢复成功！</p>
            <div class="backup-info">
              <div class="backup-info-item">
                <span class="backup-info-label">Volume:</span>
                <span class="backup-info-value">{{ restoreResult.volume_name }}</span>
              </div>
              <div class="backup-info-item">
                <span class="backup-info-label">备份路径:</span>
                <span class="backup-info-value">{{ restoreForm.backup_path }}</span>
              </div>
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-primary" @click="closeRestoreModal">
                确定
              </button>
            </div>
          </div>
          <div v-else>
            <div class="backup-info-preview">
              <p>即将恢复备份到 Volume:</p>
              <strong>{{ restoreVolume?.name || restoreVolumeName }}</strong>
            </div>
            
            <form @submit.prevent="handleRestoreVolume">
              <div class="form-group">
                <label class="form-label">备份文件路径 <span class="required">*</span></label>
                <input 
                  type="text" 
                  v-model="restoreForm.backup_path" 
                  class="form-input"
                  placeholder="例如: /tmp/volume_backups/my-volume-20260101.tar.gz"
                  :disabled="restoreLoading"
                  required
                />
                <p class="form-hint">请输入备份文件的完整路径</p>
              </div>
              
              <div class="form-group">
                <label class="form-label">目标 Volume 名称</label>
                <input 
                  type="text" 
                  v-model="restoreForm.target_name" 
                  class="form-input"
                  placeholder="留空则恢复到原 Volume"
                  :disabled="restoreLoading"
                />
                <p class="form-hint">留空则恢复到原 Volume（将覆盖现有数据）</p>
              </div>
              
              <div class="modal-footer">
                <button type="button" class="btn btn-outline" @click="closeRestoreModal" :disabled="restoreLoading">
                  取消
                </button>
                <button type="submit" class="btn btn-primary" :disabled="restoreLoading || !restoreForm.backup_path">
                  {{ restoreLoading ? '恢复中...' : '开始恢复' }}
                </button>
              </div>
            </form>
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
          <p>确定要删除 Volume "<strong>{{ deletingVolume?.name }}</strong>" 吗？</p>
          
          <div class="delete-info" v-if="deletingVolume?.container_count > 0">
            ⚠️ 该 Volume 正在被 {{ deletingVolume.container_count }} 个容器使用
          </div>
          
          <div class="checkbox-group">
            <label class="checkbox-label">
              <input 
                type="checkbox" 
                v-model="deleteForm.force"
                :disabled="deleteConfirmLoading"
              />
              <span>强制删除（断开所有使用的容器）</span>
            </label>
          </div>
          
          <div class="modal-footer">
            <button type="button" class="btn btn-outline" @click="closeDeleteConfirm" :disabled="deleteConfirmLoading">
              取消
            </button>
            <button type="button" class="btn btn-danger" @click="executeDeleteVolume" :disabled="deleteConfirmLoading">
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
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '../components/AppLayout.vue'
import { useAuth } from '../composables/useAuth'
import { volumeApi, storageApi } from '../api/containerApi'

const router = useRouter()
const { isAdmin, currentUser, logout } = useAuth()

if (!isAdmin.value) {
  router.push('/')
}

const activeTab = ref('volumes')

const volumes = ref([])
const volumesLoading = ref(false)
const volumesError = ref(null)
const volumeSearchQuery = ref('')
const volumeFilterUnused = ref('')
const volumeCurrentPage = ref(1)
const volumePageSize = ref(20)
const volumeTotal = ref(0)
const volumeTotalPages = ref(0)

const bindMounts = ref([])
const bindMountsLoading = ref(false)
const bindMountSearchQuery = ref('')

const storageUsage = ref(null)
const storageUsageLoading = ref(false)
const showCleanupSuggestions = ref(false)

const showCreateVolumeModal = ref(false)
const createVolumeLoading = ref(false)
const createVolumeError = ref('')
const createVolumeForm = ref({
  name: '',
  driver: 'local',
  labelsInput: ''
})

const showVolumeDetailModal = ref(false)
const volumeDetailLoading = ref(false)
const volumeDetail = ref(null)

const showBackupModal = ref(false)
const backupVolume = ref(null)
const backupLoading = ref(false)
const backupError = ref('')
const backupResult = ref(null)
const backupForm = ref({
  compression: 'gzip',
  backup_path: ''
})

const showRestoreModal = ref(false)
const restoreVolume = ref(null)
const restoreVolumeName = ref('')
const restoreLoading = ref(false)
const restoreError = ref('')
const restoreResult = ref(null)
const restoreForm = ref({
  backup_path: '',
  target_name: ''
})

const showDeleteConfirm = ref(false)
const deletingVolume = ref(null)
const deleteConfirmLoading = ref(false)
const deleteForm = ref({
  force: false
})

const toastMessage = ref('')
const toastType = ref('success')
let toastTimeout = null

const totalVolumes = computed(() => volumeTotal.value || 0)
const totalBindMounts = computed(() => bindMounts.value.length || 0)

const filteredBindMounts = computed(() => {
  if (!bindMountSearchQuery.value) {
    return bindMounts.value
  }
  const query = bindMountSearchQuery.value.toLowerCase()
  return bindMounts.value.filter(mount => 
    mount.container_name?.toLowerCase().includes(query) ||
    mount.source?.toLowerCase().includes(query) ||
    mount.destination?.toLowerCase().includes(query)
  )
})

const sortedVolumes = computed(() => {
  if (!storageUsage.value?.volumes) return []
  return [...storageUsage.value.volumes].sort((a, b) => {
    if (a.is_unused !== b.is_unused) {
      return a.is_unused ? -1 : 1
    }
    return (b.used_size || 0) - (a.used_size || 0)
  })
})

const fetchVolumes = async () => {
  try {
    volumesLoading.value = true
    volumesError.value = null
    
    const params = {
      page: volumeCurrentPage.value,
      page_size: volumePageSize.value
    }
    
    if (volumeSearchQuery.value) {
      params.search = volumeSearchQuery.value
    }
    
    const result = await volumeApi.getVolumes(params)
    
    if (result.success) {
      const data = result.data || {}
      let volumeList = data.volumes || data.data || []
      
      if (volumeFilterUnused.value === 'unused') {
        volumeList = volumeList.filter(v => v.is_unused)
      } else if (volumeFilterUnused.value === 'used') {
        volumeList = volumeList.filter(v => !v.is_unused)
      }
      
      volumes.value = volumeList
      volumeTotal.value = data.total || volumeList.length
      volumeTotalPages.value = data.total_pages || 1
    } else {
      volumesError.value = result.message || '获取 Volume 列表失败'
    }
  } catch (err) {
    volumesError.value = err.message || '获取 Volume 列表失败'
  } finally {
    volumesLoading.value = false
  }
}

const fetchBindMounts = async () => {
  try {
    bindMountsLoading.value = true
    const result = await storageApi.getBindMounts()
    if (result.success) {
      const data = result.data || {}
      bindMounts.value = data.mounts || data || []
    }
  } catch (err) {
    console.error('获取绑定挂载失败:', err)
  } finally {
    bindMountsLoading.value = false
  }
}

const fetchStorageUsage = async () => {
  try {
    storageUsageLoading.value = true
    const result = await storageApi.getStorageUsage()
    if (result.success) {
      storageUsage.value = result.data
    }
  } catch (err) {
    console.error('获取存储使用分析失败:', err)
  } finally {
    storageUsageLoading.value = false
  }
}

const openCreateVolumeModal = () => {
  createVolumeForm.value = {
    name: '',
    driver: 'local',
    labelsInput: ''
  }
  createVolumeError.value = ''
  showCreateVolumeModal.value = true
}

const closeCreateVolumeModal = () => {
  showCreateVolumeModal.value = false
  createVolumeForm.value = {
    name: '',
    driver: 'local',
    labelsInput: ''
  }
  createVolumeError.value = ''
}

const handleCreateVolume = async () => {
  if (!createVolumeForm.value.name) {
    createVolumeError.value = '请输入 Volume 名称'
    return
  }
  
  try {
    createVolumeLoading.value = true
    createVolumeError.value = ''
    
    const data = {
      name: createVolumeForm.value.name,
      driver: createVolumeForm.value.driver
    }
    
    if (createVolumeForm.value.labelsInput) {
      data.labels = {}
      const labelPairs = createVolumeForm.value.labelsInput.split(',')
      for (const pair of labelPairs) {
        const [key, value] = pair.split('=')
        if (key && value) {
          data.labels[key.trim()] = value.trim()
        }
      }
    }
    
    const result = await volumeApi.createVolume(data)
    
    if (result.success) {
      showToast('Volume 创建成功', 'success')
      closeCreateVolumeModal()
      fetchVolumes()
    } else {
      createVolumeError.value = result.message || '创建失败'
    }
  } catch (err) {
    createVolumeError.value = err.message || '创建失败'
  } finally {
    createVolumeLoading.value = false
  }
}

const viewVolumeDetail = async (volume) => {
  volumeDetailLoading.value = true
  showVolumeDetailModal.value = true
  
  try {
    const result = await volumeApi.getVolumeInfo(volume.name || volume.id)
    
    if (result.success) {
      volumeDetail.value = result.data
    }
  } catch (err) {
    console.error('获取 Volume 详情失败:', err)
  } finally {
    volumeDetailLoading.value = false
  }
}

const closeVolumeDetailModal = () => {
  showVolumeDetailModal.value = false
  volumeDetail.value = null
}

const openBackupModal = (volume) => {
  backupVolume.value = volume
  backupForm.value = {
    compression: 'gzip',
    backup_path: ''
  }
  backupError.value = ''
  backupResult.value = null
  showBackupModal.value = true
}

const closeBackupModal = () => {
  showBackupModal.value = false
  backupVolume.value = null
  backupForm.value = {
    compression: 'gzip',
    backup_path: ''
  }
  backupError.value = ''
  backupResult.value = null
}

const handleBackupVolume = async () => {
  try {
    backupLoading.value = true
    backupError.value = ''
    
    const data = {
      compression: backupForm.value.compression
    }
    
    if (backupForm.value.backup_path) {
      data.backup_path = backupForm.value.backup_path
    }
    
    const result = await volumeApi.backupVolume(backupVolume.value.name, data)
    
    if (result.success) {
      backupResult.value = result.data
      showToast('Volume 备份成功', 'success')
    } else {
      backupError.value = result.message || '备份失败'
    }
  } catch (err) {
    backupError.value = err.message || '备份失败'
  } finally {
    backupLoading.value = false
  }
}

const openRestoreModal = (volume) => {
  restoreVolume.value = volume
  restoreVolumeName.value = volume?.name || ''
  restoreForm.value = {
    backup_path: '',
    target_name: volume?.name || ''
  }
  restoreError.value = ''
  restoreResult.value = null
  showRestoreModal.value = true
}

const openRestoreModalFromBackup = () => {
  closeBackupModal()
  restoreVolume.value = backupVolume.value
  restoreVolumeName.value = backupResult.value?.volume_name || backupVolume.value?.name || ''
  restoreForm.value = {
    backup_path: backupResult.value?.backup_path || '',
    target_name: backupResult.value?.volume_name || backupVolume.value?.name || ''
  }
  restoreError.value = ''
  restoreResult.value = null
  showRestoreModal.value = true
}

const closeRestoreModal = () => {
  showRestoreModal.value = false
  restoreVolume.value = null
  restoreVolumeName.value = ''
  restoreForm.value = {
    backup_path: '',
    target_name: ''
  }
  restoreError.value = ''
  restoreResult.value = null
}

const handleRestoreVolume = async () => {
  if (!restoreForm.value.backup_path) {
    restoreError.value = '请输入备份文件路径'
    return
  }
  
  try {
    restoreLoading.value = true
    restoreError.value = ''
    
    const data = {
      backup_path: restoreForm.value.backup_path
    }
    
    const targetVolumeName = restoreForm.value.target_name || restoreVolumeName.value
    
    const result = await volumeApi.restoreVolume(targetVolumeName, data)
    
    if (result.success) {
      restoreResult.value = result.data
      showToast('Volume 恢复成功', 'success')
      fetchVolumes()
    } else {
      restoreError.value = result.message || '恢复失败'
    }
  } catch (err) {
    restoreError.value = err.message || '恢复失败'
  } finally {
    restoreLoading.value = false
  }
}

const confirmDeleteVolume = (volume) => {
  deletingVolume.value = volume
  deleteForm.value = {
    force: false
  }
  showDeleteConfirm.value = true
}

const closeDeleteConfirm = () => {
  showDeleteConfirm.value = false
  deletingVolume.value = null
}

const executeDeleteVolume = async () => {
  if (!deletingVolume.value) return
  
  try {
    deleteConfirmLoading.value = true
    
    const params = {}
    if (deleteForm.value.force) {
      params.force = true
    }
    
    const result = await volumeApi.deleteVolume(deletingVolume.value.name, params)
    
    if (result.success) {
      showToast('Volume 删除成功', 'success')
      closeDeleteConfirm()
      fetchVolumes()
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

const formatBytes = (bytes) => {
  if (bytes === 0 || !bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

const getUsagePercent = (used, total) => {
  if (!total || total === 0) return 0
  return Math.round((used / total) * 100)
}

const getRiskLabel = (riskLevel) => {
  const labels = {
    'low': '低风险',
    'medium': '中风险',
    'high': '高风险'
  }
  return labels[riskLevel] || '低风险'
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
  fetchVolumes()
})
</script>

<style scoped>
.tabs {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 0.5rem;
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1.25rem;
  background-color: transparent;
  border: none;
  border-radius: 0.375rem 0.375rem 0 0;
  color: var(--text-secondary);
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.tab-btn:hover:not(.active) {
  background-color: var(--bg-primary);
  color: var(--text-primary);
}

.tab-btn.active {
  background-color: var(--bg-primary);
  color: var(--primary-color);
  border-bottom: 2px solid var(--primary-color);
}

.tab-content {
  animation: fadeIn 0.2s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
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

.volume-list-container,
.usage-container {
  background-color: var(--bg-primary);
  border-radius: 0.75rem;
  padding: 1.5rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.volume-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(450px, 1fr));
  gap: 1rem;
}

.volume-card {
  background-color: var(--bg-secondary);
  border-radius: 0.75rem;
  border: 1px solid var(--border-color);
  overflow: hidden;
  transition: box-shadow 0.2s, border-color 0.2s;
}

.volume-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  border-color: var(--primary-color);
}

.volume-card.card-unused {
  border-left: 3px solid #f59e0b;
}

.volume-card-header {
  display: flex;
  padding: 1.25rem;
  gap: 1rem;
}

.volume-icon {
  width: 48px;
  height: 48px;
  border-radius: 0.5rem;
  background: linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.volume-info {
  flex: 1;
  min-width: 0;
}

.volume-name {
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

.badge-success {
  background-color: rgba(16, 185, 129, 0.1);
  color: #10b981;
}

.badge-warning {
  background-color: rgba(245, 158, 11, 0.1);
  color: #d97706;
}

.badge-info {
  background-color: rgba(14, 165, 233, 0.1);
  color: #0ea5e9;
}

.badge-secondary {
  background-color: var(--bg-primary);
  color: var(--text-secondary);
}

.badge-primary {
  background-color: rgba(99, 102, 241, 0.1);
  color: #6366f1;
}

.volume-meta {
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

.volume-card-footer {
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

.bind-mounts-table {
  overflow-x: auto;
}

.bind-mounts-table table {
  width: 100%;
  border-collapse: collapse;
  background-color: var(--bg-primary);
  border-radius: 0.75rem;
  overflow: hidden;
}

.bind-mounts-table th,
.bind-mounts-table td {
  padding: 1rem;
  text-align: left;
  border-bottom: 1px solid var(--border-color);
}

.bind-mounts-table th {
  background-color: var(--bg-secondary);
  font-weight: 600;
  font-size: 0.875rem;
  color: var(--text-secondary);
}

.bind-mounts-table td {
  font-size: 0.875rem;
}

.bind-mounts-table tr:hover td {
  background-color: var(--bg-secondary);
}

.container-cell {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.container-name {
  font-weight: 600;
  color: var(--text-primary);
}

.container-id {
  font-size: 0.75rem;
  color: var(--text-secondary);
  font-family: 'Courier New', monospace;
}

.path-cell {
  max-width: 300px;
}

.path-cell code {
  font-size: 0.75rem;
  word-break: break-all;
  background-color: var(--bg-secondary);
  padding: 0.25rem 0.5rem;
  border-radius: 0.25rem;
}

.usage-summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1rem;
  margin-bottom: 2rem;
}

.usage-card {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1.25rem;
  background-color: var(--bg-secondary);
  border-radius: 0.75rem;
  border: 1px solid var(--border-color);
}

.usage-icon {
  width: 48px;
  height: 48px;
  border-radius: 0.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.usage-icon-primary {
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  color: white;
}

.usage-icon-warning {
  background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
  color: white;
}

.usage-icon-success {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  color: white;
}

.usage-icon-danger {
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
  color: white;
}

.usage-info {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.usage-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
}

.usage-label {
  font-size: 0.875rem;
  color: var(--text-secondary);
}

.usage-section {
  margin-bottom: 2rem;
}

.section-title {
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 1rem 0;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border-color);
}

.volume-usage-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.volume-usage-item {
  padding: 1rem;
  background-color: var(--bg-secondary);
  border-radius: 0.5rem;
  border: 1px solid var(--border-color);
}

.volume-usage-item.item-unused {
  border-left: 3px solid #f59e0b;
}

.volume-usage-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.75rem;
}

.volume-usage-name {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.volume-usage-name .name {
  font-weight: 600;
  color: var(--text-primary);
}

.volume-usage-meta {
  display: flex;
  gap: 1rem;
  font-size: 0.75rem;
}

.volume-usage-bar-container {
  margin-bottom: 0.5rem;
}

.usage-bar {
  height: 8px;
  background-color: var(--border-color);
  border-radius: 4px;
  overflow: hidden;
}

.usage-bar-fill {
  height: 100%;
  background-color: #10b981;
  border-radius: 4px;
  transition: width 0.3s;
}

.usage-bar-fill.bar-warning {
  background-color: #f59e0b;
}

.usage-bar-fill.bar-danger {
  background-color: #ef4444;
}

.usage-bar-text {
  display: flex;
  justify-content: space-between;
  margin-top: 0.5rem;
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.volume-usage-path {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.volume-usage-path code {
  font-family: 'Courier New', monospace;
  background-color: var(--bg-primary);
  padding: 0.125rem 0.375rem;
  border-radius: 0.25rem;
}

.suggestions-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.suggestion-item {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem;
  background-color: var(--bg-secondary);
  border-radius: 0.5rem;
  border: 1px solid var(--border-color);
}

.suggestion-item.risk-low {
  border-left: 3px solid #10b981;
}

.suggestion-item.risk-medium {
  border-left: 3px solid #f59e0b;
}

.suggestion-item.risk-high {
  border-left: 3px solid #ef4444;
}

.suggestion-icon {
  width: 40px;
  height: 40px;
  border-radius: 0.5rem;
  background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.suggestion-content {
  flex: 1;
  min-width: 0;
}

.suggestion-name {
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 0.25rem;
}

.suggestion-reason {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.suggestion-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.size-badge {
  font-family: 'Courier New', monospace;
  font-size: 0.75rem;
  color: var(--text-primary);
  background-color: var(--bg-primary);
  padding: 0.25rem 0.5rem;
  border-radius: 0.25rem;
}

.risk-badge {
  font-size: 0.75rem;
  padding: 0.25rem 0.5rem;
  border-radius: 0.25rem;
}

.risk-badge.risk-low {
  background-color: rgba(16, 185, 129, 0.1);
  color: #10b981;
}

.risk-badge.risk-medium {
  background-color: rgba(245, 158, 11, 0.1);
  color: #d97706;
}

.risk-badge.risk-high {
  background-color: rgba(239, 68, 68, 0.1);
  color: #ef4444;
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

.btn-warning {
  background-color: #f59e0b;
  color: white;
}

.btn-warning:hover:not(:disabled) {
  background-color: #d97706;
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

.mounts-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.mount-item {
  padding: 1rem;
  background-color: var(--bg-secondary);
  border-radius: 0.5rem;
}

.mount-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.mount-paths {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.path-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.path-label {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.backup-info-preview {
  padding: 1rem;
  background-color: var(--bg-secondary);
  border-radius: 0.5rem;
  margin-bottom: 1.5rem;
}

.backup-info-preview p {
  margin: 0 0 0.5rem 0;
  color: var(--text-secondary);
}

.backup-info-preview strong {
  font-size: 1.125rem;
  color: var(--text-primary);
}

.backup-success {
  text-align: center;
  padding: 1rem;
}

.success-icon {
  font-size: 3rem;
  margin-bottom: 1rem;
}

.backup-success p {
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 1.5rem;
}

.backup-info {
  text-align: left;
  background-color: var(--bg-secondary);
  padding: 1rem;
  border-radius: 0.5rem;
  margin-bottom: 1.5rem;
}

.backup-info-item {
  display: flex;
  justify-content: space-between;
  padding: 0.5rem 0;
  border-bottom: 1px solid var(--border-color);
}

.backup-info-item:last-child {
  border-bottom: none;
}

.backup-info-label {
  color: var(--text-secondary);
}

.backup-info-value {
  font-family: 'Courier New', monospace;
  color: var(--text-primary);
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
  
  .volume-list {
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
  
  .tabs {
    flex-wrap: wrap;
  }
  
  .usage-summary {
    grid-template-columns: 1fr;
  }
}
</style>