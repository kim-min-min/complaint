import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import LoginPage from './pages/LoginPage';
import KakaoCallback from './pages/KakaoCallback';
import ComplaintForm from './pages/ComplaintForm';
import ReferenceSelectPage from './pages/ReferenceSelectPage';
import ResultPage from './pages/ResultPage';
import TermsPage from './pages/TermsPage';
import PrivacyPage from './pages/PrivacyPage';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<ComplaintForm />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/auth/kakao/callback" element={<KakaoCallback />} />
        <Route path="/form" element={<ComplaintForm />} />
        <Route path="/references" element={<ReferenceSelectPage />} />
        <Route path="/result" element={<ResultPage />} />
        <Route path="/terms" element={<TermsPage />} />
        <Route path="/privacy" element={<PrivacyPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
