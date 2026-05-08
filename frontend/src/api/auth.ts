import { api } from './client'
import type { User } from '@/types'

export interface LoginPayload {
  username: string
  password: string
}

export interface RegisterPayload {
  username: string
  password: string
  name: string
  role?: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user: User
}

export const authApi = {
  login: (data: LoginPayload) =>
    api.post<LoginResponse>('/auth/login', data),

  register: (data: RegisterPayload) =>
    api.post<LoginResponse>('/auth/register', data),

  me: () => api.get<User>('/auth/me'),

  logout: () => {
    return Promise.resolve()
  },
}
