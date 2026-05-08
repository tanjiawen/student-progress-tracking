import { useAuthStore } from '@/store/authStore'

const API_BASE = '/api/v1'
const REQUEST_TIMEOUT = 30000 // 30秒

/** 后端统一响应格式 */
interface ApiResponse<T = unknown> {
  code: number | string
  message: string
  data: T
}

function isWrappedResponse(obj: unknown): obj is ApiResponse {
  return (
    obj !== null &&
    typeof obj === 'object' &&
    'code' in obj &&
    'data' in obj
  )
}

function unwrapResponse<T>(obj: unknown): T {
  if (isWrappedResponse(obj)) {
    const code = obj.code
    if (code !== 0 && code !== 'ok') {
      throw new Error(obj.message || `请求失败 (code: ${code})`)
    }
    return obj.data as T
  }
  return obj as T
}

function handleHttpError(status: number, message: string): Error {
  if (status === 401) {
    useAuthStore.getState().logout()
    window.location.href = '/login'
    return new Error('登录已过期，请重新登录')
  }
  if (status >= 500) {
    return new Error(message || '服务器繁忙，请稍后重试')
  }
  return new Error(message || `请求失败 (HTTP ${status})`)
}

class ApiClient {
  private getToken(): string | null {
    return useAuthStore.getState().token
  }

  async request<T = unknown>(method: string, path: string, data?: unknown): Promise<T> {
    const token = this.getToken()
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT)

    try {
      const res = await fetch(`${API_BASE}${path}`, {
        method,
        headers: {
          'Content-Type': 'application/json',
          // Security fix V-017: prefer HttpOnly cookie; keep Authorization fallback for tests/mobile
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        credentials: 'include', // Security fix V-017: send HttpOnly cookies
        body: data ? JSON.stringify(data) : undefined,
        signal: controller.signal,
      })
      clearTimeout(timeoutId)

      let json: unknown
      try {
        json = await res.json()
      } catch {
        json = null
      }

      if (!res.ok) {
        const msg = isWrappedResponse(json) ? json.message : JSON.stringify(json)
        throw handleHttpError(res.status, msg || `HTTP ${res.status}`)
      }
      return unwrapResponse<T>(json)
    } catch (error) {
      clearTimeout(timeoutId)
      if (error instanceof Error) {
        if (error.name === 'AbortError') {
          throw new Error('请求超时，请检查网络后重试')
        }
        if (error.message.includes('fetch') || error.message.includes('network')) {
          throw new Error('网络异常，请检查网络连接')
        }
      }
      throw error
    }
  }

  get<T = unknown>(path: string) {
    return this.request<T>('GET', path)
  }

  post<T = unknown>(path: string, data?: unknown) {
    return this.request<T>('POST', path, data)
  }

  put<T = unknown>(path: string, data?: unknown) {
    return this.request<T>('PUT', path, data)
  }

  patch<T = unknown>(path: string, data?: unknown) {
    return this.request<T>('PATCH', path, data)
  }

  delete<T = unknown>(path: string) {
    return this.request<T>('DELETE', path)
  }

  upload<T = unknown>(path: string, formData: FormData, onProgress?: (percent: number) => void): Promise<T> {
    return new Promise((resolve, reject) => {
      const token = this.getToken()
      const xhr = new XMLHttpRequest()
      xhr.open('POST', `${API_BASE}${path}`, true)
      xhr.withCredentials = true // Security fix V-017: send HttpOnly cookies
      if (token) {
        xhr.setRequestHeader('Authorization', `Bearer ${token}`)
      }
      xhr.timeout = REQUEST_TIMEOUT
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable && onProgress) {
          onProgress(Math.round((e.loaded / e.total) * 100))
        }
      }
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const json = JSON.parse(xhr.responseText)
            resolve(unwrapResponse<T>(json))
          } catch {
            resolve(xhr.responseText as T)
          }
        } else {
          try {
            const json = JSON.parse(xhr.responseText)
            const msg = isWrappedResponse(json) ? json.message : xhr.responseText
            reject(handleHttpError(xhr.status, msg || `HTTP ${xhr.status}`))
          } catch {
            reject(handleHttpError(xhr.status, xhr.responseText || `HTTP ${xhr.status}`))
          }
        }
      }
      xhr.ontimeout = () => reject(new Error('请求超时，请检查网络后重试'))
      xhr.onerror = () => reject(new Error('网络异常，请检查网络连接'))
      xhr.send(formData)
    })
  }
}

export const api = new ApiClient()
