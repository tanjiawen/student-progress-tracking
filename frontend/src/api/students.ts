import { api } from './client'
import type {
  Student,
  KnowledgeState,
  ExamRecord,
  WeakKnowledge,
  ErrorBookItem,
  Report,
} from '@/types'

export const studentsApi = {
  list: () => api.get<Student[]>('/students'),

  detail: (id: number) => api.get<Student>(`/students/${id}`),

  knowledgeState: (id: number) =>
    api.get<KnowledgeState[]>(`/students/${id}/knowledge-state`),

  reports: (id: number) => api.get<Report[]>(`/students/${id}/reports`),

  errorBook: (id: number) =>
    api.get<ErrorBookItem[]>(`/students/${id}/error-book`),

  markErrorMastered: (studentId: number, errorId: number) =>
    api.patch(`/students/${studentId}/error-book/${errorId}/mastered`),

  examRecords: (id: number) => api.get<ExamRecord[]>(`/students/${id}/exams`),

  weakKnowledges: (id: number) =>
    api.get<WeakKnowledge[]>(`/students/${id}/weak-knowledges`),
}
