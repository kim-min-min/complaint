import { useQuery } from '@tanstack/react-query';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import LandingPage from './pages/LandingPage';
import LoginPage from './pages/LoginPage';
import KakaoCallback from './pages/KakaoCallback';
import ComplaintForm from './pages/ComplaintForm';
import AnalysisPage from './pages/AnalysisPage';
import ResultPage from './pages/ResultPage';
import TermsPage from './pages/TermsPage';
import PrivacyPage from './pages/PrivacyPage';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

async function fetchMe() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
      credentials: 'include',
    });

    if (!response.ok) {
      return null;
    }

    return response.json();
  } catch {
    return null;
  }
}

function ProtectedRoute({ children }) {
  const { data: user, isLoading } = useQuery({
    queryKey: ['me'],
    queryFn: fetchMe,
    retry: false,
    staleTime: 5 * 60 * 1000,
  });

  if (isLoading) {
    return <div className="min-h-screen bg-slate-50" />;
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return children;
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/auth/kakao/callback" element={<KakaoCallback />} />
        <Route path="/form" element={<ProtectedRoute><ComplaintForm /></ProtectedRoute>} />
        <Route path="/analysis" element={<ProtectedRoute><AnalysisPage /></ProtectedRoute>} />
        <Route path="/result" element={<ProtectedRoute><ResultPage /></ProtectedRoute>} />
        <Route path="/terms" element={<TermsPage />} />
        <Route path="/privacy" element={<PrivacyPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
