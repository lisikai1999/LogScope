import { createRouter, createWebHistory } from 'vue-router'
import ContainerList from '../views/ContainerList.vue'
import LogViewer from '../views/LogViewer.vue'
import MultiLogViewer from '../views/MultiLogViewer.vue'
import Dashboard from '../views/Dashboard.vue'
import AlertRules from '../views/AlertRules.vue'

const routes = [
  {
    path: '/',
    name: 'ContainerList',
    component: ContainerList
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: Dashboard
  },
  {
    path: '/alert-rules',
    name: 'AlertRules',
    component: AlertRules
  },
  {
    path: '/containers/:id',
    name: 'LogViewer',
    component: LogViewer
  },
  {
    path: '/multi-logs',
    name: 'MultiLogViewer',
    component: MultiLogViewer
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router