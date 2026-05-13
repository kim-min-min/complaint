import { Link } from 'react-router-dom';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

export default function LoginPage() {
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

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#eef3f8] px-4 py-10 text-slate-950">
      <div className="absolute inset-0 bg-[linear-gradient(120deg,rgba(255,255,255,0.92),rgba(248,250,252,0.68))]" />
      <div className="absolute left-[7%] top-[12%] hidden h-56 w-40 rotate-[-8deg] rounded-sm border border-slate-200 bg-white/70 shadow-2xl shadow-slate-300/40 lg:block" />
      <div className="absolute right-[9%] top-[18%] hidden h-64 w-44 rotate-[7deg] rounded-sm border border-slate-200 bg-white/60 shadow-2xl shadow-slate-300/30 lg:block" />
      <div className="absolute bottom-[10%] left-[15%] hidden h-1 w-44 rotate-[-16deg] rounded-full bg-slate-400/25 lg:block" />

      <div className="relative w-full max-w-[460px] rounded-[22px] border border-white/80 bg-white/95 p-8 text-center shadow-2xl shadow-slate-300/60 backdrop-blur sm:p-10">
        <div className="mb-7">
          <div className="mx-auto mb-6 flex h-20 w-20 rotate-3 items-center justify-center rounded-2xl bg-blue-700 shadow-lg shadow-blue-200">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-12 w-12 -rotate-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <h1 className="text-3xl font-extrabold tracking-normal text-slate-950 sm:text-[34px]">AI 고소장 작성 도우미</h1>
        </div>

        <div className="mb-9 text-[15px] leading-7 text-slate-500">
          사건 내용을 입력하면<br />
          고소장을 작성해드립니다.
        </div>

        <button
          onClick={handleLogin}
          className="flex min-h-14 w-full items-center justify-center rounded-xl bg-[#FEE500] px-6 py-4 font-bold text-[#191919] shadow-md shadow-yellow-200/70 transition-all duration-200 hover:bg-[#FDE100] active:scale-[0.98]"
        >
          <svg className="mr-3 h-6 w-6" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path d="M12 3c-4.97 0-9 3.185-9 7.115 0 2.558 1.707 4.8 4.315 6.055-.177.65-.638 2.35-.731 2.723-.117.46.166.454.349.33.143-.097 2.274-1.543 3.18-2.155.603.085 1.233.132 1.887.132 4.97 0 9-3.185 9-7.115S16.97 3 12 3z" />
          </svg>
          카카오 계정으로 로그인
        </button>

        <div className="mt-8 flex justify-center gap-6 border-t border-slate-100 pt-8 text-xs text-slate-400">
          <Link to="/terms" className="hover:underline">이용약관</Link>
          <Link to="/privacy" className="hover:underline">개인정보 처리방침</Link>
          <button className="hover:underline">고객센터</button>
        </div>
      </div>
    </div>
  );
}
