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
    <div className="min-h-screen bg-slate-50 px-4 py-8 text-left text-slate-900">
      <main className="mx-auto max-w-3xl">
        <AuthBar />
        <header className="mb-8">
          <p className="text-sm font-semibold text-blue-700">빠른 고소장 초안</p>
          <h1 className="mt-2 text-3xl font-bold tracking-normal text-slate-950">일단 아는 내용만 적어도 초안을 만들어드립니다</h1>
          <p className="mt-3 text-sm leading-6 text-slate-600">사기, 폭행, 명예훼손 등 사건 종류를 몰라도 괜찮습니다. 제출용 개인정보는 미리보기 후 보완할 수 있습니다.</p>
          {usage && (
            <p className="mt-3 inline-flex rounded-md border border-blue-100 bg-blue-50 px-3 py-2 text-sm font-semibold text-blue-800">
              오늘 남은 AI 요청 {usage.remaining}회 / {usage.limit}회
            </p>
          )}
        </header>

        <form onSubmit={handleSubmit} className="space-y-5 rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
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

          <p className="text-center text-xs leading-5 text-slate-500">생성 결과는 개인정보 보호를 위해 자동 삭제됩니다.</p>
          <button type="submit" className="w-full rounded-lg bg-blue-700 px-4 py-3 text-base font-bold text-white transition hover:bg-blue-800">
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
      <span className="mb-1 block text-sm font-semibold text-slate-700">{label}</span>
      <input {...props} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none transition focus:border-blue-600 focus:ring-2 focus:ring-blue-100" />
    </label>
  );
}

function TextArea({ label, ...props }) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-semibold text-slate-700">{label}</span>
      <textarea {...props} className="w-full resize-y rounded-md border border-slate-300 px-3 py-2 text-sm leading-6 outline-none transition focus:border-blue-600 focus:ring-2 focus:ring-blue-100" />
    </label>
  );
}
