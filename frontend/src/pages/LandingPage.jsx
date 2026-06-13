import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

export default function LandingPage() {
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
        // 비로그인 상태와 동일하게 랜딩 페이지를 보여줍니다.
      }
      if (!ignore) setCheckingAuth(false);
    }

    checkAuth();
    return () => {
      ignore = true;
    };
  }, [navigate]);

  if (checkingAuth) {
    return <div className="min-h-screen bg-[#f7f8f5]" />;
  }

  return (
    <div className="min-h-screen bg-[#f7f8f5] text-[#111111]">
      <header className="mx-auto flex w-full max-w-7xl items-center px-5 py-5 sm:px-8 lg:px-10">
        <Link to="/" className="text-sm font-semibold tracking-normal">
          AI 고소장 작성
        </Link>
      </header>

      <main>
        <section className="mx-auto grid min-h-[calc(100vh-72px)] w-full max-w-7xl items-center gap-10 px-5 pb-16 pt-8 sm:px-8 lg:grid-cols-[0.82fr_1.18fr] lg:px-10 lg:pb-20">
          <div className="max-w-2xl">
            <h1 className="text-[50px] font-semibold leading-[1.02] tracking-normal text-[#10110f] sm:text-[72px] lg:text-[86px]">
              AI 고소장 작성
            </h1>
            <p className="mt-7 max-w-xl text-lg leading-8 text-[#50534e] sm:text-xl sm:leading-9">
              사건을 입력하면 AI가 쟁점, 판례, 고소장 초안을 정리합니다.
            </p>
            <div className="mt-9 flex flex-col gap-3 sm:flex-row">
              <Link
                to="/login"
                className="inline-flex min-h-12 items-center justify-center rounded-full bg-[#111111] px-6 py-3 text-sm font-semibold text-white transition hover:bg-[#30302d]"
              >
                시작하기
              </Link>
            </div>
          </div>

          <div className="relative">
            <img
              src="/landing-hero.png"
              alt="AI 고소장 작성 서비스 화면"
              className="aspect-[16/10] w-full rounded-[6px] object-cover shadow-[0_32px_90px_rgba(30,32,27,0.14)]"
            />
          </div>
        </section>

        <section id="workflow" className="border-y border-[#e1e3dc] bg-[#fbfbf8]">
          <div className="mx-auto grid max-w-7xl gap-0 px-5 sm:px-8 lg:grid-cols-3 lg:px-10">
            <Feature
              number="01"
              title="사건 정리"
              text="입력한 내용을 범죄사실과 증거관계로 나눕니다."
            />
            <Feature
              number="02"
              title="판례 추천"
              text="사실관계가 가까운 형사 판례를 찾습니다."
            />
            <Feature
              number="03"
              title="초안 작성"
              text="선택한 판례를 반영해 고소장 초안을 만듭니다."
            />
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-5 py-16 sm:px-8 lg:px-10">
          <div className="max-w-3xl text-sm leading-7 text-[#64675f]">
            본 서비스는 고소장 초안 작성을 보조하는 도구이며, 법률 자문이나 사건 결과를 보장하지 않습니다. 제출 전 변호사 등 법률전문가의 검토를 권장합니다.
          </div>
        </section>
      </main>

      <footer className="border-t border-[#e1e3dc] px-5 py-8 sm:px-8 lg:px-10">
        <div className="mx-auto flex max-w-7xl gap-5 text-sm text-[#64675f]">
          <Link to="/terms" className="hover:text-[#111111]">이용약관</Link>
          <Link to="/privacy" className="hover:text-[#111111]">개인정보처리방침</Link>
        </div>
      </footer>
    </div>
  );
}

function Feature({ number, title, text }) {
  return (
    <article className="border-[#e1e3dc] py-10 lg:border-r lg:px-8 first:lg:pl-0 last:lg:border-r-0 last:lg:pr-0">
      <p className="text-xs font-semibold text-[#7b7f75]">{number}</p>
      <h3 className="mt-5 text-xl font-semibold tracking-normal text-[#151612]">{title}</h3>
      <p className="mt-4 text-sm leading-7 text-[#5d6159]">{text}</p>
    </article>
  );
}
