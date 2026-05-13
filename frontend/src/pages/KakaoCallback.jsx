import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

export default function KakaoCallback() {
  const navigate = useNavigate();
  const didRequest = useRef(false);

  useEffect(() => {
    const sendCodeToBackend = async (code) => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/auth/kakao/login`, {
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ code }),
        });

        if (!response.ok) {
          const data = await response.json().catch(() => ({}));
          throw new Error(data.detail || '로그인 처리 중 오류가 발생했습니다.');
        }

        navigate('/', { replace: true });
      } catch (error) {
        alert(error.message || '로그인 처리 중 오류가 발생했습니다.');
        navigate('/login', { replace: true });
      }
    };

    const code = new URL(window.location.href).searchParams.get('code');
    if (code) {
      if (didRequest.current) return;
      didRequest.current = true;
      sendCodeToBackend(code);
    } else {
      alert('로그인에 실패했습니다.');
      navigate('/login', { replace: true });
    }
  }, [navigate]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <div className="text-xl font-bold text-gray-600">
        카카오 로그인 처리 중입니다...
      </div>
    </div>
  );
}
