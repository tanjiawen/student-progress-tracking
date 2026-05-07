import { api } from './client'
import type { Exam, ExamDetailData, Question } from '@/types'

export interface PaginatedExams {
  items: Exam[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface UploadExamPayload {
  title: string
  subject: string
  class_id: number
}

export const examsApi = {
  list: () => api.get<PaginatedExams>('/exams'),

  detail: (id: number) => api.get<ExamDetailData>(`/exams/${id}`),

  questions: (id: number) => api.get<Question[]>(`/exams/${id}/questions`),

  upload: (formData: FormData, onProgress?: (percent: number) => void) =>
    api.upload<Exam>('/exams/upload', formData, onProgress),

  startOCR: (id: number) => api.post<{ task_id: string }>(`/exams/${id}/start-ocr`),

  startGrading: (id: number) => api.post<{ task_id: string }>(`/exams/${id}/start-grading`),

  create: (data: UploadExamPayload) => api.post<Exam>('/exams', data),
}
