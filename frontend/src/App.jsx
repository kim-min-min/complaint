import { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import LoginPage from './pages/LoginPage';
import KakaoCallback from './pages/KakaoCallback';
import ComplaintForm from './pages/ComplaintForm';
import ReferenceSelectPage from './pages/ReferenceSelectPage';
import ResultPage from './pages/ResultPage';
import TermsPage from './pages/TermsPage';
import PrivacyPage from './pages/PrivacyPage';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

function ProtectedRoute({ children }) {
  const [status, setStatus] = useState('checking');

  useEffect(() => {
    let ignore = false;

    async function checkAuth() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
          credentials: 'include',
        });
        if (!ignore) setStatus(response.ok ? 'authenticated' : 'unauthenticated');
      } catch {
        if (!ignore) setStatus('unauthenticated');
      }
    }

    checkAuth();
    return () => {
      ignore = true;
    };
  }, []);

  if (status === 'checking') {
    return <div className="min-h-screen bg-slate-50" />;
  }

  if (status === 'unauthenticated') {
    return <Navigate to="/login" replace />;
  }

  return children;
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<ProtectedRoute><ComplaintForm /></ProtectedRoute>} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/auth/kakao/callback" element={<KakaoCallback />} />
        <Route path="/form" element={<ProtectedRoute><ComplaintForm /></ProtectedRoute>} />
        <Route path="/references" element={<ProtectedRoute><ReferenceSelectPage /></ProtectedRoute>} />
        <Route path="/result" element={<ProtectedRoute><ResultPage /></ProtectedRoute>} />
        <Route path="/terms" element={<TermsPage />} />
        <Route path="/privacy" element={<PrivacyPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
