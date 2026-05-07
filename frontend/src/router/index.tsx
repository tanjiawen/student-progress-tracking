import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { Spin } from 'antd'
import { useEffect, useState } from 'react'

import Login from '@/pages/Login'
import MainLayout from '@/layouts/MainLayout'
import Dashboard from '@/pages/Dashboard'
import ExamUpload from '@/pages/ExamUpload'
import ExamDetail from '@/pages/ExamDetail'
import StudentProfile from '@/pages/StudentProfile'
import ErrorBook from '@/pages/ErrorBook'
import ReportView from '@/pages/ReportView'
import GradingReview from '@/pages/GradingReview'
import KnowledgeManage from '@/pages/KnowledgeManage'
import ClassManage from '@/pages/ClassManage'
import ExercisePage from '@/pages/ExercisePage'

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, token } = useAuthStore()
  const [checked, setChecked] = useState(false)

  useEffect(() => {
    if (token && !isAuthenticated) {
      useAuthStore.getState().refresh().finally(() => setChecked(true))
    } else {
      setChecked(true)
    }
  }, [token, isAuthenticated])

  if (!checked) {
    return (
      <div style={{ height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Spin size="large" tip="加载中..." />
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}

function RoleGuard({
  children,
  allowedRoles,
}: {
  children: React.ReactNode
  allowedRoles: string[]
}) {
  const { user } = useAuthStore()
  if (!user || !allowedRoles.includes(user.role)) {
    return <Navigate to="/" replace />
  }
  return <>{children}</>
}

function PublicRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore()
  if (isAuthenticated) {
    return <Navigate to="/" replace />
  }
  return <>{children}</>
}

export default function AppRouter() {
  return (
    <Routes>
      <Route
        path="/login"
        element={
          <PublicRoute>
            <Login />
          </PublicRoute>
        }
      />
      <Route
        path="/"
        element={
          <RequireAuth>
            <MainLayout />
          </RequireAuth>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="exams" element={<ExamUpload />} />
        <Route path="exams/:examId" element={<ExamDetail />} />
        <Route path="students/:studentId" element={<StudentProfile />} />
        <Route path="error-book" element={<ErrorBook />} />
        <Route path="reports" element={<ReportView />} />
        <Route path="grading" element={<GradingReview />} />
        <Route path="knowledge" element={<KnowledgeManage />} />
        <Route path="classes" element={<ClassManage />} />
        <Route
          path="exercise"
          element={
            <RoleGuard allowedRoles={['student']}>
              <ExercisePage />
            </RoleGuard>
          }
        />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
