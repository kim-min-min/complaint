import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import AuthBar from '../components/AuthBar';
import StepIndicator from '../components/StepIndicator';
import { clearDraft } from '../draftStorage';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

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
};

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

function defaultPurpose() {
  return '저는 피고소인의 위 행위에 대하여 고소하오니 철저히 수사하여 법에 따라 처벌하여 주시기 바랍니다.';
}

function formatReferenceText(references) {
  return (references || [])
    .map((item) => String(item || '').trim())
    .filter(Boolean)
    .map((item) => {
      const lines = item.split('\n').map((line) => line.trim()).filter(Boolean);
      const precedent = lines.find((line) => line.startsWith('판례:'));
      if (precedent) return `- ${precedent}`;
      return '';
    })
    .filter(Boolean)
    .join('\n');
}

function normalizeReferenceHeading(text) {
  return String(text || '')
    .replace(/\s*※?\s*참고판례\s*[:：]\s*/g, '\n\n※ 참고판례\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

function stripReferenceSection(text) {
  return normalizeReferenceHeading(text).split(/\n\s*※ 참고판례\s*\n/)[0].trim();
}

function appendReferenceText(reason, references) {
  const referenceText = formatReferenceText(references);
  const base = stripReferenceSection(reason);
  if (!referenceText) return base;
  return `${base}\n\n※ 참고판례\n${referenceText}`.trim();
}

function evidenceListText(items) {
  return (items || [])
    .map((item) => item.name?.trim())
    .filter(Boolean)
    .map((name, index) => `${index + 1}. ${name}`)
    .join('\n');
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result || '');
      resolve(result.includes(',') ? result.split(',').pop() : result);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function cleanOtherSection(value) {
  const text = String(value || '').trim();
  if (['(비워둠)', '비워둠', '없음'].includes(text)) return '';
  return text;
}

function parseDraftSections(text, references = []) {
  return {
    purpose: defaultPurpose(),
    facts: extractSection(text, 4),
    reason: appendReferenceText(extractSection(text, 5), references),
    other: cleanOtherSection(extractSection(text, 7)),
  };
}

function composeComplaintText(originalText, sections, evidenceText = '') {
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
    evidenceText,
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
  const [complaintText] = useState(location.state?.complaint_text || '');
  const [missingFields] = useState(location.state?.missing_fields || []);
  const [draftSections, setDraftSections] = useState(() => parseDraftSections(location.state?.complaint_text || '', selectedReferences));
  const [finalFields, setFinalFields] = useState({ ...EMPTY_FINAL_FIELDS, chargeName: selectedChargeName });
  const [evidenceItems, setEvidenceItems] = useState([]);
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

  const handleAddEvidence = () => {
    if (evidenceItems.length >= 10) {
      setError('증거자료는 최대 10개까지 첨부할 수 있습니다.');
      return;
    }
    setEvidenceItems((prev) => [...prev, {
      id: `${Date.now()}-${prev.length}`,
      name: '',
      filename: '',
      contentType: '',
      dataBase64: '',
    }]);
  };

  const handleEvidenceNameChange = (id, value) => {
    setEvidenceItems((prev) => prev.map((item) => (item.id === id ? { ...item, name: value } : item)));
  };

  const handleEvidenceFileChange = async (id, file) => {
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      setError('증거자료 이미지는 jpg, png, webp 등 이미지 파일만 첨부할 수 있습니다.');
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setError('이미지 1개당 최대 10MB까지 첨부할 수 있습니다.');
      return;
    }
    const dataBase64 = await fileToBase64(file);
    setEvidenceItems((prev) => prev.map((item) => (
      item.id === id
        ? {
            ...item,
            name: item.name || file.name.replace(/\.[^.]+$/, ''),
            filename: file.name,
            contentType: file.type,
            dataBase64,
          }
        : item
    )));
  };

  const handleRemoveEvidence = (id) => {
    setEvidenceItems((prev) => prev.filter((item) => item.id !== id));
  };

  const evidenceText = evidenceListText(evidenceItems);
  const currentComplaintText = composeComplaintText(complaintText, draftSections, evidenceText);

  const buildPayload = () => ({
    complainant_name: initialFormData.complainantName || '',
    accused_name: initialFormData.accusedName || '',
    incident_date: initialFormData.incidentDate || '',
    incident_location: initialFormData.incidentLocation || '',
    incident_description: draftSections.facts || initialFormData.incidentDescription || '',
    evidence_summary: evidenceText,
    requested_punishment: '',
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
    attachments: evidenceItems.map((item) => item.name.trim()).filter(Boolean),
    evidence_attachments: evidenceItems
      .filter((item) => item.name.trim() && item.dataBase64)
      .map((item) => ({
        name: item.name.trim(),
        filename: item.filename,
        content_type: item.contentType,
        data_base64: item.dataBase64,
      })),
  });

  useEffect(() => {
    let ignore = false;

    async function checkAuth() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
          credentials: 'include',
        });
        if (!ignore && response.status === 401) navigate('/login');
      } catch {
        // Result edits can stay visible even if a transient auth check fails.
      }
    }

    checkAuth();
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

  if (!complaintText) {
    return (
      <div className="min-h-screen bg-slate-50 px-4 py-12 text-center text-slate-900">
        <h1 className="text-2xl font-bold tracking-normal">생성된 고소장 초안이 없습니다</h1>
        <p className="mt-3 text-sm text-slate-500">생성 결과는 장기 보관되지 않습니다. 다시 작성이 필요하면 새 고소장을 생성해주세요.</p>
        <button onClick={() => { clearDraft(); navigate('/'); }} className="mt-6 rounded-lg bg-blue-700 px-5 py-3 font-bold text-white">작성 화면으로 이동</button>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 px-4 py-8 text-left text-slate-900">
      <main className="mx-auto max-w-6xl">
        <AuthBar />
        <StepIndicator current={3} />
        <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-sm font-semibold text-green-700">고소장 미리보기</p>
            <h1 className="mt-1 text-3xl font-bold tracking-normal text-slate-950">초안을 확인하고 제출 정보를 채워주세요</h1>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
          <section>
            <div className="space-y-4 rounded-lg border border-slate-200 bg-white p-6 shadow-sm md:p-8">
              <div>
                <p className="text-sm font-semibold text-slate-500">고 소 장</p>
                <h2 className="mt-1 text-xl font-bold text-slate-950">AI 초안 수정</h2>
                <p className="mt-2 text-sm leading-6 text-slate-500">고소취지, 범죄사실, 고소이유는 제출 전 본인이 직접 진술하는 문장으로 확인하세요.</p>
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
                <DraftTextArea label="5. 고소이유" name="reason" value={draftSections.reason} onChange={handleDraftChange} rows={8} helper="범행 경위, 정황, 피해 내용, 고소하게 된 이유를 본인이 겪은 사실 중심으로 정리하세요." />
                {reasonImprovementItems.length > 0 && (
                  <div className="mt-3 rounded-md border border-blue-200 bg-blue-50 px-4 py-3">
                    <p className="text-sm font-bold text-blue-950">고소이유 보완 포인트</p>
                    <ul className="mt-2 space-y-1 text-sm leading-6 text-blue-950">
                      {reasonImprovementItems.map((item) => <li key={item}>- {item}</li>)}
                    </ul>
                  </div>
                )}
              </div>
              <EvidenceAttachments
                items={evidenceItems}
                onAdd={handleAddEvidence}
                onNameChange={handleEvidenceNameChange}
                onFileChange={handleEvidenceFileChange}
                onRemove={handleRemoveEvidence}
              />
              <DraftTextArea label="7. 기타" name="other" value={draftSections.other} onChange={handleDraftChange} rows={4} helper="특별히 추가할 내용이 없으면 비워두세요." />
            </div>
          </section>

          <aside className="space-y-4">
            <div className="rounded-lg border border-blue-100 bg-blue-50 p-4">
              <h2 className="text-base font-bold text-blue-950">제출 전 보완하면 좋은 항목</h2>
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
              </div>

              {error && <div className="mt-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}

              <button onClick={handleDownloadPdf} disabled={downloadingPdf} className="mt-4 w-full rounded-lg bg-slate-900 px-4 py-3 text-sm font-bold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400">
                {downloadingPdf ? 'PDF 생성 중...' : 'PDF 다운로드'}
              </button>
              <button onClick={() => { clearDraft(); navigate('/'); }} className="mt-2 w-full rounded-lg border border-slate-300 bg-white px-4 py-3 text-sm font-bold text-slate-700 hover:bg-slate-100">
                새 고소장 작성
              </button>
            </div>
          </aside>
        </div>
        <div className="mt-8 rounded-lg border border-slate-200 bg-white px-5 py-4 text-left text-xs leading-6 text-slate-500 shadow-sm">
          <p>본 문서는 AI가 작성한 초안입니다. 본 문서의 사용으로 발생하는 법적 책임은 서비스 제공자가 지지 않습니다.</p>
          <p>제출 전 반드시 변호사 등 전문가의 검토를 받으세요. 생성 결과는 개인정보 보호를 위해 자동 삭제됩니다.</p>
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

function EvidenceAttachments({ items, onAdd, onNameChange, onFileChange, onRemove }) {
  return (
    <section className="block">
      <div className="mb-2 flex items-center justify-between gap-3">
        <div>
          <h3 className="text-base font-bold text-slate-900">6. 증거자료</h3>
          <p className="mt-1 text-xs leading-5 text-slate-500">제출할 증거의 이름을 적고 이미지를 첨부하세요. PDF에는 증거목록과 별지 이미지가 반영됩니다.</p>
        </div>
        <button type="button" onClick={onAdd} className="shrink-0 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-bold text-slate-700 hover:bg-slate-100">
          추가
        </button>
      </div>

      {items.length === 0 ? (
        <div className="rounded-md border border-dashed border-slate-300 bg-slate-50 px-4 py-5 text-sm text-slate-500">
          첨부할 증거자료가 있으면 추가 버튼을 눌러 등록하세요.
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((item, index) => (
            <div key={item.id} className="rounded-md border border-slate-200 bg-slate-50 p-4">
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm font-bold text-slate-700">증거 {index + 1}</span>
                <button type="button" onClick={() => onRemove(item.id)} className="text-sm font-semibold text-red-600 hover:text-red-700">
                  삭제
                </button>
              </div>
              <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-[minmax(0,1fr)_220px]">
                <label className="block">
                  <span className="mb-1 block text-sm font-semibold text-slate-700">증거명</span>
                  <input
                    value={item.name}
                    onChange={(event) => onNameChange(item.id, event.target.value)}
                    placeholder="예: 송금내역, 채팅내역, CCTV 캡처"
                    className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-blue-600 focus:ring-2 focus:ring-blue-100"
                  />
                </label>
                <label className="block">
                  <span className="mb-1 block text-sm font-semibold text-slate-700">이미지 첨부</span>
                  <span className="inline-flex cursor-pointer rounded-md bg-slate-900 px-3 py-2 text-sm font-bold text-white hover:bg-slate-800">
                    파일 선택
                  </span>
                  <input
                    type="file"
                    accept="image/*"
                    onChange={(event) => onFileChange(item.id, event.target.files?.[0])}
                    className="sr-only"
                  />
                </label>
              </div>
              {item.filename && <p className="mt-2 text-xs text-slate-500">첨부됨: {item.filename}</p>}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

