import { ref, computed, watch } from 'vue'
import axios from 'axios'


const token = ref(localStorage.getItem('logscope_token') || null)
const user = ref(JSON.parse(localStorage.getItem('logscope_user') || 'null'))
const permissions = ref(JSON.parse(localStorage.getItem('logscope_permissions') || '[]'))


axios.interceptors.request.use(
  (config) => {
    if (token.value) {
      config.headers.Authorization = `Bearer ${token.value}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)


axios.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      token.value = null
      user.value = null
      permissions.value = []
      localStorage.removeItem('logscope_token')
      localStorage.removeItem('logscope_user')
      localStorage.removeItem('logscope_permissions')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)


export function useAuth() {
  const isAuthenticated = computed(() => !!token.value && !!user.value)
  const isAdmin = computed(() => user.value?.role === 'admin')
  const currentUser = computed(() => user.value)
  const currentToken = computed(() => token.value)
  const userPermissions = computed(() => permissions.value)
  

  const hasContainerPermission = (containerId, requireWrite = false) => {
    if (isAdmin.value) return true
    
    const perm = permissions.value.find(p => p.container_id === containerId)
    if (!perm) return false
    
    if (requireWrite) {
      return perm.permission_level === 'read_write'
    }
    return true
  }
  

  const canReadContainer = (containerId) => {
    return hasContainerPermission(containerId, false)
  }
  

  const canWriteContainer = (containerId) => {
    return hasContainerPermission(containerId, true)
  }
  

  const login = async (username, password) => {
    try {
      const response = await axios.post('/api/auth/login', {
        username,
        password
      })
      
      if (response.data.access_token) {
        token.value = response.data.access_token
        localStorage.setItem('logscope_token', response.data.access_token)
        
        const meResponse = await axios.get('/api/auth/me')
        if (meResponse.data) {
          user.value = meResponse.data
          permissions.value = meResponse.data.permissions || []
          localStorage.setItem('logscope_user', JSON.stringify(meResponse.data))
          localStorage.setItem('logscope_permissions', JSON.stringify(meResponse.data.permissions || []))
        }
        
        return { success: true }
      }
      
      return { success: false, message: '登录失败' }
    } catch (error) {
      return {
        success: false,
        message: error.response?.data?.message || '登录失败'
      }
    }
  }
  

  const logout = () => {
    token.value = null
    user.value = null
    permissions.value = []
    localStorage.removeItem('logscope_token')
    localStorage.removeItem('logscope_user')
    localStorage.removeItem('logscope_permissions')
    window.location.href = '/login'
  }
  

  const refreshUserInfo = async () => {
    if (!token.value) return false
    
    try {
      const response = await axios.get('/api/auth/me')
      if (response.data) {
        user.value = response.data
        permissions.value = response.data.permissions || []
        localStorage.setItem('logscope_user', JSON.stringify(response.data))
        localStorage.setItem('logscope_permissions', JSON.stringify(response.data.permissions || []))
        return true
      }
      return false
    } catch (error) {
      return false
    }
  }
  

  const changePassword = async (oldPassword, newPassword) => {
    try {
      const response = await axios.post('/api/auth/change-password', {
        old_password: oldPassword,
        new_password: newPassword
      })
      return response.data
    } catch (error) {
      throw error
    }
  }
  

  return {
    isAuthenticated,
    isAdmin,
    currentUser,
    currentToken,
    userPermissions,
    login,
    logout,
    refreshUserInfo,
    changePassword,
    hasContainerPermission,
    canReadContainer,
    canWriteContainer
  }
}
