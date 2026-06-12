import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import AuthBar from '../components/AuthBar';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

export default function ComplaintForm() {
  const navigate = useNavigate();
  const location = useLocation();
  const restoredFormData = location.state?.formData || {};
  const [error, setError] = useState('');
  const [usage, setUsage] = useState(null);
  const [formData, setFormData] = useState({
    complainantName: restoredFormData.complainantName || '',
    accusedName: restoredFormData.accusedName || '',
    incidentDescription: restoredFormData.incidentDescription || '',
    incidentDate: restoredFormData.incidentDate || '',
    incidentLocation: restoredFormData.incidentLocation || '',
    evidenceSummary: restoredFormData.evidenceSummary || '',
    requestedPunishment: restoredFormData.requestedPunishment || '',
  });

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const toPayload = () => ({
    complainant_name: formData.complainantName,
    accused_name: formData.accusedName,
    incident_date: formData.incidentDate,
    incident_location: formData.incidentLocation,
    incident_description: formData.incidentDescription,
    evidence_summary: formData.evidenceSummary,
    requested_punishment: formData.requestedPunishment,
  });

  useEffect(() => {
    let ignore = false;

    async function loadUsage() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/usage/today`, {
          credentials: 'include',
        });
        const data = await response.json();
        if (!ignore && response.ok) setUsage(data);
        if (!ignore && response.status === 401) navigate('/login');
      } catch {
        if (!ignore) setUsage(null);
      }
    }

    loadUsage();
    return () => {
      ignore = true;
    };
  }, [navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (toPayload().incident_description.trim().length < 10) {
      setError('무슨 일이 있었는지 10자 이상 조금 더 자세히 적어주세요.');
      return;
    }
    navigate('/references', { state: { formData } });
  };

  return (
    <div className="min-h-screen bg-[#f7f8f5] px-4 py-8 text-left text-[#111111]">
      <main className="mx-auto max-w-3xl">
        <AuthBar />
        <header className="mb-8">
          <p className="text-sm font-semibold text-[#50534e]">고소장 초안</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-normal text-[#111111]">아는 내용부터 적어주세요</h1>
          <p className="mt-3 text-sm leading-6 text-[#5f625d]">사건 종류를 몰라도 괜찮습니다. 필요한 내용은 다음 단계에서 함께 정리합니다.</p>
          {usage && (
            <p className="mt-3 inline-flex rounded-full border border-[#d7d9d2] bg-[#eef2e8] px-4 py-2 text-sm font-semibold text-[#3d4a35]">
              오늘 남은 AI 요청 {usage.remaining}회 / {usage.limit}회
            </p>
          )}
        </header>

        <form onSubmit={handleSubmit} className="space-y-5 rounded-[6px] border border-[#d7d9d2] bg-[#fbfbf8] p-6 shadow-[0_22px_60px_rgba(30,32,27,0.08)]">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Field label="내 이름" name="complainantName" value={formData.complainantName} onChange={handleChange} placeholder="예: 홍길동" required />
            <Field label="상대방 이름/닉네임" name="accusedName" value={formData.accusedName} onChange={handleChange} placeholder="모르면 성명불상" required />
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Field label="언제 있었나요" name="incidentDate" value={formData.incidentDate} onChange={handleChange} placeholder="예: 2026년 10월 31일" />
            <Field label="어디서 있었나요" name="incidentLocation" value={formData.incidentLocation} onChange={handleChange} placeholder="예: 집 앞, 회사, 온라인 게시판" />
          </div>

          <TextArea label="무슨 일이 있었는지 편하게 적어주세요" name="incidentDescription" value={formData.incidentDescription} onChange={handleChange} rows={8} placeholder="예: 상대방이 언제, 어디서, 어떤 행동을 했고, 그로 인해 어떤 피해가 있었는지 적어주세요." minLength={10} required />
          <TextArea label="가지고 있는 증거" name="evidenceSummary" value={formData.evidenceSummary} onChange={handleChange} rows={3} placeholder="예: 사진, 진단서, 송금 내역, 대화 캡처, 녹취, 목격자" />
          <TextArea label="처벌 의사" name="requestedPunishment" value={formData.requestedPunishment} onChange={handleChange} rows={2} placeholder="예: 엄정한 수사와 처벌을 원합니다." />

          {error && <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}

          <p className="text-center text-xs leading-5 text-[#64675f]">생성 결과는 개인정보 보호를 위해 자동 삭제됩니다.</p>
          <button type="submit" className="w-full rounded-full bg-[#111111] px-4 py-3 text-base font-semibold text-white transition hover:bg-[#30302d]">
            참고자료 선택하기
          </button>
        </form>
      </main>
    </div>
  );
}

function Field({ label, ...props }) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-semibold text-[#32342f]">{label}</span>
      <input {...props} className="w-full rounded-[4px] border border-[#d7d9d2] bg-white px-3 py-2 text-sm text-[#111111] outline-none transition placeholder:text-[#8b8e86] focus:border-[#111111] focus:ring-2 focus:ring-[#e9efe3]" />
    </label>
  );
}

function TextArea({ label, ...props }) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-semibold text-[#32342f]">{label}</span>
      <textarea {...props} className="w-full resize-y rounded-[4px] border border-[#d7d9d2] bg-white px-3 py-2 text-sm leading-6 text-[#111111] outline-none transition placeholder:text-[#8b8e86] focus:border-[#111111] focus:ring-2 focus:ring-[#e9efe3]" />
    </label>
  );
}
