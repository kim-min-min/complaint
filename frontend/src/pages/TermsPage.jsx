import { Link } from 'react-router-dom';

export default function TermsPage() {
  return (
    <PolicyLayout title="이용약관">
      <Section title="1. 서비스의 목적">
        본 서비스는 사용자가 입력한 사건 내용을 바탕으로 고소장 초안 작성을 보조하는 도구입니다. 본 서비스는 변호사 또는 법률 전문가의 자문을 대체하지 않습니다.
      </Section>
      <Section title="2. AI 초안의 한계">
        서비스가 제공하는 문서는 AI가 생성한 초안이며, 법적 효력이나 제출 결과를 보장하지 않습니다. 사용자는 제출 전 사실관계, 증거자료, 법률 표현을 직접 확인해야 합니다.
      </Section>
      <Section title="3. 사용자 책임">
        사용자는 허위 사실, 타인의 개인정보, 불법적 목적의 내용을 입력해서는 안 됩니다. 본 문서의 사용으로 발생하는 어떠한 법적 책임도 서비스 제공자는 지지 않습니다.
      </Section>
      <Section title="4. 이용 제한">
        서비스 안정성과 비용 관리를 위해 계정별 AI 요청 횟수가 제한될 수 있습니다. 비정상적 이용, 자동화된 대량 요청, 타인 계정 사용이 확인될 경우 이용이 제한될 수 있습니다.
      </Section>
      <Section title="5. 서비스 변경 및 중단">
        서비스 제공자는 운영상 필요에 따라 기능을 변경하거나 일시 중단할 수 있습니다. 중요한 변경 사항은 서비스 화면 또는 별도 공지로 안내합니다.
      </Section>
      <Section title="6. 문의">
        서비스 이용과 관련한 문의는 서비스 제공자가 별도로 안내하는 연락처를 통해 접수합니다.
      </Section>
    </PolicyLayout>
  );
}

function PolicyLayout({ title, children }) {
  return (
    <div className="min-h-screen bg-slate-50 px-4 py-10 text-slate-900">
      <main className="mx-auto max-w-3xl rounded-lg border border-slate-200 bg-white p-6 shadow-sm md:p-8">
        <Link to="/login" className="text-sm font-semibold text-blue-700 hover:underline">로그인으로 돌아가기</Link>
        <h1 className="mt-5 text-3xl font-bold tracking-normal text-slate-950">{title}</h1>
        <div className="mt-8 space-y-7">{children}</div>
      </main>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <section>
      <h2 className="text-base font-bold text-slate-950">{title}</h2>
      <p className="mt-2 text-sm leading-7 text-slate-600">{children}</p>
    </section>
  );
}
