import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import AuthBar from '../components/AuthBar';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';
const POLL_INTERVAL_MS = 2000;
const POLL_TIMEOUT_MS = 120000;

const EMPTY_FINAL_FIELDS = {
  complainantRrn: '',
  complainantAddress: '',
  complainantJob: '',
  complainantPhone: '',
  accusedRrn: '',
  accusedAddress: '',
  accusedJob: '',
  accusedPhone: '',
  accusedIdentifier: '',
  policeStation: '',
  filingDate: '',
  chargeName: '',
  attachments: '',
};

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function pollJob(jobId) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < POLL_TIMEOUT_MS) {
    await wait(POLL_INTERVAL_MS);

    const response = await fetch(`${API_BASE_URL}/api/complaints/jobs/${jobId}`, {
      credentials: 'include',
    });
    const data = await response.json();
    if (!response.ok) throw new Error(formatApiError(data, '작업 상태 조회에 실패했습니다.'));

    if (data.status === 'completed') return data;
    if (data.status === 'failed') throw new Error(data.error_message || 'AI 작업에 실패했습니다.');
  }

  throw new Error('생성 시간이 오래 걸리고 있습니다. 잠시 후 다시 시도해주세요.');
}

function formatApiError(data, fallback) {
  const detail = data?.detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => item?.msg).filter(Boolean).join('\n') || fallback;
  }
  if (typeof detail === 'string') return detail;
  if (detail && typeof detail === 'object') return detail.message || JSON.stringify(detail);
  return fallback;
}

function extractSection(text, number, fallback = '') {
  const pattern = new RegExp(`(?:^|\\n)\\s*${number}\\.\\s*[^\\n]*\\n([\\s\\S]*?)(?=\\n\\s*${number + 1}\\.\\s|\\n\\s*첨부서류|\\s*$)`);
  const match = text.match(pattern);
  return (match?.[1] || fallback).trim();
}

function defaultPurpose(chargeName) {
  const charge = String(chargeName || '').trim() || '○○죄';
  return `고소인은 피고소인을 ${charge}로 고소하오니 처벌하여 주시기 바랍니다.`;
}

function formatReferenceText(references) {
  return (references || [])
    .map((item) => String(item || '').trim())
    .filter(Boolean)
    .map((item) => `- ${item}`)
    .join('\n');
}

function normalizeReferenceHeading(text) {
  return String(text || '')
    .replace(/\s*※?\s*참고판례\s*[:：]\s*/g, '\n\n※ 참고판례\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

function appendReferenceText(reason, references) {
  const referenceText = formatReferenceText(references);
  const base = normalizeReferenceHeading(reason);
  if (!referenceText || base.includes('참고판례')) return base;
  return `${base}\n\n※ 참고판례\n${referenceText}`.trim();
}

function cleanOtherSection(value) {
  const text = String(value || '').trim();
  if (['(비워둠)', '비워둠', '없음'].includes(text)) return '';
  return text;
}

function parseDraftSections(text, references = [], chargeName = '') {
  return {
    purpose: defaultPurpose(chargeName),
    facts: extractSection(text, 4),
    reason: appendReferenceText(extractSection(text, 5), references),
    evidence: extractSection(text, 6),
    other: cleanOtherSection(extractSection(text, 7)),
  };
}

function composeComplaintText(originalText, sections) {
  const complainant = extractSection(originalText, 1);
  const accused = extractSection(originalText, 2);
  return [
    '고 소 장',
    '',
    '1. 고소인',
    complainant,
    '',
    '2. 피고소인',
    accused,
    '',
    '3. 고소취지',
    sections.purpose,
    '',
    '4. 범죄사실',
    sections.facts,
    '',
    '5. 고소이유',
    sections.reason,
    '',
    '6. 증거자료',
    sections.evidence,
    '',
    '7. 기타',
    sections.other,
  ].join('\n').trim();
}

export default function ResultPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const initialFormData = location.state?.formData || {};
  const selectedChargeName = location.state?.selectedChargeName || '';
  const selectedReferences = location.state?.selectedReferences || [];
  const factImprovementItems = location.state?.factImprovementItems || [];
  const reasonImprovementItems = location.state?.reasonImprovementItems || [];
  const [complaintText, setComplaintText] = useState(location.state?.complaint_text || '');
  const [missingFields, setMissingFields] = useState(location.state?.missing_fields || []);
  const [usedFallback, setUsedFallback] = useState(Boolean(location.state?.used_fallback));
  const [draftSections, setDraftSections] = useState(() => parseDraftSections(location.state?.complaint_text || '', selectedReferences, selectedChargeName));
  const [finalFields, setFinalFields] = useState({ ...EMPTY_FINAL_FIELDS, chargeName: selectedChargeName });
  const [usage, setUsage] = useState(location.state?.usage || null);
  const [finalizing, setFinalizing] = useState(false);
  const [downloadingPdf, setDownloadingPdf] = useState(false);
  const [error, setError] = useState('');

  const handleFinalChange = (e) => {
    const { name, value } = e.target;
    setFinalFields((prev) => ({ ...prev, [name]: value }));
  };

  const handleDraftChange = (e) => {
    const { name, value } = e.target;
    setDraftSections((prev) => ({ ...prev, [name]: value }));
  };

  const currentComplaintText = composeComplaintText(complaintText, draftSections);

  const buildPayload = () => ({
    complainant_name: initialFormData.complainantName || '',
    accused_name: initialFormData.accusedName || '',
    incident_date: initialFormData.incidentDate || '',
    incident_location: initialFormData.incidentLocation || '',
    incident_description: draftSections.facts || initialFormData.incidentDescription || '',
    evidence_summary: draftSections.evidence || initialFormData.evidenceSummary || '',
    requested_punishment: initialFormData.requestedPunishment || '',
    charge_name: finalFields.chargeName,
    legal_references: selectedReferences,
    complainant_rrn: finalFields.complainantRrn,
    complainant_address: finalFields.complainantAddress,
    complainant_job: finalFields.complainantJob,
    complainant_phone: finalFields.complainantPhone,
    accused_rrn: finalFields.accusedRrn,
    accused_address: finalFields.accusedAddress,
    accused_job: finalFields.accusedJob,
    accused_phone: finalFields.accusedPhone,
    accused_identifier: finalFields.accusedIdentifier,
    police_station: finalFields.policeStation,
    filing_date: finalFields.filingDate,
    attachments: finalFields.attachments.split('\n').map((item) => item.trim()).filter(Boolean),
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

  const handleDownloadPdf = async () => {
    setDownloadingPdf(true);
    setError('');

    try {
      const response = await fetch(`${API_BASE_URL}/api/complaints/pdf`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          payload: buildPayload(),
          complaint_text: currentComplaintText,
        }),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(formatApiError(data, 'PDF 생성에 실패했습니다.'));
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'complaint-draft.pdf';
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message || '알 수 없는 오류가 발생했습니다.');
    } finally {
      setDownloadingPdf(false);
    }
  };

  const handleFinalize = async () => {
    setFinalizing(true);
    setError('');

    try {
      const response = await fetch(`${API_BASE_URL}/api/complaints/generate-async?request_type=final`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(buildPayload()),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(formatApiError(data, '최종본 생성에 실패했습니다.'));
      setUsage({
        limit: data.usage_limit,
        used: data.usage_used,
        remaining: data.usage_remaining,
      });

      const job = await pollJob(data.job_id);

      setComplaintText(job.complaint_text);
      setDraftSections(parseDraftSections(job.complaint_text, selectedReferences, finalFields.chargeName || selectedChargeName));
      setMissingFields([]);
      setUsedFallback(false);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (err) {
      setError(err.message || '알 수 없는 오류가 발생했습니다.');
    } finally {
      setFinalizing(false);
    }
  };

  if (!complaintText) {
    return (
      <div className="min-h-screen bg-slate-50 px-4 py-12 text-center text-slate-900">
        <h1 className="text-2xl font-bold tracking-normal">생성된 고소장 초안이 없습니다</h1>
        <p className="mt-3 text-sm text-slate-500">생성 결과는 장기 보관되지 않습니다. 다시 작성이 필요하면 새 고소장을 생성해주세요.</p>
        <button onClick={() => navigate('/')} className="mt-6 rounded-lg bg-blue-700 px-5 py-3 font-bold text-white">작성 화면으로 이동</button>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 px-4 py-8 text-left text-slate-900">
      <main className="mx-auto max-w-6xl">
        <AuthBar />
        <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-sm font-semibold text-green-700">고소장 미리보기</p>
            <h1 className="mt-1 text-3xl font-bold tracking-normal text-slate-950">초안 확인 후 제출용 정보만 보완하세요</h1>
          </div>
          <div className="flex flex-wrap gap-2">
            <button onClick={handleDownloadPdf} disabled={downloadingPdf} className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-bold text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:bg-slate-400">
              {downloadingPdf ? 'PDF 생성 중...' : 'PDF 다운로드'}
            </button>
          </div>
        </div>

        {usedFallback && (
          <div className="mb-4 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            OPENAI_API_KEY가 없어 개발용 기본 초안으로 생성되었습니다. 환경변수 설정 후 백엔드를 재시작하면 gpt-4o-mini 결과를 사용합니다.
          </div>
        )}

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
          <section>
            <div className="space-y-4 rounded-lg border border-slate-200 bg-white p-6 shadow-sm md:p-8">
              <div>
                <p className="text-sm font-semibold text-slate-500">고 소 장</p>
                <h2 className="mt-1 text-xl font-bold text-slate-950">AI 초안 수정</h2>
                <p className="mt-2 text-sm leading-6 text-slate-500">고소취지, 범죄사실, 고소이유는 제출 전 사실관계에 맞게 직접 수정하세요.</p>
              </div>
              <DraftTextArea label="3. 고소취지" name="purpose" value={draftSections.purpose} onChange={handleDraftChange} rows={4} />
              <div>
                <DraftTextArea label="4. 범죄사실" name="facts" value={draftSections.facts} onChange={handleDraftChange} rows={9} helper="일시, 장소, 행위 방법, 피해 결과를 구체적으로 남겨주세요." />
                {factImprovementItems.length > 0 && (
                  <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-4 py-3">
                    <p className="text-sm font-bold text-amber-900">보완하면 더 좋아요</p>
                    <ul className="mt-2 space-y-1 text-sm leading-6 text-amber-900">
                      {factImprovementItems.map((item) => <li key={item}>- {item}</li>)}
                    </ul>
                  </div>
                )}
              </div>
              <div>
                <DraftTextArea label="5. 고소이유" name="reason" value={draftSections.reason} onChange={handleDraftChange} rows={8} helper="범행 경위, 정황, 고소하게 된 사유를 간략하고 명확하게 정리하세요." />
                {reasonImprovementItems.length > 0 && (
                  <div className="mt-3 rounded-md border border-blue-200 bg-blue-50 px-4 py-3">
                    <p className="text-sm font-bold text-blue-950">고소이유 보완 포인트</p>
                    <ul className="mt-2 space-y-1 text-sm leading-6 text-blue-950">
                      {reasonImprovementItems.map((item) => <li key={item}>- {item}</li>)}
                    </ul>
                  </div>
                )}
              </div>
              <DraftTextArea label="6. 증거자료" name="evidence" value={draftSections.evidence} onChange={handleDraftChange} rows={4} />
              <DraftTextArea label="7. 기타" name="other" value={draftSections.other} onChange={handleDraftChange} rows={4} helper="특별히 추가할 내용이 없으면 비워두세요." />
            </div>

            <p className="mt-5 whitespace-pre-line text-center text-xs leading-5 text-slate-500">
              {`본 문서는 AI가 작성한 초안입니다.
본 문서의 사용으로 발생하는 어떠한 법적 책임도 서비스 제공자는 지지 않으며,
제출 전 반드시 변호사 등 전문가의 검토를 받으세요.`}
            </p>
            <p className="mt-2 text-center text-xs leading-5 text-slate-500">
              생성 결과는 개인정보 보호를 위해 자동 삭제됩니다.
            </p>
          </section>

          <aside className="space-y-4">
            <div className="rounded-lg border border-blue-100 bg-blue-50 p-4">
              <h2 className="text-base font-bold text-blue-950">제출 전 보완하면 좋은 항목</h2>
              {usage && (
                <p className="mt-2 text-sm font-semibold text-blue-900">
                  오늘 남은 AI 요청 {usage.remaining}회 / {usage.limit}회
                </p>
              )}
              {missingFields.length > 0 ? (
                <ul className="mt-3 space-y-1 text-sm text-blue-900">
                  {missingFields.map((field) => <li key={field}>- {field}</li>)}
                </ul>
              ) : (
                <p className="mt-3 text-sm text-blue-900">필수 보완 항목이 대부분 채워졌습니다.</p>
              )}
            </div>

            <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
              <h2 className="text-base font-bold text-slate-950">제출용 정보 보완</h2>
              <p className="mt-1 text-xs leading-5 text-slate-500">모르는 항목은 비워두면 문서에는 미상으로 반영됩니다.</p>

              <div className="mt-4 space-y-3">
                <Field label="고소인 주민등록번호" name="complainantRrn" value={finalFields.complainantRrn} onChange={handleFinalChange} />
                <Field label="고소인 주소" name="complainantAddress" value={finalFields.complainantAddress} onChange={handleFinalChange} />
                <Field label="고소인 직업" name="complainantJob" value={finalFields.complainantJob} onChange={handleFinalChange} />
                <Field label="고소인 휴대폰 번호" name="complainantPhone" value={finalFields.complainantPhone} onChange={handleFinalChange} />
                <Field label="피고소인 주민등록번호" name="accusedRrn" value={finalFields.accusedRrn} onChange={handleFinalChange} />
                <Field label="피고소인 주소" name="accusedAddress" value={finalFields.accusedAddress} onChange={handleFinalChange} />
                <Field label="피고소인 직업" name="accusedJob" value={finalFields.accusedJob} onChange={handleFinalChange} />
                <Field label="피고소인 휴대폰 번호" name="accusedPhone" value={finalFields.accusedPhone} onChange={handleFinalChange} />
                <Field label="피고소인 기타사항" name="accusedIdentifier" value={finalFields.accusedIdentifier} onChange={handleFinalChange} />
                <Field label="제출 관서" name="policeStation" value={finalFields.policeStation} onChange={handleFinalChange} placeholder="예: 서울강남경찰서" />
                <Field label="제출일" name="filingDate" value={finalFields.filingDate} onChange={handleFinalChange} placeholder="예: 2026. 05. 10." />
                <label className="block">
                  <span className="mb-1 block text-sm font-semibold text-slate-700">첨부서류</span>
                  <textarea name="attachments" value={finalFields.attachments} onChange={handleFinalChange} rows={3} placeholder="예: 송금내역 사본, 온라인 캡처, 진단서" className="w-full resize-y rounded-md border border-slate-300 px-3 py-2 text-sm leading-6 outline-none transition focus:border-blue-600 focus:ring-2 focus:ring-blue-100" />
                </label>
              </div>

              {error && <div className="mt-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}

              <button onClick={handleFinalize} disabled={finalizing} className="mt-4 w-full rounded-lg bg-slate-900 px-4 py-3 text-sm font-bold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400">
                {finalizing ? 'AI가 문장을 다듬는 중...' : 'AI로 문장 다시 다듬기'}
              </button>
              <button onClick={() => navigate('/')} className="mt-2 w-full rounded-lg border border-slate-300 bg-white px-4 py-3 text-sm font-bold text-slate-700 hover:bg-slate-100">
                새 고소장 작성
              </button>
            </div>
          </aside>
        </div>
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

function DraftTextArea({ label, helper, ...props }) {
  return (
    <label className="block">
      <span className="mb-1 block text-base font-bold text-slate-900">{label}</span>
      {helper && <span className="mb-2 block text-xs leading-5 text-slate-500">{helper}</span>}
      <textarea {...props} className="w-full resize-y rounded-md border border-slate-300 px-3 py-2 font-serif text-sm leading-7 text-slate-900 outline-none transition focus:border-blue-600 focus:ring-2 focus:ring-blue-100" />
    </label>
  );
}

