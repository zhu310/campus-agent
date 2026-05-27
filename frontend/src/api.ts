// 前端统一的 Axios 实例，集中配置后端 API 基础地址。
import axios from 'axios'

const api = axios.create({
  baseURL: 'http://localhost:8000/api',
})

export default api
