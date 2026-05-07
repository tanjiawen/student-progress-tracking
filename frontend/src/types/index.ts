export interface User {
  id: number
  username: string
  name: string
  role: 'admin' | 'teacher' | 'student'
  email?: string
}

export interface AuthState {
  user: User | null
  token: string | null
  isAuthenticated: boolean
}

export interface Exam {
  id: number
  title: string
  subject: string
  class_name: string
  status: 'processing' | 'ready' | 'grading' | 'graded'
  created_at: string
  updated_at?: string
  total_score?: number
  question_count?: number
}

export interface Question {
  id: number
  sequence: number
  type: 'choice' | 'fill_blank' | 'calculation' | 'essay'
  content: string
  score: number
  answer?: string
  status: 'pending' | 'graded'
  knowledge_points?: string[]
}

export interface ExamDetailData extends Exam {
  questions?: Question[]
}

export interface Student {
  id: number
  name: string
  student_no: string
  class_id: number
  class_name: string
  gender?: string
  total_score?: number
  rank?: number
}

export interface KnowledgeState {
  subject: string
  score: number
  max_score: number
}

export interface ExamRecord {
  id: number
  exam_name: string
  score: number
  max_score: number
  date: string
  rank?: number
}

export interface WeakKnowledge {
  knowledge: string
  mastery: number
  level: 'excellent' | 'good' | 'medium' | 'weak'
  error_count: number
}

export interface ErrorBookItem {
  id: number
  question_id: number
  question_content: string
  knowledge_point: string
  error_type: string
  error_count: number
  next_review_at: string
  mastered: boolean
}

export interface Report {
  id: number
  student_id: number
  type: 'monthly' | 'exam' | 'comprehensive'
  generated_at: string
  total_score: number
  rank: number
  evaluation: string
  weak_knowledges: string[]
  error_patterns: string[]
  suggestions: string[]
  target_score: number
}

export interface GradingItem {
  question_id: number
  student_id: number
  student_name: string
  answer_text: string
  ai_score: number
  ai_comment: string
  standard_answer: string
  final_score?: number
  error_type?: string
  status: 'pending' | 'confirmed' | 'rejected'
}

export interface KnowledgeNode {
  id: number
  code: string
  name: string
  level: number
  parent_id: number | null
  subject: string
  children?: KnowledgeNode[]
}

export interface ClassItem {
  id: number
  name: string
  student_count: number
  exam_count: number
  created_at: string
}

export interface ClassDetail extends ClassItem {
  students: Student[]
  exams: Exam[]
  heatmap: HeatmapData[]
}

export interface HeatmapData {
  knowledge_point: string
  student_name: string
  mastery: number
}

export interface ExerciseQuestion {
  id: number
  type: 'choice' | 'fill_blank' | 'essay'
  content: string
  options?: string[]
  answer?: string
  knowledge_point: string
  explanation?: string
}

export interface ExerciseResult {
  question_id: number
  correct: boolean
  user_answer: string
  correct_answer: string
  explanation: string
  score: number
}

export interface Subject {
  id: number
  name: string
  code: string
}

export interface VectorSearchResult {
  question_id: number
  similarity: number
  content: string
  knowledge_point: string
}
