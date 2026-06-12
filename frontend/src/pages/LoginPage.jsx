import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

export default function LoginPage() {
  const navigate = useNavigate();
  const [checkingAuth, setCheckingAuth] = useState(true);

  useEffect(() => {
    let ignore = false;

    async function checkAuth() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
          credentials: 'include',
        });
        if (ignore) return;
        if (response.ok) {
          navigate('/form', { replace: true });
          return;
        }
      } catch {
        // 비로그인 상태와 동일하게 로그인 화면을 보여줍니다.
      }
      if (!ignore) setCheckingAuth(false);
    }

    checkAuth();
    return () => {
      ignore = true;
    };
  }, [navigate]);

  const handleLogin = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/kakao/login-url`, {
        credentials: 'include',
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || '카카오 로그인 URL을 만들 수 없습니다.');
      window.location.href = data.login_url;
    } catch (error) {
      alert(error.message || '로그인을 시작하지 못했습니다.');
    }
  };

  if (checkingAuth) {
    return <div className="min-h-screen bg-[#f7f8f5]" />;
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#f7f8f5] px-4 py-10 text-[#111111]">
      <div className="absolute inset-x-0 top-0 h-px bg-[#e1e3dc]" />
      <div className="absolute left-[8%] top-[16%] hidden h-52 w-36 rotate-[-7deg] rounded-[4px] border border-[#e1e3dc] bg-[#fbfbf8]/80 shadow-[0_28px_70px_rgba(30,32,27,0.08)] lg:block" />
      <div className="absolute right-[10%] top-[20%] hidden h-60 w-40 rotate-[6deg] rounded-[4px] border border-[#e1e3dc] bg-[#fbfbf8]/70 shadow-[0_28px_70px_rgba(30,32,27,0.08)] lg:block" />

      <div className="relative w-full max-w-[460px]">
        <Link to="/" className="mb-4 inline-flex text-sm font-semibold text-[#64675f] transition hover:text-[#111111]">
          처음으로
        </Link>
        <div className="rounded-[6px] border border-[#d7d9d2] bg-[#fbfbf8]/95 p-8 text-center shadow-[0_32px_90px_rgba(30,32,27,0.12)] backdrop-blur sm:p-10">
        <div className="mb-7">
          <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-[6px] border border-[#d7d9d2] bg-white shadow-[0_16px_42px_rgba(30,32,27,0.08)]">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-9 w-9 text-[#111111]" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <h1 className="text-3xl font-semibold tracking-normal text-[#111111] sm:text-[34px]">AI 고소장 작성</h1>
        </div>

        <div className="mb-9 text-[15px] leading-7 text-[#5f625d]">
          사건 내용을 입력하면<br />
          고소장 초안 작성을 도와드립니다.
        </div>

        <button
          onClick={handleLogin}
          className="flex min-h-14 w-full items-center justify-center rounded-full bg-[#FEE500] px-6 py-4 font-bold text-[#191919] shadow-[0_16px_38px_rgba(85,71,0,0.12)] transition-all duration-200 hover:bg-[#FDE100] active:scale-[0.98]"
        >
          <svg className="mr-3 h-6 w-6" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path d="M12 3c-4.97 0-9 3.185-9 7.115 0 2.558 1.707 4.8 4.315 6.055-.177.65-.638 2.35-.731 2.723-.117.46.166.454.349.33.143-.097 2.274-1.543 3.18-2.155.603.085 1.233.132 1.887.132 4.97 0 9-3.185 9-7.115S16.97 3 12 3z" />
          </svg>
          카카오 계정으로 로그인
        </button>

        <div className="mt-8 flex justify-center gap-6 border-t border-[#e1e3dc] pt-8 text-xs text-[#64675f]">
          <Link to="/terms" className="hover:underline">이용약관</Link>
          <Link to="/privacy" className="hover:underline">개인정보 처리방침</Link>
        </div>
        </div>
      </div>
    </div>
  );
}
