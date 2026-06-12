import { Link } from 'react-router-dom';

export default function PrivacyPage() {
  return (
    <PolicyLayout title="개인정보 처리방침">
      <Section title="1. 수집하는 개인정보">
        서비스는 카카오 로그인 시 카카오 고유 식별자, 닉네임, 이메일을 수집할 수 있습니다. 고소장 작성 과정에서 사용자가 직접 입력한 성명, 주소, 연락처, 사건 내용, 증거자료 정보가 처리될 수 있습니다.
      </Section>
      <Section title="2. 개인정보 이용 목적">
        수집한 정보는 회원 식별, AI 요청 횟수 관리, 고소장 초안 생성, PDF 생성, 서비스 부정 이용 방지, 문의 대응을 위해 사용합니다.
      </Section>
      <Section title="3. 민감정보 입력 주의">
        고소장 작성에는 주민등록번호, 주소, 연락처 등 민감한 개인정보가 포함될 수 있습니다. 사용자는 제출에 필요한 범위에서만 정보를 입력해야 하며, 타인의 개인정보를 입력할 때에는 관련 법령을 준수해야 합니다.
      </Section>
      <Section title="4. 보관 및 파기">
        AI 작업 처리를 위해 입력 내용은 암호화되어 일시적으로 저장될 수 있으며, 작업 완료 후 원본 입력값은 삭제됩니다. 생성 결과와 작업 기록은 서비스 운영상 필요한 기간 동안 보관 후 파기될 수 있습니다.
      </Section>
      <Section title="5. 제3자 제공">
        서비스는 사용자의 개인정보를 법령상 근거 없이 제3자에게 판매하거나 제공하지 않습니다. 다만 AI 초안 생성을 위해 사용자가 입력한 내용이 AI API 제공자에게 전송될 수 있습니다.
      </Section>
      <Section title="6. 이용자의 권리">
        사용자는 개인정보 열람, 정정, 삭제, 처리정지를 요청할 수 있습니다. 구체적인 요청 방법은 서비스 제공자가 별도로 안내하는 연락처를 통해 진행합니다.
      </Section>
      <Section title="7. 보안 조치">
        서비스는 HttpOnly 쿠키 기반 로그인, 주요 데이터 암호화, 접근 제한 등 개인정보 보호를 위한 기술적 조치를 적용합니다.
      </Section>
    </PolicyLayout>
  );
}

function PolicyLayout({ title, children }) {
  return (
    <div className="min-h-screen bg-slate-50 px-4 py-10 text-slate-900">
      <main className="mx-auto max-w-3xl rounded-lg border border-slate-200 bg-white p-6 shadow-sm md:p-8">
        <Link to="/" className="text-sm font-semibold text-blue-700 hover:underline">처음으로 돌아가기</Link>
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
