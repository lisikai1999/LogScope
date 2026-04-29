
import { ref } from 'vue'
import axios from 'axios'


const globalLoading = ref(false)
const pendingRequests = new Map()


function createRequestId(config) {
  const method = config.method?.toUpperCase() || 'GET'
  const url = config.url || ''
  const params = config.params ? JSON.stringify(config.params) : ''
  const data = config.data ? JSON.stringify(config.data) : ''
  return `${method}:${url}:${params}:${data}`
}


function updateGlobalLoading(increment = false) {
  if (increment) {
    globalLoading.value = true
  } else {
    globalLoading.value = pendingRequests.size > 0
  }
}


function getErrorMessage(error) {
  if (error.response) {
    const status = error.response.status
    const data = error.response.data
    
    switch (status) {
      case 400:
        return data?.message || data?.error || '请求参数无效'
      case 401:
        return '未授权，请重新登录'
      case 403:
        return data?.message || '权限不足，无法执行此操作'
      case 404:
        return data?.message || '请求的资源不存在'
      case 409:
        return data?.message || '资源冲突'
      case 422:
        return data?.message || '请求验证失败'
      case 429:
        return '请求过于频繁，请稍后再试'
      case 500:
        return data?.message || '服务器内部错误'
      case 502:
        return '网关错误'
      case 503:
        return '服务不可用'
      case 504:
        return '网关超时'
      default:
        return data?.message || `请求失败 (${status})`
    }
  } else if (error.request) {
    return '网络错误，请检查网络连接'
  } else {
    return error.message || '请求失败'
  }
}


function createApiResponse(response) {
  return {
    success: response.data?.success !== false,
    data: response.data?.data ?? response.data,
    message: response.data?.message || '操作成功',
    status: response.status
  }
}


function createApiError(error) {
  const status = error.response?.status
  const message = getErrorMessage(error)
  
  return {
    success: false,
    data: null,
    message,
    status,
    error,
    isNetworkError: !error.response,
    isClientError: status && status >= 400 && status < 500,
    isServerError: status && status >= 500
  }
}


async function request(method, url, data = null, config = {}) {
  const { showLoading = false, ...axiosConfig } = config
  const requestId = createRequestId({ method, url, params: axiosConfig.params, data })
  
  try {
    if (showLoading) {
      pendingRequests.set(requestId, true)
      updateGlobalLoading(true)
    }
    
    let response
    const methodLower = method.toLowerCase()
    
    if (methodLower === 'get' || methodLower === 'delete') {
      response = await axios[methodLower](url, { params: data, ...axiosConfig })
    } else {
      response = await axios[methodLower](url, data, axiosConfig)
    }
    
    return createApiResponse(response)
  } catch (error) {
    return createApiError(error)
  } finally {
    if (showLoading) {
      pendingRequests.delete(requestId)
      updateGlobalLoading()
    }
  }
}


function get(url, params = null, config = {}) {
  return request('GET', url, params, config)
}

function post(url, data = null, config = {}) {
  return request('POST', url, data, config)
}

function put(url, data = null, config = {}) {
  return request('PUT', url, data, config)
}

function del(url, params = null, config = {}) {
  return request('DELETE', url, params, config)
}


const containerApi = {
  async getContainers(params = {}) {
    return get('/api/containers', params)
  },
  
  async getContainerInfo(containerId) {
    return get(`/api/containers/${containerId}/info`)
  },
  
  async getContainerFullInfo(containerId) {
    return get(`/api/containers/${containerId}/full-info`)
  },
  
  async getContainerStats(containerId) {
    return get(`/api/containers/${containerId}/stats`)
  },
  
  async getAllContainersStats(params = {}) {
    return get('/api/containers/stats', params)
  },
  
  async startContainer(containerId) {
    return post(`/api/containers/${containerId}/start`)
  },
  
  async stopContainer(containerId) {
    return post(`/api/containers/${containerId}/stop`)
  },
  
  async restartContainer(containerId) {
    return post(`/api/containers/${containerId}/restart`)
  },
  
  async deleteContainer(containerId, params = {}) {
    return post(`/api/containers/${containerId}/delete`, null, { params })
  },
  
  async bulkStartContainers(containerIds, params = {}) {
    return post('/api/containers/bulk-start', containerIds, { params })
  },
  
  async bulkStopContainers(containerIds, params = {}) {
    return post('/api/containers/bulk-stop', containerIds, { params })
  },
  
  async bulkRestartContainers(containerIds, params = {}) {
    return post('/api/containers/bulk-restart', containerIds, { params })
  },
  
  async getContainerLogs(containerId, params = {}) {
    return get(`/api/containers/${containerId}/logs`, params)
  },
  
  async getContainerLogsPaginated(containerId, params = {}) {
    return get(`/api/containers/${containerId}/logs/paginated`, params)
  },
  
  async searchLogs(containerId, params = {}) {
    return get(`/api/containers/${containerId}/logs/search`, params)
  }
}


const imageApi = {
  async getImageLayers(imageName) {
    return get(`/api/images/${encodeURIComponent(imageName)}/layers`)
  },
  
  async getImageInfo(imageName) {
    return get(`/api/images/${encodeURIComponent(imageName)}/info`)
  }
}


const dashboardApi = {
  async getStats(params = {}) {
    return get('/api/dashboard/stats', params)
  },
  
  async getRuntimeStats(params = {}) {
    return get('/api/dashboard/runtime', params)
  }
}


const authApi = {
  async login(username, password) {
    return post('/api/auth/login', { username, password })
  },
  
  async getCurrentUser() {
    return get('/api/auth/me')
  },
  
  async changePassword(oldPassword, newPassword) {
    return post('/api/auth/change-password', {
      old_password: oldPassword,
      new_password: newPassword
    })
  }
}


const auditLogApi = {
  async getRetention() {
    return get('/api/audit/retention')
  },
  
  async updateRetention(days) {
    return put('/api/audit/retention', { retention_days: days })
  },
  
  async getLogs(params = {}) {
    return get('/api/audit/logs', params)
  },
  
  async cleanup() {
    return post('/api/audit/cleanup')
  }
}


const userManagementApi = {
  async getUsers() {
    return get('/api/users')
  },
  
  async updateUser(userId, data) {
    return put(`/api/users/${userId}`, data)
  },
  
  async createUser(data) {
    return post('/api/users', data)
  },
  
  async deleteUser(userId) {
    return del(`/api/users/${userId}`)
  },
  
  async getUserPermissions(userId) {
    return get(`/api/users/${userId}/permissions`)
  },
  
  async updateUserPermissions(userId, permissions) {
    return put(`/api/users/${userId}/permissions`, permissions)
  },
  
  async addUserPermission(userId, permission) {
    return post(`/api/users/${userId}/permissions`, permission)
  },
  
  async deleteUserPermission(userId, permissionId) {
    return del(`/api/users/${userId}/permissions/${permissionId}`)
  }
}


const hostApi = {
  async getHosts() {
    return get('/api/hosts')
  },
  
  async getHost(hostId) {
    return get(`/api/hosts/${hostId}`)
  },
  
  async createHost(data) {
    return post('/api/hosts', data)
  },
  
  async updateHost(hostId, data) {
    return put(`/api/hosts/${hostId}`, data)
  },
  
  async deleteHost(hostId) {
    return del(`/api/hosts/${hostId}`)
  },
  
  async testConnection(hostId) {
    return post(`/api/hosts/${hostId}/test`)
  },
  
  async getStatuses() {
    return get('/api/hosts/status')
  },
  
  async getAllContainers(params = {}) {
    return get('/api/hosts/containers', params)
  },
  
  async batchStartContainers(containersWithHosts) {
    return post('/api/hosts/containers/batch/start', { containers: containersWithHosts })
  },
  
  async batchStopContainers(containersWithHosts) {
    return post('/api/hosts/containers/batch/stop', { containers: containersWithHosts })
  },
  
  async batchDeleteContainers(containersWithHosts, force = false) {
    return post('/api/hosts/containers/batch/delete', { containers: containersWithHosts }, { params: { force } })
  }
}


export {
  globalLoading,
  getErrorMessage,
  createApiResponse,
  createApiError,
  request,
  get,
  post,
  put,
  del,
  containerApi,
  imageApi,
  dashboardApi,
  authApi,
  auditLogApi,
  userManagementApi,
  hostApi
}

export default {
  globalLoading,
  getErrorMessage,
  request,
  get,
  post,
  put,
  del,
  containerApi,
  imageApi,
  dashboardApi,
  authApi,
  auditLogApi,
  userManagementApi,
  hostApi
}
