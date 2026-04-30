import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { AuthProvider, useAuth } from './context/AuthContext';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import CreateProjectPage from './pages/CreateProjectPage';
import ProjectDetailPage from './pages/ProjectDetailPage';
import DocumentListPage from './pages/DocumentListPage';
import GoogleCallback from './pages/GoogleCallback';
import AIConfigManagementPage from './pages/AIConfigManagementPage';

const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" />;
};

const AdminRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, isAdmin } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" />;
  if (!isAdmin) return <Navigate to="/" />;
  return <>{children}</>;
};

const App: React.FC = () => {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/api/v1/auth/google/redirect" element={<GoogleCallback />} />
          <Route path="/" element={
            <ProtectedRoute>
              <DashboardPage />
            </ProtectedRoute>
          } />
          <Route path="/create" element={
            <ProtectedRoute>
              <CreateProjectPage />
            </ProtectedRoute>
          } />
          <Route path="/documents" element={
            <ProtectedRoute>
              <DocumentListPage />
            </ProtectedRoute>
          } />
          <Route path="/project/:id" element={
            <ProtectedRoute>
              <ProjectDetailPage />
            </ProtectedRoute>
          } />
          <Route path="/admin/configs" element={
            <AdminRoute>
              <AIConfigManagementPage />
            </AdminRoute>
          } />
        </Routes>
        <Toaster position="bottom-right" toastOptions={{
          style: {
            background: 'var(--bg-card)',
            color: 'var(--text-main)',
            border: '1px solid var(--border)',
          }
        }} />
      </BrowserRouter>
    </AuthProvider>
  );
};

export default App;
