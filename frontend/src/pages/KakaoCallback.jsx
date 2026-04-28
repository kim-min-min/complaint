import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

export default function KakaoCallback() {
  const navigate = useNavigate();

  useEffect(() => {
    // 1. 현재 주소창(URL)에서 '?code=...' 부분의 값만 쏙 뽑아냅니다.
    const code = new URL(window.location.href).searchParams.get("code");

    if (code) {
      // 코드가 존재하면 백엔드로 전송하는 함수 실행
      sendCodeToBackend(code);
    } else {
      // 코드가 없다면 (비정상적인 접근) 다시 로그인 페이지로 돌려보냄
      alert("로그인에 실패했습니다.");
      navigate('/login');
    }
  }, [navigate]);

  const sendCodeToBackend = async (code) => {
    try {
      // 2. 파이썬 백엔드 서버(예: 8000포트)로 코드를 담아 POST 요청을 보냅니다.
      // (axios를 쓰신다면 axios.post()를 사용하시면 됩니다)
      const response = await fetch(`http://localhost:8000/api/auth/kakao/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ code: code }),
      });

      if (!response.ok) throw new Error('백엔드 통신 에러');

      const data = await response.json();

      // 3. 백엔드에서 받은 우리 서비스의 토큰(JWT)을 저장합니다.
      // (보통 로컬 스토리지나 세션, 쿠키 등에 저장합니다)
      localStorage.setItem('accessToken', data.access_token);

      // 4. 로그인 성공! 메인 서비스 화면으로 이동시킵니다.
      navigate('/'); 

    } catch (error) {
      console.error("백엔드 전달 중 에러 발생:", error);
      alert("로그인 처리 중 오류가 발생했습니다.");
      navigate('/login');
    }
  };

  // 통신이 진행되는 아주 짧은 시간 동안 유저에게 보여줄 화면
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-xl font-bold text-gray-600 animate-pulse">
        카카오 로그인 처리 중입니다... 잠시만 기다려주세요. 💬
      </div>
    </div>
  );
}