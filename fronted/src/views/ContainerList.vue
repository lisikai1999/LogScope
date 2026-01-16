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
              <p>日志查看工具</p>
            </div>
          </div>
          <button class="btn btn-outline" @click="fetchContainers">
            刷新
          </button>
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
                  @change="fetchContainers"
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

          <!-- Container Table -->
          <div v-else class="table-container">
            <table class="table">
              <thead>
                <tr>
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
                <tr v-if="filteredContainers.length === 0">
                  <td colspan="7" class="empty-state">
                    {{ searchQuery ? '没有找到匹配的容器' : '暂无容器' }}
                  </td>
                </tr>
                <tr v-for="container in filteredContainers" :key="container.id">
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
                  <td class="text-muted">{{ container.created }}</td>
                  <td class="text-right">
                    <router-link
                      :to="`/containers/${container.id}`"
                      class="btn btn-ghost btn-sm"
                    >
                      查看日志
                    </router-link>
                  </td>
                </tr>
              </tbody>
            </table>
            <div class="table-footer">
              共 {{ filteredContainers.length }} 个容器
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

const containers = ref([])
const loading = ref(true)
const error = ref(null)
const searchQuery = ref('')
const showAll = ref(false)

const filteredContainers = computed(() => {
  const query = searchQuery.value.toLowerCase()
  return containers.value.filter(container => {
    const name = getContainerName(container.names).toLowerCase()
    return (
      name.includes(query) ||
      container.image.toLowerCase().includes(query) ||
      container.id.toLowerCase().includes(query)
    )
  })
})

const fetchContainers = async () => {
  try {
    loading.value = true
    error.value = null
    const response = await axios.get('/api/containers', {
      params: { all: showAll.value }
    })
    if (response.data.success) {
      containers.value = response.data.data
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
  return new Date(timestamp * 1000).toLocaleString('zh-CN')
}

const getStatusClass = (state) => {
  const classes = {
    running: 'status-running',
    exited: 'status-stopped',
    paused: 'status-paused'
  }
  return classes[state] || 'status-unknown'
}

onMounted(() => {
  fetchContainers()
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

.btn-outline {
  border: 1px solid var(--border-color);
}

.btn-outline:hover {
  background-color: var(--bg-secondary);
}

.btn-ghost {
  background-color: transparent;
}

.btn-ghost:hover {
  background-color: var(--bg-secondary);
}

.btn-sm {
  padding: 0.25rem 0.5rem;
  font-size: 0.75rem;
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
}
</style>
