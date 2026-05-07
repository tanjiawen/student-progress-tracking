import { api } from './client'
import type { ClassItem, ClassDetail, Student } from '@/types'

export interface CreateClassPayload {
  name: string
}

export interface AddStudentsPayload {
  student_ids: number[]
}

export const classesApi = {
  list: () => api.get<ClassItem[]>('/classes'),

  create: (data: CreateClassPayload) => api.post<ClassItem>('/classes', data),

  detail: (id: number) => api.get<ClassDetail>(`/classes/${id}`),

  addStudents: (id: number, data: AddStudentsPayload) =>
    api.post<Student[]>(`/classes/${id}/students`, data),

  heatmap: (id: number) =>
    api.get<{ heatmap: { knowledge_point: string; student_name: string; mastery: number }[] }>(
      `/classes/${id}/heatmap`
    ),

  importStudents: (id: number, formData: FormData) =>
    api.upload<Student[]>(`/classes/${id}/students/import`, formData),
}
