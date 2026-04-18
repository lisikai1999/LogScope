import { createRouter, createWebHistory } from 'vue-router'
import ContainerList from '../views/ContainerList.vue'
import LogViewer from '../views/LogViewer.vue'
import MultiLogViewer from '../views/MultiLogViewer.vue'
import Dashboard from '../views/Dashboard.vue'

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