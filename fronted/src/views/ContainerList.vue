<template>
  <div class="container-list">
    <!-- Header -->
    <header class="header">
      <div class="container">
        <div class="header-content">
          <div class="logo">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
            </svg>
            <div>
              <h1>Docker 日志查看器</h1>
              <p>容器管理</p>
            </div>
          </div>
          <div class="header-actions">
            <router-link to="/dashboard" class="btn btn-outline">
              Dashboard
            </router-link>
            <router-link to="/multi-logs" class="btn btn-primary">
              多容器日志聚合
            </router-link>
            <button class="btn btn-outline" @click="fetchContainers">
              刷新
            </button>
          </div>
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <main class="main-content">
      <div class="container">
        <div class="card">
          <!-- Controls -->
          <div class="controls">
            <div class="search-box">
              <input
                ref="searchInputRef"
                type="text"
                v-model="searchQuery"
                placeholder="搜索容器名称、镜像或 ID..."
                class="input"
              />
            </div>
            <div class="filters">
              <label class="checkbox-label">
                <input
                  type="checkbox"
                  v-model="showAll"
                />
                <span>显示全部容器</span>
              </label>
            </div>
          </div>

          <!-- Error Message -->
          <div v-if="error" class="error-message">
            {{ error }}
          </div>

          <!-- Loading State -->
          <div v-if="loading" class="loading">
            <div v-for="i in 5" :key="i" class="skeleton"></div>
          </div>

          <!-- Batch Actions Bar -->
          <div v-if="selectedContainerIds.length > 0" class="batch-actions-bar">
            <div class="batch-actions-info">
              <span>已选择 <strong>{{ selectedContainerIds.length }}</strong> 个容器</span>
            </div>
            <div class="batch-actions-buttons">
              <button
                class="btn btn-success btn-sm"
                @click="confirmBatchStart"
                :disabled="batchOperationInProgress"
              >
                批量启动
              </button>
              <button
                class="btn btn-warning btn-sm"
                @click="confirmBatchStop"
                :disabled="batchOperationInProgress"
              >
                批量停止
              </button>
              <button
                class="btn btn-danger btn-sm"
                @click="confirmBatchDelete"
                :disabled="batchOperationInProgress"
              >
                批量删除
              </button>
              <button
                class="btn btn-ghost btn-sm"
                @click="clearSelection"
                :disabled="batchOperationInProgress"
              >
                取消选择
              </button>
            </div>
          </div>

          <!-- Container Table -->
          <div class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th style="width: 40px;">
                    <label class="checkbox-label">
                      <input
                        type="checkbox"
                        :checked="isAllSelected"
                        :indeterminate="isIndeterminate"
                        @change="toggleSelectAll"
                      />
                    </label>
                  </th>
                  <th>状态</th>
                  <th>名称</th>
                  <th>镜像</th>
                  <th>ID</th>
                  <th>状态</th>
                  <th>创建时间</th>
                  <th class="text-right">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="total === 0">
                  <td colspan="8" class="empty-state">
                    {{ searchQuery ? '没有找到匹配的容器' : '暂无容器' }}
                  </td>
                </tr>
                <tr 
                  v-for="(container, index) in containers" 
                  :key="container.id"
                  :class="{ 
                    'row-selected': selectedIndex === index,
                    'row-checkbox-selected': isContainerSelected(container.id)
                  }"
                >
                  <td>
                    <label class="checkbox-label">
                      <input
                        type="checkbox"
                        :checked="isContainerSelected(container.id)"
                        @change="toggleContainerSelection(container.id)"
                      />
                    </label>
                  </td>
                  <td>
                    <div
                      class="status-dot"
                      :class="getStatusClass(container.state)"
                    ></div>
                  </td>
                  <td class="font-medium">
                    {{ getContainerName(container.names) }}
                  </td>
                  <td class="text-muted">{{ container.image }}</td>
                  <td class="font-mono">{{ container.id.slice(0, 12) }}</td>
                  <td>
                    <span
                      class="badge"
                      :class="container.state === 'running' ? 'badge-success' : 'badge-secondary'"
                    >
                      {{ container.status }}
                    </span>
                  </td>
                  <td class="text-muted">{{ formatDate(container.created) }}</td>
                  <td class="text-right">
                    <div class="action-buttons">
                      <button
                        v-if="container.state !== 'running'"
                        class="btn btn-success btn-sm action-btn"
                        @click="startContainer(container)"
                        :disabled="operationInProgress === container.id"
                        title="启动容器"
                      >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                          <polygon points="5 3 19 12 5 21 5 3"></polygon>
                        </svg>
                      </button>
                      <button
                        v-if="container.state === 'running'"
                        class="btn btn-warning btn-sm action-btn"
                        @click="stopContainer(container)"
                        :disabled="operationInProgress === container.id"
                        title="停止容器"
                      >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                          <rect x="6" y="4" width="4" height="16"></rect>
                          <rect x="14" y="4" width="4" height="16"></rect>
                        </svg>
                      </button>
                      <router-link
                        :to="`/containers/${container.id}`"
                        class="btn btn-ghost btn-sm action-btn"
                        title="查看日志"
                      >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                          <polyline points="14 2 14 8 20 8"></polyline>
                          <line x1="16" y1="13" x2="8" y2="13"></line>
                          <line x1="16" y1="17" x2="8" y2="17"></line>
                          <polyline points="10 9 9 9 8 9"></polyline>
                        </svg>
                      </router-link>
                      
                      <div class="dropdown" :class="{ 'dropdown-open': openDropdown === container.id }">
                        <button 
                          class="btn btn-ghost btn-sm action-btn"
                          @click="toggleDropdown(container.id)"
                          title="更多操作"
                        >
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <circle cx="12" cy="12" r="1"></circle>
                            <circle cx="12" cy="5" r="1"></circle>
                            <circle cx="12" cy="19" r="1"></circle>
                          </svg>
                        </button>
                        <div class="dropdown-menu" v-if="openDropdown === container.id">
                          <button 
                            class="dropdown-item"
                            @click="restartContainer(container)"
                            :disabled="operationInProgress === container.id"
                          >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="dropdown-icon">
                              <polyline points="23 4 23 10 17 10"></polyline>
                              <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
                            </svg>
                            重启容器
                          </button>
                          <button 
                            class="dropdown-item"
                            @click="viewContainerDetails(container)"
                          >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="dropdown-icon">
                              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                              <circle cx="12" cy="12" r="3"></circle>
                            </svg>
                            查看详情
                          </button>
                          <button 
                            class="dropdown-item"
                            @click="viewImageLayers(container)"
                          >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="dropdown-icon">
                              <rect x="3" y="1" width="18" height="18" rx="2" ry="2"></rect>
                              <line x1="9" y1="9" x2="15" y2="9"></line>
                              <line x1="9" y1="15" x2="15" y2="15"></line>
                              <line x1="12" y1="6" x2="12" y2="18"></line>
                            </svg>
                            镜像层信息
                          </button>
                          <div class="dropdown-divider"></div>
                          <button 
                            class="dropdown-item dropdown-danger"
                            @click="confirmDeleteContainer(container)"
                            :disabled="operationInProgress === container.id"
                          >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="dropdown-icon">
                              <polyline points="3 6 5 6 21 6"></polyline>
                              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                              <line x1="10" y1="11" x2="10" y2="17"></line>
                              <line x1="14" y1="11" x2="14" y2="17"></line>
                            </svg>
                            删除容器
                          </button>
                        </div>
                      </div>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
            <div class="table-footer">
              <span>共 {{ total }} 个容器</span>
              <div v-if="totalPages > 1" class="pagination">
                <button
                  class="pagination-btn"
                  @click="prevPage"
                  :disabled="currentPage === 1"
                >
                  上一页
                </button>
                <span class="pagination-info">
                  第 {{ currentPage }} / {{ totalPages }} 页
                </span>
                <button
                  class="pagination-btn"
                  @click="nextPage"
                  :disabled="currentPage === totalPages"
                >
                  下一页
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>

    <!-- Container Details Modal -->
    <div v-if="showDetailsModal" class="modal-overlay" @click.self="closeDetailsModal">
      <div class="modal modal-large">
        <div class="modal-header">
          <h3 class="modal-title">容器详情 - {{ currentContainer?.name || currentContainer?.names?.[0]?.replace(/^\//, '') || 'N/A' }}</h3>
          <button class="modal-close" @click="closeDetailsModal">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        <div class="modal-body modal-scrollable">
          <div v-if="loadingDetails" class="loading-details">
            <div class="loading-spinner"></div>
            <p>加载中...</p>
          </div>
          <div v-else-if="containerDetails">
            <div class="details-section">
              <h4 class="section-title">基本信息</h4>
              <div class="details-grid">
                <div class="detail-item">
                  <span class="detail-label">容器 ID</span>
                  <span class="detail-value font-mono">{{ containerDetails.id?.slice(0, 12) || 'N/A' }}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">名称</span>
                  <span class="detail-value">{{ containerDetails.name }}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">镜像</span>
                  <span class="detail-value">{{ containerDetails.image }}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">状态</span>
                  <span class="detail-value">
                    <span class="badge" :class="containerDetails.running ? 'badge-success' : 'badge-secondary'">
                      {{ containerDetails.status }}
                    </span>
                  </span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">运行状态</span>
                  <span class="detail-value">
                    {{ containerDetails.running ? '运行中' : '已停止' }}
                    <span v-if="containerDetails.paused" class="text-warning ml-2">(已暂停)</span>
                    <span v-if="containerDetails.restarting" class="text-warning ml-2">(重启中)</span>
                  </span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">退出代码</span>
                  <span class="detail-value">{{ containerDetails.exit_code }}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">创建时间</span>
                  <span class="detail-value">{{ containerDetails.created }}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">启动时间</span>
                  <span class="detail-value">{{ containerDetails.started_at || 'N/A' }}</span>
                </div>
                <div v-if="containerDetails.finished_at" class="detail-item">
                  <span class="detail-label">结束时间</span>
                  <span class="detail-value">{{ containerDetails.finished_at }}</span>
                </div>
              </div>
            </div>

            <div class="details-section">
              <h4 class="section-title">配置信息</h4>
              <div class="details-grid">
                <div class="detail-item">
                  <span class="detail-label">工作目录</span>
                  <span class="detail-value">{{ containerDetails.working_dir || 'N/A' }}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">用户</span>
                  <span class="detail-value">{{ containerDetails.user || 'N/A' }}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">重启策略</span>
                  <span class="detail-value">{{ containerDetails.restart_policy || 'N/A' }}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">特权模式</span>
                  <span class="detail-value">{{ containerDetails.privileged ? '是' : '否' }}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">只读根文件系统</span>
                  <span class="detail-value">{{ containerDetails.readonly_rootfs ? '是' : '否' }}</span>
                </div>
              </div>
            </div>

            <div class="details-section">
              <h4 class="section-title">资源限制</h4>
              <div class="details-grid">
                <div class="detail-item">
                  <span class="detail-label">内存限制</span>
                  <span class="detail-value">{{ formatBytes(containerDetails.memory_limit) || '无限制' }}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">内存预留</span>
                  <span class="detail-value">{{ formatBytes(containerDetails.memory_reservation) || '无' }}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">CPU 份额</span>
                  <span class="detail-value">{{ containerDetails.cpu_shares || '默认' }}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">CPU 数量</span>
                  <span class="detail-value">{{ containerDetails.cpus || '无限制' }}</span>
                </div>
              </div>
            </div>

            <div v-if="containerDetails.command && containerDetails.command.length > 0" class="details-section">
              <h4 class="section-title">启动命令</h4>
              <div class="code-block">
                <pre>{{ containerDetails.command.join(' ') }}</pre>
              </div>
            </div>

            <div v-if="containerDetails.env && containerDetails.env.length > 0" class="details-section">
              <h4 class="section-title">环境变量</h4>
              <div class="table-container">
                <table class="details-table">
                  <thead>
                    <tr>
                      <th>键</th>
                      <th>值</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(env, idx) in containerDetails.env" :key="idx">
                      <td class="font-mono">{{ env.key }}</td>
                      <td class="font-mono">{{ env.value }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div v-if="containerDetails.port_mappings && containerDetails.port_mappings.length > 0" class="details-section">
              <h4 class="section-title">端口映射</h4>
              <div class="table-container">
                <table class="details-table">
                  <thead>
                    <tr>
                      <th>容器端口</th>
                      <th>主机 IP</th>
                      <th>主机端口</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(port, idx) in containerDetails.port_mappings" :key="idx">
                      <td>{{ port.container_port }}</td>
                      <td>{{ port.host_ip || '0.0.0.0' }}</td>
                      <td>{{ port.host_port }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div v-if="containerDetails.networks && containerDetails.networks.length > 0" class="details-section">
              <h4 class="section-title">网络配置</h4>
              <div class="table-container">
                <table class="details-table">
                  <thead>
                    <tr>
                      <th>网络</th>
                      <th>IP 地址</th>
                      <th>MAC 地址</th>
                      <th>网关</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(net, idx) in containerDetails.networks" :key="idx">
                      <td>{{ net.name }}</td>
                      <td class="font-mono">{{ net.ip_address || 'N/A' }}</td>
                      <td class="font-mono">{{ net.mac_address || 'N/A' }}</td>
                      <td class="font-mono">{{ net.gateway || 'N/A' }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div v-if="containerDetails.mounts && containerDetails.mounts.length > 0" class="details-section">
              <h4 class="section-title">挂载点</h4>
              <div class="table-container">
                <table class="details-table">
                  <thead>
                    <tr>
                      <th>类型</th>
                      <th>源</th>
                      <th>目标</th>
                      <th>模式</th>
                      <th>读写</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(mount, idx) in containerDetails.mounts" :key="idx">
                      <td>{{ mount.type }}</td>
                      <td class="font-mono">{{ mount.source }}</td>
                      <td class="font-mono">{{ mount.destination }}</td>
                      <td>{{ mount.mode || 'N/A' }}</td>
                      <td>
                        <span :class="mount.rw ? 'text-success' : 'text-muted'">
                          {{ mount.rw ? '读写' : '只读' }}
                        </span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div v-if="containerDetails.labels && Object.keys(containerDetails.labels).length > 0" class="details-section">
              <h4 class="section-title">标签</h4>
              <div class="table-container">
                <table class="details-table">
                  <thead>
                    <tr>
                      <th>键</th>
                      <th>值</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(value, key) in containerDetails.labels" :key="key">
                      <td class="font-mono">{{ key }}</td>
                      <td class="font-mono">{{ value }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div v-if="containerDetails.log_config" class="details-section">
              <h4 class="section-title">日志配置</h4>
              <div class="details-grid">
                <div class="detail-item">
                  <span class="detail-label">日志驱动</span>
                  <span class="detail-value">{{ containerDetails.log_config.Type || 'N/A' }}</span>
                </div>
              </div>
              <div v-if="containerDetails.log_config.Config && Object.keys(containerDetails.log_config.Config).length > 0" class="table-container mt-2">
                <table class="details-table">
                  <thead>
                    <tr>
                      <th>配置项</th>
                      <th>值</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(value, key) in containerDetails.log_config.Config" :key="key">
                      <td class="font-mono">{{ key }}</td>
                      <td class="font-mono">{{ value }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-outline" @click="closeDetailsModal">关闭</button>
        </div>
      </div>
    </div>

    <!-- Image Layers Modal -->
    <div v-if="showImageLayersModal" class="modal-overlay" @click.self="closeImageLayersModal">
      <div class="modal modal-large">
        <div class="modal-header">
          <h3 class="modal-title">镜像层信息 - {{ currentContainer?.image || 'N/A' }}</h3>
          <button class="modal-close" @click="closeImageLayersModal">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        <div class="modal-body modal-scrollable">
          <div v-if="loadingImageLayers" class="loading-details">
            <div class="loading-spinner"></div>
            <p>加载中...</p>
          </div>
          <div v-else-if="imageLayersData">
            <div class="details-section">
              <h4 class="section-title">镜像信息</h4>
              <div class="details-grid">
                <div class="detail-item">
                  <span class="detail-label">镜像 ID</span>
                  <span class="detail-value font-mono">{{ imageLayersData.id?.slice(7, 19) || imageLayersData.id?.slice(0, 12) || 'N/A' }}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">标签</span>
                  <span class="detail-value">{{ imageLayersData.tags?.join(', ') || 'N/A' }}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">操作系统</span>
                  <span class="detail-value">{{ imageLayersData.os || 'N/A' }}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">架构</span>
                  <span class="detail-value">{{ imageLayersData.architecture || 'N/A' }}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">创建时间</span>
                  <span class="detail-value">{{ imageLayersData.created || 'N/A' }}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">总大小</span>
                  <span class="detail-value">{{ formatBytes(imageLayersData.total_size) }}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">层数</span>
                  <span class="detail-value">{{ imageLayersData.layer_count }}</span>
                </div>
              </div>
            </div>

            <div class="details-section">
              <h4 class="section-title">镜像层详情 (从底层到顶层)</h4>
              <div v-if="imageLayersData.layers && imageLayersData.layers.length > 0" class="layers-list">
                <div 
                  v-for="(layer, idx) in imageLayersData.layers" 
                  :key="idx" 
                  class="layer-item"
                  :class="{ 'layer-top': idx === imageLayersData.layers.length - 1 }"
                >
                  <div class="layer-header">
                    <div class="layer-index">
                      <span class="layer-number">Layer {{ idx + 1 }}</span>
                      <span v-if="layer.tags && layer.tags.length > 0" class="layer-tag badge badge-primary">{{ layer.tags[0] }}</span>
                    </div>
                    <div class="layer-size">{{ formatBytes(layer.size) }}</div>
                  </div>
                  <div class="layer-command">
                    <div class="code-block">
                      <pre>{{ layer.created_by || 'N/A' }}</pre>
                    </div>
                  </div>
                  <div class="layer-meta">
                    <span class="layer-id font-mono">{{ layer.id }}</span>
                    <span class="layer-time">{{ formatTimestamp(layer.created) }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-outline" @click="closeImageLayersModal">关闭</button>
        </div>
      </div>
    </div>

    <!-- Confirm Delete Modal -->
    <div v-if="showDeleteConfirm" class="modal-overlay" @click.self="cancelDelete">
      <div class="modal modal-small">
        <div class="modal-header">
          <h3 class="modal-title">确认删除容器</h3>
        </div>
        <div class="modal-body">
          <p class="delete-warning">
            确定要删除容器 <strong>{{ currentContainer?.names?.[0]?.replace(/^\//, '') || currentContainer?.name }}</strong> 吗？
          </p>
          <p class="delete-info">
            此操作不可撤销。
          </p>
          <div v-if="currentContainer?.state === 'running'" class="checkbox-label mt-2">
            <input type="checkbox" v-model="forceDelete" id="forceDelete" />
            <label for="forceDelete">强制删除（终止并删除运行中的容器）</label>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-outline" @click="cancelDelete">取消</button>
          <button class="btn btn-danger" @click="executeDeleteContainer">
            {{ operationInProgress === currentContainer?.id ? '删除中...' : '确认删除' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Batch Operation Confirm Modal -->
    <div v-if="showBatchConfirmModal" class="modal-overlay" @click.self="closeBatchConfirmModal">
      <div class="modal modal-small">
        <div class="modal-header">
          <h3 class="modal-title">
            {{ batchOperationType === 'start' ? '确认批量启动' : 
               batchOperationType === 'stop' ? '确认批量停止' : '确认批量删除' }}
          </h3>
        </div>
        <div class="modal-body">
          <p class="delete-warning">
            确定要{{ batchOperationType === 'start' ? '启动' : 
                       batchOperationType === 'stop' ? '停止' : '删除' }} 
            <strong>{{ selectedContainerIds.length }}</strong> 个容器吗？
          </p>
          <p class="delete-info">
            此操作将影响以下容器：
          </p>
          <div class="selected-containers-list">
            <div 
              v-for="container in selectedContainersForBatch" 
              :key="container.id"
              class="selected-container-item"
            >
              <span class="container-name">{{ getContainerName(container.names) }}</span>
              <span class="container-status">
                <span
                  class="badge"
                  :class="container.state === 'running' ? 'badge-success' : 'badge-secondary'"
                >
                  {{ container.status }}
                </span>
              </span>
            </div>
          </div>
          <div v-if="batchOperationType === 'delete' && hasRunningContainersInSelection" class="checkbox-label mt-2">
            <input type="checkbox" v-model="batchForceDelete" id="batchForceDelete" />
            <label for="batchForceDelete">强制删除（终止并删除运行中的容器）</label>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-outline" @click="closeBatchConfirmModal">取消</button>
          <button 
            :class="['btn', batchOperationType === 'delete' ? 'btn-danger' : batchOperationType === 'stop' ? 'btn-warning' : 'btn-success']"
            @click="executeBatchOperation"
          >
            {{ batchOperationInProgress ? '处理中...' : 
               batchOperationType === 'start' ? '确认启动' : 
               batchOperationType === 'stop' ? '确认停止' : '确认删除' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Batch Result Modal -->
    <div v-if="showBatchResultModal" class="modal-overlay" @click.self="closeBatchResultModal">
      <div class="modal modal-large">
        <div class="modal-header">
          <h3 class="modal-title">批量操作结果</h3>
          <button class="modal-close" @click="closeBatchResultModal">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        <div class="modal-body modal-scrollable">
          <div class="batch-result-summary">
            <div class="result-item success">
              <span class="result-label">成功</span>
              <span class="result-count">{{ batchResult?.data?.started_count || batchResult?.data?.stopped_count || batchResult?.data?.deleted_count || 0 }}</span>
            </div>
            <div class="result-item failed" v-if="batchResult?.data?.failed_count > 0">
              <span class="result-label">失败</span>
              <span class="result-count">{{ batchResult?.data?.failed_count || 0 }}</span>
            </div>
          </div>
          
          <div v-if="batchResult?.data?.failed && batchResult.data.failed.length > 0" class="failed-list-section">
            <h4 class="section-title">失败详情</h4>
            <div class="failed-list">
              <div 
                v-for="(failed, idx) in batchResult.data.failed" 
                :key="idx"
                class="failed-item"
              >
                <div class="failed-container-id font-mono">{{ failed.container_id?.slice(0, 12) || '未知容器' }}</div>
                <div class="failed-error">{{ failed.error }}</div>
              </div>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-primary" @click="closeBatchResultModal">确定</button>
        </div>
      </div>
    </div>

    <!-- Toast Notification -->
    <div v-if="toastMessage" class="toast" :class="toastType">
      {{ toastMessage }}
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { useKeyboardShortcuts } from '../composables/useKeyboardShortcuts'

const router = useRouter()
const { register } = useKeyboardShortcuts('container-list')

const containers = ref([])
const loading = ref(true)
const error = ref(null)
const searchQuery = ref('')
const showAll = ref(false)

const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const totalPages = ref(0)

const searchInputRef = ref(null)
const selectedIndex = ref(-1)

const openDropdown = ref(null)
const operationInProgress = ref(null)

const showDetailsModal = ref(false)
const showImageLayersModal = ref(false)
const showDeleteConfirm = ref(false)
const currentContainer = ref(null)
const containerDetails = ref(null)
const imageLayersData = ref(null)
const loadingDetails = ref(false)
const loadingImageLayers = ref(false)
const forceDelete = ref(false)

const toastMessage = ref('')
const toastType = ref('success')
let toastTimeout = null

const selectedContainerIds = ref([])
const batchOperationInProgress = ref(false)
const showBatchConfirmModal = ref(false)
const batchOperationType = ref('')
const batchForceDelete = ref(false)
const showBatchResultModal = ref(false)
const batchResult = ref(null)

const isAllSelected = computed(() => {
  if (containers.value.length === 0) return false
  return containers.value.every(container => selectedContainerIds.value.includes(container.id))
})

const isIndeterminate = computed(() => {
  if (containers.value.length === 0) return false
  const selectedCount = containers.value.filter(container => selectedContainerIds.value.includes(container.id)).length
  return selectedCount > 0 && selectedCount < containers.value.length
})

const selectedContainersForBatch = computed(() => {
  return containers.value.filter(container => selectedContainerIds.value.includes(container.id))
})

const hasRunningContainersInSelection = computed(() => {
  return selectedContainersForBatch.value.some(container => container.state === 'running')
})

const isContainerSelected = (containerId) => {
  return selectedContainerIds.value.includes(containerId)
}

const toggleContainerSelection = (containerId) => {
  const index = selectedContainerIds.value.indexOf(containerId)
  if (index === -1) {
    selectedContainerIds.value.push(containerId)
  } else {
    selectedContainerIds.value.splice(index, 1)
  }
}

const toggleSelectAll = () => {
  if (isAllSelected.value) {
    selectedContainerIds.value = []
  } else {
    selectedContainerIds.value = containers.value.map(container => container.id)
  }
}

const clearSelection = () => {
  selectedContainerIds.value = []
}

const confirmBatchStart = () => {
  batchOperationType.value = 'start'
  batchForceDelete.value = false
  showBatchConfirmModal.value = true
}

const confirmBatchStop = () => {
  batchOperationType.value = 'stop'
  batchForceDelete.value = false
  showBatchConfirmModal.value = true
}

const confirmBatchDelete = () => {
  batchOperationType.value = 'delete'
  batchForceDelete.value = hasRunningContainersInSelection.value
  showBatchConfirmModal.value = true
}

const closeBatchConfirmModal = () => {
  showBatchConfirmModal.value = false
  batchOperationType.value = ''
  batchForceDelete.value = false
}

const closeBatchResultModal = () => {
  showBatchResultModal.value = false
  batchResult.value = null
  clearSelection()
}

const executeBatchOperation = async () => {
  try {
    batchOperationInProgress.value = true
    
    let endpoint = ''
    let params = {}
    
    if (batchOperationType.value === 'start') {
      endpoint = '/api/containers/batch/start'
    } else if (batchOperationType.value === 'stop') {
      endpoint = '/api/containers/batch/stop'
    } else if (batchOperationType.value === 'delete') {
      endpoint = '/api/containers/batch/delete'
      if (batchForceDelete.value) {
        params.force = true
      }
    }
    
    const response = await axios.post(endpoint, selectedContainerIds.value, { params })
    
    closeBatchConfirmModal()
    batchResult.value = response.data
    
    if (response.data.success) {
      showToast(response.data.message, 'success')
    } else {
      showToast(response.data.message, 'error')
    }
    
    if (response.data.data?.failed_count > 0) {
      showBatchResultModal.value = true
    } else {
      clearSelection()
    }
    
    fetchContainers()
  } catch (err) {
    showToast(err.message || '批量操作失败', 'error')
  } finally {
    batchOperationInProgress.value = false
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

const fetchContainers = async () => {
  try {
    loading.value = true
    error.value = null
    
    const params = {
      all_containers: showAll.value,
      page: currentPage.value,
      page_size: pageSize.value
    }
    
    if (searchQuery.value && searchQuery.value.trim()) {
      params.search = searchQuery.value.trim()
    }
    
    const response = await axios.get('/api/containers', { params })
    
    if (response.data.success) {
      containers.value = response.data.data
      total.value = response.data.total
      totalPages.value = response.data.total_pages
      selectedIndex.value = -1
    } else {
      error.value = response.data.error || '获取容器列表失败'
    }
  } catch (err) {
    error.value = err.message || '获取容器列表失败'
  } finally {
    loading.value = false
  }
}

const getContainerName = (names) => {
  if (!names || names.length === 0) return 'N/A'
  return names[0].replace(/^\//, '')
}

const formatDate = (timestamp) => {
  if (!timestamp) return 'N/A'
  const date = new Date(timestamp)
  return date.toLocaleString('zh-CN')
}

const formatBytes = (bytes) => {
  if (bytes === 0 || !bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

const formatTimestamp = (timestamp) => {
  if (!timestamp) return 'N/A'
  const date = new Date(timestamp * 1000)
  return date.toLocaleString('zh-CN')
}

const getStatusClass = (state) => {
  const classes = {
    running: 'status-running',
    exited: 'status-stopped',
    paused: 'status-paused'
  }
  return classes[state] || 'status-unknown'
}

const goToPage = (page) => {
  if (page >= 1 && page <= totalPages.value) {
    currentPage.value = page
  }
}

const nextPage = () => {
  if (currentPage.value < totalPages.value) {
    currentPage.value++
    fetchContainers()
  }
}

const prevPage = () => {
  if (currentPage.value > 1) {
    currentPage.value--
    fetchContainers()
  }
}

const toggleDropdown = (containerId) => {
  if (openDropdown.value === containerId) {
    openDropdown.value = null
  } else {
    openDropdown.value = containerId
  }
}

const closeDropdowns = (event) => {
  if (openDropdown.value) {
    const dropdown = event.target.closest('.dropdown')
    if (!dropdown) {
      openDropdown.value = null
    }
  }
}

const startContainer = async (container) => {
  try {
    operationInProgress.value = container.id
    const response = await axios.post(`/api/containers/${container.id}/start`)
    if (response.data.success) {
      showToast('容器启动成功', 'success')
      fetchContainers()
    } else {
      showToast(response.data.error || '启动容器失败', 'error')
    }
  } catch (err) {
    showToast(err.message || '启动容器失败', 'error')
  } finally {
    operationInProgress.value = null
    openDropdown.value = null
  }
}

const stopContainer = async (container) => {
  try {
    operationInProgress.value = container.id
    const response = await axios.post(`/api/containers/${container.id}/stop`)
    if (response.data.success) {
      showToast('容器停止成功', 'success')
      fetchContainers()
    } else {
      showToast(response.data.error || '停止容器失败', 'error')
    }
  } catch (err) {
    showToast(err.message || '停止容器失败', 'error')
  } finally {
    operationInProgress.value = null
    openDropdown.value = null
  }
}

const restartContainer = async (container) => {
  try {
    operationInProgress.value = container.id
    const response = await axios.post(`/api/containers/${container.id}/restart`)
    if (response.data.success) {
      showToast('容器重启成功', 'success')
      fetchContainers()
    } else {
      showToast(response.data.error || '重启容器失败', 'error')
    }
  } catch (err) {
    showToast(err.message || '重启容器失败', 'error')
  } finally {
    operationInProgress.value = null
    openDropdown.value = null
  }
}

const confirmDeleteContainer = (container) => {
  currentContainer.value = container
  forceDelete.value = container.state === 'running'
  showDeleteConfirm.value = true
  openDropdown.value = null
}

const cancelDelete = () => {
  showDeleteConfirm.value = false
  currentContainer.value = null
  forceDelete.value = false
}

const executeDeleteContainer = async () => {
  if (!currentContainer.value) return
  
  try {
    operationInProgress.value = currentContainer.value.id
    const response = await axios.post(`/api/containers/${currentContainer.value.id}/delete`, null, {
      params: { force: forceDelete.value }
    })
    if (response.data.success) {
      showToast('容器删除成功', 'success')
      showDeleteConfirm.value = false
      currentContainer.value = null
      fetchContainers()
    } else {
      showToast(response.data.error || '删除容器失败', 'error')
    }
  } catch (err) {
    showToast(err.message || '删除容器失败', 'error')
  } finally {
    operationInProgress.value = null
  }
}

const viewContainerDetails = async (container) => {
  currentContainer.value = container
  openDropdown.value = null
  showDetailsModal.value = true
  loadingDetails.value = true
  containerDetails.value = null
  
  try {
    const response = await axios.get(`/api/containers/${container.id}/full-info`)
    if (response.data.success) {
      containerDetails.value = response.data.data
    } else {
      showToast('获取容器详情失败', 'error')
    }
  } catch (err) {
    showToast(err.message || '获取容器详情失败', 'error')
  } finally {
    loadingDetails.value = false
  }
}

const closeDetailsModal = () => {
  showDetailsModal.value = false
  containerDetails.value = null
  currentContainer.value = null
}

const viewImageLayers = async (container) => {
  currentContainer.value = container
  openDropdown.value = null
  showImageLayersModal.value = true
  loadingImageLayers.value = true
  imageLayersData.value = null
  
  try {
    const imageName = container.image
    const response = await axios.get(`/api/images/${encodeURIComponent(imageName)}/layers`)
    if (response.data.success) {
      imageLayersData.value = response.data.data
    } else {
      showToast('获取镜像层信息失败', 'error')
    }
  } catch (err) {
    showToast(err.message || '获取镜像层信息失败', 'error')
  } finally {
    loadingImageLayers.value = false
  }
}

const closeImageLayersModal = () => {
  showImageLayersModal.value = false
  imageLayersData.value = null
  currentContainer.value = null
}

watch(showAll, (newValue) => {
  console.log('[DEBUG] showAll changed to:', newValue)
  currentPage.value = 1
  fetchContainers()
})

let searchDebounceTimer = null
watch(searchQuery, () => {
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer)
  }
  searchDebounceTimer = setTimeout(() => {
    currentPage.value = 1
    fetchContainers()
  }, 300)
})

watch(currentPage, () => {
  if (currentPage.value > totalPages.value && totalPages.value > 0) {
    currentPage.value = totalPages.value
  }
})

const focusSearch = () => {
  if (searchInputRef.value) {
    searchInputRef.value.focus()
    searchInputRef.value.select()
  }
}

const selectUp = () => {
  if (containers.value.length === 0) return
  if (selectedIndex.value <= 0) {
    if (currentPage.value > 1) {
      prevPage()
      nextTick(() => {
        selectedIndex.value = containers.value.length - 1
      })
    } else {
      selectedIndex.value = 0
    }
  } else {
    selectedIndex.value--
  }
  scrollSelectedIntoView()
}

const selectDown = () => {
  if (containers.value.length === 0) return
  if (selectedIndex.value === -1) {
    selectedIndex.value = 0
  } else if (selectedIndex.value >= containers.value.length - 1) {
    if (currentPage.value < totalPages.value) {
      nextPage()
      nextTick(() => {
        selectedIndex.value = 0
      })
    } else {
      selectedIndex.value = containers.value.length - 1
    }
  } else {
    selectedIndex.value++
  }
  scrollSelectedIntoView()
}

const scrollSelectedIntoView = () => {
  nextTick(() => {
    const selectedRow = document.querySelector('.row-selected')
    if (selectedRow) {
      selectedRow.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    }
  })
}

const viewSelectedLogs = () => {
  if (selectedIndex.value >= 0 && selectedIndex.value < containers.value.length) {
    const container = containers.value[selectedIndex.value]
    router.push(`/containers/${container.id}`)
  }
}

const setupShortcuts = () => {
  register({
    key: 'f',
    ctrl: true,
    description: '聚焦搜索框',
    handler: focusSearch,
    allowInInput: false,
    preventDefault: true
  })
  
  register({
    key: 'r',
    ctrl: true,
    description: '刷新列表',
    handler: fetchContainers,
    allowInInput: false,
    preventDefault: true
  })
  
  register({
    key: 'ArrowUp',
    description: '向上选择容器',
    handler: selectUp,
    allowInInput: false,
    preventDefault: true
  })
  
  register({
    key: 'ArrowDown',
    description: '向下选择容器',
    handler: selectDown,
    allowInInput: false,
    preventDefault: true
  })
  
  register({
    key: 'Enter',
    description: '查看日志',
    handler: viewSelectedLogs,
    allowInInput: false,
    preventDefault: true
  })
}

onMounted(() => {
  fetchContainers()
  setupShortcuts()
  document.addEventListener('click', closeDropdowns)
})

onUnmounted(() => {
  document.removeEventListener('click', closeDropdowns)
  if (toastTimeout) {
    clearTimeout(toastTimeout)
  }
})
</script>

<style scoped>
.container-list {
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

.logo {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.logo h1 {
  font-size: 1.5rem;
  font-weight: 700;
  margin: 0;
}

.logo p {
  font-size: 0.875rem;
  color: var(--text-secondary);
  margin: 0;
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

.controls {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1.5rem;
}

.search-box {
  flex: 1;
  min-width: 250px;
}

.input {
  width: 100%;
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  font-size: 0.875rem;
}

.input:focus {
  outline: none;
  border-color: var(--primary-color);
}

.filters {
  display: flex;
  gap: 1rem;
  align-items: center;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  cursor: pointer;
}

.error-message {
  background-color: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
  padding: 1rem;
  border-radius: 0.5rem;
  margin-bottom: 1rem;
}

.loading {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.skeleton {
  height: 4rem;
  background-color: var(--bg-secondary);
  border-radius: 0.375rem;
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.table-container {
  overflow-x: auto;
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

.row-selected {
  background-color: rgba(59, 130, 246, 0.1);
}

.row-selected td {
  border-bottom-color: var(--primary-color);
}

.status-dot {
  width: 0.5rem;
  height: 0.5rem;
  border-radius: 50%;
  display: inline-block;
}

.status-running {
  background-color: var(--success-color);
}

.status-stopped {
  background-color: var(--error-color);
}

.status-paused {
  background-color: var(--warning-color);
}

.status-unknown {
  background-color: var(--text-secondary);
}

.font-medium {
  font-weight: 500;
}

.font-mono {
  font-family: 'Courier New', monospace;
  font-size: 0.75rem;
}

.text-muted {
  color: var(--text-secondary);
}

.text-right {
  text-align: right;
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

.badge-secondary {
  background-color: var(--text-secondary);
  color: white;
}

.badge-primary {
  background-color: var(--primary-color);
  color: white;
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

.btn-success {
  background-color: var(--success-color);
  color: white;
}

.btn-success:hover:not(:disabled) {
  background-color: #059669;
}

.btn-warning {
  background-color: var(--warning-color);
  color: white;
}

.btn-warning:hover:not(:disabled) {
  background-color: #d97706;
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

.action-buttons {
  display: flex;
  gap: 0.25rem;
  justify-content: flex-end;
}

.action-btn {
  min-width: 28px;
  padding: 0.25rem;
}

.empty-state {
  text-align: center;
  padding: 4rem 1rem;
  color: var(--text-secondary);
}

.table-footer {
  margin-top: 1rem;
  font-size: 0.875rem;
  color: var(--text-secondary);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 1rem;
}

.pagination {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.pagination-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.375rem 0.75rem;
  border-radius: 0.375rem;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  border: 1px solid var(--border-color);
  background-color: var(--bg-primary);
  color: var(--text-primary);
  transition: all 0.2s;
}

.pagination-btn:hover:not(:disabled) {
  background-color: var(--bg-secondary);
  border-color: var(--primary-color);
}

.pagination-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.pagination-info {
  font-size: 0.875rem;
  color: var(--text-secondary);
  padding: 0 0.5rem;
}

.dropdown {
  position: relative;
  display: inline-block;
}

.dropdown-menu {
  position: absolute;
  right: 0;
  top: 100%;
  margin-top: 0.25rem;
  min-width: 160px;
  background-color: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  z-index: 1000;
  padding: 0.25rem 0;
}

.dropdown-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
  padding: 0.5rem 1rem;
  text-align: left;
  font-size: 0.875rem;
  color: var(--text-primary);
  background: none;
  border: none;
  cursor: pointer;
  transition: background-color 0.15s;
}

.dropdown-item:hover:not(:disabled) {
  background-color: var(--bg-secondary);
}

.dropdown-item:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.dropdown-item.dropdown-danger {
  color: var(--error-color);
}

.dropdown-item.dropdown-danger:hover:not(:disabled) {
  background-color: rgba(239, 68, 68, 0.1);
}

.dropdown-icon {
  flex-shrink: 0;
}

.dropdown-divider {
  height: 1px;
  background-color: var(--border-color);
  margin: 0.25rem 0;
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

.modal-large {
  width: 900px;
}

.modal-small {
  width: 400px;
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

.modal-scrollable {
  max-height: 60vh;
  overflow-y: auto;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  padding: 1rem 1.5rem;
  border-top: 1px solid var(--border-color);
}

.loading-details {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 2rem;
  color: var(--text-secondary);
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

.details-section {
  margin-bottom: 1.5rem;
}

.details-section:last-child {
  margin-bottom: 0;
}

.section-title {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-secondary);
  margin: 0 0 0.75rem 0;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border-color);
}

.details-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 0.75rem;
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
  font-weight: 500;
}

.code-block {
  background-color: var(--bg-secondary);
  border-radius: 0.375rem;
  padding: 0.75rem;
  overflow-x: auto;
}

.code-block pre {
  margin: 0;
  font-family: 'Courier New', monospace;
  font-size: 0.875rem;
  white-space: pre-wrap;
  word-break: break-all;
}

.details-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}

.details-table th {
  text-align: left;
  padding: 0.5rem 0.75rem;
  font-weight: 600;
  color: var(--text-secondary);
  border-bottom: 2px solid var(--border-color);
}

.details-table td {
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--border-color);
}

.details-table tr:last-child td {
  border-bottom: none;
}

.mt-2 {
  margin-top: 0.5rem;
}

.text-success {
  color: var(--success-color);
}

.text-warning {
  color: var(--warning-color);
}

.ml-2 {
  margin-left: 0.5rem;
}

.delete-warning {
  font-size: 1rem;
  margin-bottom: 0.5rem;
}

.delete-warning strong {
  color: var(--error-color);
}

.delete-info {
  font-size: 0.875rem;
  color: var(--text-secondary);
}

.layers-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.layer-item {
  background-color: var(--bg-secondary);
  border-radius: 0.5rem;
  padding: 1rem;
  border: 1px solid var(--border-color);
}

.layer-item.layer-top {
  border-color: var(--primary-color);
}

.layer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.layer-index {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.layer-number {
  font-weight: 600;
  color: var(--primary-color);
}

.layer-tag {
  font-size: 0.7rem;
}

.layer-size {
  font-weight: 500;
  color: var(--text-secondary);
}

.layer-command {
  margin-bottom: 0.5rem;
}

.layer-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.layer-time {
  text-align: right;
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

.batch-actions-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.5rem;
  background-color: var(--primary-color);
  border-radius: 0.5rem;
  margin-bottom: 1rem;
}

.batch-actions-info {
  color: white;
  font-weight: 500;
}

.batch-actions-info strong {
  font-size: 1.1rem;
}

.batch-actions-buttons {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.batch-actions-buttons .btn {
  background-color: rgba(255, 255, 255, 0.2);
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.3);
}

.batch-actions-buttons .btn:hover:not(:disabled) {
  background-color: rgba(255, 255, 255, 0.3);
}

.batch-actions-buttons .btn:disabled {
  opacity: 0.5;
}

.batch-actions-buttons .btn.btn-success:hover:not(:disabled) {
  background-color: var(--success-color);
  border-color: var(--success-color);
}

.batch-actions-buttons .btn.btn-warning:hover:not(:disabled) {
  background-color: var(--warning-color);
  border-color: var(--warning-color);
}

.batch-actions-buttons .btn.btn-danger:hover:not(:disabled) {
  background-color: var(--error-color);
  border-color: var(--error-color);
}

.row-checkbox-selected {
  background-color: rgba(59, 130, 246, 0.05);
}

.selected-containers-list {
  max-height: 200px;
  overflow-y: auto;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  margin-top: 0.5rem;
  background-color: var(--bg-secondary);
}

.selected-container-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--border-color);
}

.selected-container-item:last-child {
  border-bottom: none;
}

.container-name {
  font-weight: 500;
  color: var(--text-primary);
}

.container-status {
  margin-left: 0.5rem;
}

.batch-result-summary {
  display: flex;
  gap: 2rem;
  margin-bottom: 1.5rem;
}

.result-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
  padding: 1rem 2rem;
  border-radius: 0.5rem;
  background-color: var(--bg-secondary);
}

.result-item.success {
  border-left: 4px solid var(--success-color);
}

.result-item.failed {
  border-left: 4px solid var(--error-color);
}

.result-label {
  font-size: 0.875rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.result-count {
  font-size: 2rem;
  font-weight: 700;
  color: var(--text-primary);
}

.result-item.success .result-count {
  color: var(--success-color);
}

.result-item.failed .result-count {
  color: var(--error-color);
}

.failed-list-section {
  margin-top: 1rem;
}

.failed-list {
  max-height: 300px;
  overflow-y: auto;
}

.failed-item {
  padding: 0.75rem;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  margin-bottom: 0.5rem;
  background-color: #fef2f2;
  border-left: 3px solid var(--error-color);
}

.failed-container-id {
  font-weight: 600;
  color: var(--error-color);
  margin-bottom: 0.25rem;
}

.failed-error {
  font-size: 0.875rem;
  color: var(--text-secondary);
  word-break: break-all;
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

  .stats-summary {
    grid-template-columns: repeat(2, 1fr);
  }

  .container-stats-grid {
    grid-template-columns: 1fr;
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

  .details-grid {
    grid-template-columns: 1fr;
  }

  .action-buttons {
    flex-wrap: wrap;
  }

  .batch-actions-bar {
    flex-direction: column;
    gap: 1rem;
    align-items: flex-start;
  }

  .batch-actions-buttons {
    width: 100%;
    justify-content: flex-start;
  }

  .batch-result-summary {
    flex-direction: column;
    gap: 1rem;
  }

  .result-item {
    width: 100%;
  }
}
</style>
