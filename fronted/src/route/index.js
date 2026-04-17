import { createRouter, createWebHistory } from 'vue-router'
import ContainerList from '../views/ContainerList.vue'
import LogViewer from '../views/LogViewer.vue'

const routes = [
  {
    path: '/',
    name: 'ContainerList',
    component: ContainerList
  },
  {
    path: '/containers/:id',
    name: 'LogViewer',
    component: LogViewer
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router