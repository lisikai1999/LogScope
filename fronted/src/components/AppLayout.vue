<template>
  <div class="app-layout">
    <aside class="sidebar" :class="{ 'sidebar-collapsed': isCollapsed }">
      <div class="sidebar-header">
        <div class="logo">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
          </svg>
          <span v-if="!isCollapsed" class="logo-text">LogScope</span>
        </div>
        <button class="collapse-btn" @click="isCollapsed = !isCollapsed" :title="isCollapsed ? '展开侧边栏' : '收起侧边栏'">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline :points="isCollapsed ? '15 18 9 12 15 6' : '9 18 15 12 9 6'"></polyline>
          </svg>
        </button>
      </div>

      <nav class="sidebar-nav">
        <ul class="nav-menu">
          <li class="nav-item">
            <router-link to="/" class="nav-link" :class="{ 'nav-link-active': $route.path === '/' }">
              <svg class="nav-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="3" y="3" width="7" height="7"></rect>
                <rect x="14" y="3" width="7" height="7"></rect>
                <rect x="3" y="14" width="7" height="7"></rect>
                <rect x="14" y="14" width="7" height="7"></rect>
              </svg>
              <span v-if="!isCollapsed" class="nav-text">容器管理</span>
            </router-link>
          </li>

          <li class="nav-item">
            <router-link to="/dashboard" class="nav-link" :class="{ 'nav-link-active': $route.path === '/dashboard' }">
              <svg class="nav-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                <line x1="3" y1="9" x2="21" y2="9"></line>
                <line x1="9" y1="21" x2="9" y2="9"></line>
              </svg>
              <span v-if="!isCollapsed" class="nav-text">仪表盘</span>
            </router-link>
          </li>

          <li class="nav-item">
            <router-link to="/multi-logs" class="nav-link" :class="{ 'nav-link-active': $route.path === '/multi-logs' }">
              <svg class="nav-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
              </svg>
              <span v-if="!isCollapsed" class="nav-text">日志聚合</span>
            </router-link>
          </li>

          <li v-if="isAdmin" class="nav-item nav-item-group">
            <button class="nav-link nav-toggle" @click="toggleImageMenu" :class="{ 'nav-link-active': isImageMenuActive }">
              <svg class="nav-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M20 7h-9l-2-2H4a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2z"></path>
                <circle cx="18" cy="13" r="2"></circle>
                <path d="M10 13h4"></path>
                <path d="M6 13h2"></path>
              </svg>
              <span v-if="!isCollapsed" class="nav-text">镜像管理</span>
              <svg v-if="!isCollapsed" class="nav-arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" :class="{ 'rotated': isImageMenuOpen }">
                <polyline points="6 9 12 15 18 9"></polyline>
              </svg>
            </button>
            <Transition name="slide">
              <ul v-if="!isCollapsed && isImageMenuOpen" class="nav-submenu">
                <li class="nav-subitem">
                  <router-link to="/images" class="nav-sublink" :class="{ 'nav-sublink-active': $route.path === '/images' }">
                    镜像列表
                  </router-link>
                </li>
                <li class="nav-subitem">
                  <router-link to="/registries" class="nav-sublink" :class="{ 'nav-sublink-active': $route.path === '/registries' }">
                    仓库配置
                  </router-link>
                </li>
                <li class="nav-subitem">
                  <router-link to="/scans" class="nav-sublink" :class="{ 'nav-sublink-active': $route.path === '/scans' }">
                    安全扫描
                  </router-link>
                </li>
                <li class="nav-subitem">
                  <router-link to="/builds" class="nav-sublink" :class="{ 'nav-sublink-active': $route.path === '/builds' }">
                    镜像构建
                  </router-link>
                </li>
              </ul>
            </Transition>
          </li>

          <li v-if="isAdmin" class="nav-item">
            <router-link to="/networks" class="nav-link" :class="{ 'nav-link-active': $route.path === '/networks' }">
              <svg class="nav-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="5" r="3"></circle>
                <circle cx="6" cy="12" r="3"></circle>
                <circle cx="18" cy="12" r="3"></circle>
                <circle cx="12" cy="19" r="3"></circle>
                <line x1="9.5" y1="7" x2="8.5" y2="9.5"></line>
                <line x1="14.5" y1="7" x2="15.5" y2="9.5"></line>
                <line x1="8.5" y1="14.5" x2="9.5" y2="17"></line>
                <line x1="15.5" y1="14.5" x2="14.5" y2="17"></line>
              </svg>
              <span v-if="!isCollapsed" class="nav-text">网络管理</span>
            </router-link>
          </li>

          <li v-if="isAdmin" class="nav-item">
            <router-link to="/storage" class="nav-link" :class="{ 'nav-link-active': $route.path === '/storage' }">
              <svg class="nav-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="2" y="2" width="20" height="8" rx="2" ry="2"></rect>
                <rect x="2" y="14" width="20" height="8" rx="2" ry="2"></rect>
                <line x1="6" y1="6" x2="6.01" y2="6"></line>
                <line x1="6" y1="18" x2="6.01" y2="18"></line>
              </svg>
              <span v-if="!isCollapsed" class="nav-text">存储管理</span>
            </router-link>
          </li>

          <li v-if="isAdmin" class="nav-item">
            <router-link to="/hosts" class="nav-link" :class="{ 'nav-link-active': $route.path === '/hosts' }">
              <svg class="nav-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect>
                <line x1="8" y1="21" x2="16" y2="21"></line>
                <line x1="12" y1="17" x2="12" y2="21"></line>
              </svg>
              <span v-if="!isCollapsed" class="nav-text">主机管理</span>
            </router-link>
          </li>

          <li v-if="isAdmin" class="nav-item">
            <router-link to="/users" class="nav-link" :class="{ 'nav-link-active': $route.path === '/users' }">
              <svg class="nav-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
                <circle cx="9" cy="7" r="4"></circle>
                <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
                <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
              </svg>
              <span v-if="!isCollapsed" class="nav-text">用户管理</span>
            </router-link>
          </li>

          <li v-if="isAdmin" class="nav-item">
            <router-link to="/audit-logs" class="nav-link" :class="{ 'nav-link-active': $route.path === '/audit-logs' }">
              <svg class="nav-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
                <line x1="16" y1="13" x2="8" y2="13"></line>
                <line x1="16" y1="17" x2="8" y2="17"></line>
                <polyline points="10 9 9 9 8 9"></polyline>
              </svg>
              <span v-if="!isCollapsed" class="nav-text">操作审计</span>
            </router-link>
          </li>
        </ul>
      </nav>

      <div class="sidebar-footer" v-if="!isCollapsed">
        <div class="version-info">
          <span class="version-label">LogScope</span>
          <span class="version-number">v1.0.0</span>
        </div>
      </div>
    </aside>

    <div class="main-wrapper">
      <header class="top-header">
        <div class="header-left">
          <h2 class="page-title">{{ pageTitle }}</h2>
        </div>
        <div class="header-right">
          <button class="refresh-btn" @click="$emit('refresh')" title="刷新">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="23 4 23 10 17 10"></polyline>
              <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
            </svg>
          </button>
          <div class="user-menu">
            <div class="user-info">
              <div class="user-avatar" :class="{ 'admin-avatar': isAdmin }">
                {{ userInitial }}
              </div>
              <div class="user-details">
                <span class="user-name">{{ currentUser?.username }}</span>
                <span class="user-role" :class="isAdmin ? 'role-admin' : 'role-user'">
                  {{ isAdmin ? '管理员' : '普通用户' }}
                </span>
              </div>
            </div>
            <button class="logout-btn" @click="$emit('logout')" title="退出登录">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                <polyline points="16 17 21 12 16 7"></polyline>
                <line x1="21" y1="12" x2="9" y2="12"></line>
              </svg>
            </button>
          </div>
        </div>
      </header>

      <main class="main-content">
        <slot></slot>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  currentUser: {
    type: Object,
    default: null
  },
  pageTitle: {
    type: String,
    default: '容器管理'
  }
})

defineEmits(['refresh', 'logout'])

const isCollapsed = ref(false)
const isImageMenuOpen = ref(true)

const isAdmin = computed(() => {
  return props.currentUser?.role === 'admin'
})

const userInitial = computed(() => {
  return props.currentUser?.username?.charAt(0).toUpperCase() || 'U'
})

const isImageMenuActive = computed(() => {
  const imagePaths = ['/images', '/registries', '/scans', '/builds']
  return imagePaths.some(path => window.location.pathname.startsWith(path))
})

const toggleImageMenu = () => {
  isImageMenuOpen.value = !isImageMenuOpen.value
}
</script>

<style scoped>
.app-layout {
  display: flex;
  min-height: 100vh;
  background-color: var(--bg-secondary);
}

.sidebar {
  width: 240px;
  background-color: var(--sidebar-bg, #1e293b);
  color: var(--sidebar-text, #e2e8f0);
  display: flex;
  flex-direction: column;
  transition: width 0.3s ease;
  position: fixed;
  top: 0;
  left: 0;
  height: 100vh;
  z-index: 100;
  border-right: 1px solid var(--sidebar-border, #334155);
}

.sidebar-collapsed {
  width: 64px;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem;
  border-bottom: 1px solid var(--sidebar-border, #334155);
}

.logo {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  color: var(--sidebar-primary, #60a5fa);
}

.logo-text {
  font-size: 1.125rem;
  font-weight: 700;
  letter-spacing: 0.5px;
}

.collapse-btn {
  background: transparent;
  border: none;
  color: var(--sidebar-text, #e2e8f0);
  cursor: pointer;
  padding: 0.25rem;
  border-radius: 0.375rem;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background-color 0.2s;
}

.collapse-btn:hover {
  background-color: var(--sidebar-hover, #334155);
}

.sidebar-nav {
  flex: 1;
  overflow-y: auto;
  padding: 0.75rem 0;
}

.nav-menu {
  list-style: none;
  padding: 0;
  margin: 0;
}

.nav-item {
  margin: 0.125rem 0.5rem;
}

.nav-link {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.625rem 0.75rem;
  color: var(--sidebar-text, #e2e8f0);
  text-decoration: none;
  border-radius: 0.5rem;
  transition: all 0.2s;
  cursor: pointer;
  border: none;
  background: transparent;
  width: 100%;
  font-size: 0.875rem;
}

.nav-link:hover {
  background-color: var(--sidebar-hover, #334155);
  color: var(--sidebar-primary, #60a5fa);
}

.nav-link-active {
  background-color: var(--sidebar-active-bg, #334155);
  color: var(--sidebar-primary, #60a5fa);
  border-left: 3px solid var(--sidebar-primary, #60a5fa);
}

.nav-icon {
  flex-shrink: 0;
}

.nav-text {
  flex: 1;
}

.nav-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.nav-arrow {
  transition: transform 0.3s ease;
}

.nav-arrow.rotated {
  transform: rotate(180deg);
}

.nav-submenu {
  list-style: none;
  padding: 0.25rem 0 0.25rem 2rem;
  margin: 0;
}

.nav-subitem {
  margin: 0.125rem 0;
}

.nav-sublink {
  display: block;
  padding: 0.5rem 0.75rem;
  color: var(--sidebar-secondary, #94a3b8);
  text-decoration: none;
  border-radius: 0.375rem;
  font-size: 0.8125rem;
  transition: all 0.2s;
}

.nav-sublink:hover {
  color: var(--sidebar-primary, #60a5fa);
  background-color: var(--sidebar-hover, #334155);
}

.nav-sublink-active {
  color: var(--sidebar-primary, #60a5fa);
  background-color: rgba(96, 165, 250, 0.1);
}

.slide-enter-active,
.slide-leave-active {
  transition: all 0.3s ease;
  overflow: hidden;
}

.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  max-height: 0;
}

.slide-enter-to,
.slide-leave-from {
  max-height: 200px;
  opacity: 1;
}

.sidebar-footer {
  padding: 1rem;
  border-top: 1px solid var(--sidebar-border, #334155);
}

.version-info {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
}

.version-label {
  font-size: 0.75rem;
  color: var(--sidebar-secondary, #94a3b8);
}

.version-number {
  font-size: 0.6875rem;
  color: var(--sidebar-primary, #60a5fa);
  font-weight: 600;
}

.main-wrapper {
  flex: 1;
  margin-left: 240px;
  display: flex;
  flex-direction: column;
  transition: margin-left 0.3s ease;
}

.sidebar-collapsed + .main-wrapper {
  margin-left: 64px;
}

.top-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.875rem 1.5rem;
  background-color: var(--bg-primary, #ffffff);
  border-bottom: 1px solid var(--border-color, #e2e8f0);
  position: sticky;
  top: 0;
  z-index: 50;
}

.page-title {
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--text-primary, #1e293b);
  margin: 0;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.refresh-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0.5rem;
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 0.5rem;
  background-color: var(--bg-primary, #ffffff);
  color: var(--text-secondary, #64748b);
  cursor: pointer;
  transition: all 0.2s;
}

.refresh-btn:hover {
  background-color: var(--bg-secondary, #f8fafc);
  color: var(--primary-color, #3b82f6);
  border-color: var(--primary-color, #3b82f6);
}

.user-menu {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem 0.75rem;
  background-color: var(--bg-secondary, #f8fafc);
  border-radius: 0.5rem;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.user-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background-color: var(--primary-color, #3b82f6);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.875rem;
  font-weight: 600;
}

.admin-avatar {
  background: linear-gradient(135deg, #8b5cf6, #6366f1);
}

.user-details {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
}

.user-name {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-primary, #1e293b);
}

.user-role {
  font-size: 0.6875rem;
  padding: 0.125rem 0.5rem;
  border-radius: 9999px;
  font-weight: 500;
}

.role-admin {
  background-color: rgba(139, 92, 246, 0.1);
  color: #8b5cf6;
}

.role-user {
  background-color: rgba(100, 116, 139, 0.1);
  color: #64748b;
}

.logout-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0.5rem;
  border: none;
  border-radius: 0.375rem;
  background-color: transparent;
  color: var(--text-secondary, #64748b);
  cursor: pointer;
  transition: all 0.2s;
}

.logout-btn:hover {
  background-color: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}

.main-content {
  flex: 1;
  padding: 1.5rem;
}
</style>
