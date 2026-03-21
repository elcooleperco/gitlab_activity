/** HTTP-клиент для работы с backend API. */

import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

export default api
