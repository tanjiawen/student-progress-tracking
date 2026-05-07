import { api } from './client'
import type { KnowledgeNode, Subject } from '@/types'

export interface CreateKnowledgePayload {
  code?: string
  name: string
  level: number
  parent_id: number | null
  subject: string
}

export interface UpdateKnowledgePayload {
  name?: string
  code?: string
  parent_id?: number | null
}

export const knowledgeApi = {
  subjects: () => api.get<Subject[]>('/knowledge/subjects'),

  tree: (subjectId?: number) =>
    api.get<KnowledgeNode[]>(
      subjectId ? `/knowledge/subjects/${subjectId}/tree` : '/knowledge/subjects/1/tree'
    ),

  point: (id: number) => api.get<KnowledgeNode>(`/knowledge/points/${id}`),

  create: (data: CreateKnowledgePayload) =>
    api.post<KnowledgeNode>('/knowledge/points', data),

  update: (id: number, data: UpdateKnowledgePayload) =>
    api.patch<KnowledgeNode>(`/knowledge/points/${id}`, data),

  delete: (id: number) => api.delete<void>(`/knowledge/points/${id}`),

  importStandard: (formData: FormData) =>
    api.upload<{ count: number }>('/knowledge/import', formData),
}
