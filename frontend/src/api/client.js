// Axios wrapper. Attaches the single-user API key to every request and
// normalises the backend's {error: {code, message, detail}} shape into a
// thrown ApiError. Wrappers return the parsed envelope body ({data, meta}).

import axios from 'axios'

const KEY_STORAGE = 'reed.apiKey'

let apiKey = localStorage.getItem(KEY_STORAGE) || ''

export function getApiKey() {
  return apiKey
}

export function setApiKey(key) {
  apiKey = key || ''
  if (apiKey) localStorage.setItem(KEY_STORAGE, apiKey)
  else localStorage.removeItem(KEY_STORAGE)
}

export class ApiError extends Error {
  constructor(code, message, detail, status) {
    super(message || code)
    this.name = 'ApiError'
    this.code = code
    this.detail = detail
    this.status = status
  }
}

const http = axios.create({ baseURL: '/api/v1' })

http.interceptors.request.use((config) => {
  if (apiKey) config.headers['X-API-Key'] = apiKey
  return config
})

http.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status
    const body = error.response?.data
    if (body?.error) {
      return Promise.reject(
        new ApiError(body.error.code, body.error.message, body.error.detail, status),
      )
    }
    return Promise.reject(new ApiError('NETWORK_ERROR', error.message, null, status))
  },
)

export const api = {
  get: (url, config) => http.get(url, config).then((r) => r.data),
  post: (url, data, config) => http.post(url, data, config).then((r) => r.data),
  patch: (url, data, config) => http.patch(url, data, config).then((r) => r.data),
  put: (url, data, config) => http.put(url, data, config).then((r) => r.data),
  delete: (url, config) => http.delete(url, config).then((r) => r.data),
}
