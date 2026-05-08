import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { Spin } from 'antd'
import React, { Suspense, useEffect, useState } from 'react'

const Login = React.lazy(() => import('@/pages/Login'))
const MainLayout = React.lazy(() => import('@/layouts/MainLayout'))
const Dashboard = React.lazy(() => import('@/pages/Dashboard'))
const ExamUpload = React.lazy(() => import('@/pages/ExamUpload'))
const ExamDetail = React.lazy(() => import('@/pages/ExamDetail'))
const StudentProfile = React.lazy(() => import('@/pages/StudentProfile'))
const ErrorBook = React.lazy(() => import('@/pages/ErrorBook'))
const ReportView = React.lazy(() => import('@/pages/ReportView'))
const GradingReview = React.lazy(() => import('@/pages/GradingReview'))
const KnowledgeManage = React.lazy(() => import('@/pages/KnowledgeManage'))
const ClassManage = React.lazy(() => import('@/pages/ClassManage'))
const ExercisePage = React.lazy(() => import('@/pages/ExercisePage'))

const PageFallback = (
  <div style={{ height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
    <Spin size="large" tip="页面加载中..." />
  </div>
)

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore()
  const [checked, setChecked] = useState(false)

  useEffect(() => {
    // Security fix V-017: always try refresh via HttpOnly cookie
    if (!isAuthenticated) {
      useAuthStore.getState().refresh().finally(() => setChecked(true))
    } else {
      setChecked(true)
    }
  }, [isAuthenticated])

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
            <Suspense fallback={PageFallback}>
              <Login />
            </Suspense>
          </PublicRoute>
        }
      />
      <Route
        path="/"
        element={
          <RequireAuth>
            <Suspense fallback={PageFallback}>
              <MainLayout />
            </Suspense>
          </RequireAuth>
        }
      >
        <Route index element={<Suspense fallback={PageFallback}><Dashboard /></Suspense>} />
        <Route path="exams" element={<Suspense fallback={PageFallback}><ExamUpload /></Suspense>} />
        <Route path="exams/:examId" element={<Suspense fallback={PageFallback}><ExamDetail /></Suspense>} />
        <Route path="students/:studentId" element={<Suspense fallback={PageFallback}><StudentProfile /></Suspense>} />
        <Route path="error-book" element={<Suspense fallback={PageFallback}><ErrorBook /></Suspense>} />
        <Route path="reports" element={<Suspense fallback={PageFallback}><ReportView /></Suspense>} />
        <Route path="grading" element={<Suspense fallback={PageFallback}><GradingReview /></Suspense>} />
        <Route path="knowledge" element={<Suspense fallback={PageFallback}><KnowledgeManage /></Suspense>} />
        <Route path="classes" element={<Suspense fallback={PageFallback}><ClassManage /></Suspense>} />
        <Route
          path="exercise"
          element={
            <RoleGuard allowedRoles={['student']}>
              <Suspense fallback={PageFallback}>
                <ExercisePage />
              </Suspense>
            </RoleGuard>
          }
        />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
