const API_BASE = '/api/v1'

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

class ApiClient {
  async request<T = unknown>(method: string, path: string, data?: unknown): Promise<T> {
    const token = localStorage.getItem('token')
    const res = await fetch(`${API_BASE}${path}`, {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: data ? JSON.stringify(data) : undefined,
    })
    const json = await res.json()
    if (!res.ok) {
      const msg = isWrappedResponse(json) ? json.message : JSON.stringify(json)
      throw new Error(msg || `HTTP ${res.status}`)
    }
    return unwrapResponse<T>(json)
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
      const token = localStorage.getItem('token')
      const xhr = new XMLHttpRequest()
      xhr.open('POST', `${API_BASE}${path}`, true)
      if (token) {
        xhr.setRequestHeader('Authorization', `Bearer ${token}`)
      }
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
            reject(new Error(msg || `HTTP ${xhr.status}`))
          } catch {
            reject(new Error(xhr.responseText || `HTTP ${xhr.status}`))
          }
        }
      }
      xhr.onerror = () => reject(new Error('网络错误'))
      xhr.send(formData)
    })
  }
}

export const api = new ApiClient()
