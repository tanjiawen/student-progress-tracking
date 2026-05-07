import { api } from './client'
import type { VectorSearchResult } from '@/types'

export interface VectorSearchPayload {
  query: string
  subject?: string
  top_k?: number
}

export interface VectorSimilarPayload {
  question_id: number
  top_k?: number
}

export const vectorApi = {
  search: (data: VectorSearchPayload) =>
    api.post<VectorSearchResult[]>('/vector/search', data),

  similar: (data: VectorSimilarPayload) =>
    api.post<VectorSearchResult[]>('/vector/similar', data),
}
