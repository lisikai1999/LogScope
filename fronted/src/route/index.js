import { createRouter, createWebHistory } from 'vue-router'
import ContainerList from '../views/ContainerList.vue'
import LogViewer from '../views/LogViewer.vue'
import MultiLogViewer from '../views/MultiLogViewer.vue'
import Dashboard from '../views/Dashboard.vue'
import Login from '../views/Login.vue'
import UserManagement from '../views/UserManagement.vue'


const routes = [
  {
    path: '/login',
    name: 'Login',
    component: Login,
    meta: { requiresAuth: false }
  },
  {
    path: '/',
    name: 'ContainerList',
    component: ContainerList,
    meta: { requiresAuth: true }
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: Dashboard,
    meta: { requiresAuth: true }
  },
  {
    path: '/users',
    name: 'UserManagement',
    component: UserManagement,
    meta: { requiresAuth: true, requiresAdmin: true }
  },
  {
    path: '/containers/:id',
    name: 'LogViewer',
    component: LogViewer,
    meta: { requiresAuth: true }
  },
  {
    path: '/multi-logs',
    name: 'MultiLogViewer',
    component: MultiLogViewer,
    meta: { requiresAuth: true }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})


router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('logscope_token')
  const user = JSON.parse(localStorage.getItem('logscope_user') || 'null')
  
  const isAuthenticated = !!token && !!user
  const isAdmin = user?.role === 'admin'
  
  if (to.meta.requiresAuth === false) {
    if (isAuthenticated) {
      next('/')
    } else {
      next()
    }
  } else {
    if (isAuthenticated) {
      if (to.meta.requiresAdmin && !isAdmin) {
        next('/')
      } else {
        next()
      }
    } else {
      next({
        name: 'Login',
        query: { redirect: to.fullPath }
      })
    }
  }
})


export default router
