import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import AuthBar from '../components/AuthBar';
import StepIndicator from '../components/StepIndicator';
import { readCachedResult, readDraft, writeCachedResult, writeDraft } from '../draftStorage';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';
const POLL_INTERVAL_MS = 2000;
const POLL_TIMEOUT_MS = 120000;
const analysisCache = new Map();

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function formatApiError(data, fallback = '요청 처리에 실패했습니다.') {
  const detail = data?.detail;
  if (Array.isArray(detail)) return detail.map((item) => item?.msg).filter(Boolean).join('\n') || fallback;
  if (typeof detail === 'string') return detail;
  if (detail && typeof detail === 'object') return detail.message || JSON.stringify(detail);
  return fallback;
}

async function pollJob(jobId, onStatus) {
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
    onStatus(data.status === 'queued' ? '대기열에서 순서를 기다리는 중입니다.' : 'AI가 초안을 작성 중입니다.');
  }
  throw new Error('생성 시간이 오래 걸리고 있습니다. 잠시 후 다시 시도해주세요.');
}

async function pollReferenceJob(jobId, onStatus) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < POLL_TIMEOUT_MS) {
    await wait(POLL_INTERVAL_MS);
    const response = await fetch(`${API_BASE_URL}/api/references/jobs/${jobId}`, {
      credentials: 'include',
    });
    const data = await response.json();
    if (!response.ok) throw new Error(formatApiError(data, '작업 상태 조회에 실패했습니다.'));
    if (data.status === 'completed') return data.result;
    if (data.status === 'failed') throw new Error(data.error_message || '사건 분석에 실패했습니다.');
    onStatus(data.status === 'queued' ? '대기열에서 순서를 기다리는 중입니다.' : '유사 판례를 분석하고 있습니다.');
  }
  throw new Error('분석 시간이 오래 걸리고 있습니다. 잠시 후 다시 시도해주세요.');
}

function toRequestBody(formData) {
  return {
    complainant_name: formData.complainantName,
    accused_name: formData.accusedName,
    incident_date: formData.incidentDate,
    incident_location: formData.incidentLocation,
    incident_description: formData.incidentDescription,
    evidence_summary: formData.evidenceSummary,
    requested_punishment: '',
  };
}

function coreReferenceText(precedent, answer) {
  if (!precedent) return '';
  return [
    '고소이유 보완',
    precedent.question ? `질문: ${precedent.question}` : '',
    answer?.trim() ? `답변: ${answer.trim()}` : '',
    '',
    '참고판례',
    `판례: ${precedent.title}`,
    precedent.issue ? `쟁점: ${precedent.issue}` : '',
    precedent.summary ? `판례 요약: ${precedent.summary}` : '',
    precedent.source_url ? `원문: ${precedent.source_url}` : '',
    precedent.how_to_use_in_complaint ? `고소장 반영 방향: ${precedent.how_to_use_in_complaint}` : '',
  ].filter(Boolean).join('\n');
}

function referenceKey(precedent) {
  return precedent?.id || precedent?.title || '';
}

function selectedReferenceTexts(precedents, selectedIds, answers) {
  return (precedents || [])
    .filter((precedent) => selectedIds.includes(referenceKey(precedent)))
    .map((precedent) => coreReferenceText(precedent, answers[referenceKey(precedent)] || ''))
    .filter(Boolean);
}

function selectedChargeText(precedents, selectedIds) {
  const charges = [];
  for (const precedent of precedents || []) {
    if (!selectedIds.includes(referenceKey(precedent))) continue;
    const charge = (precedent.charge || '').trim();
    if (charge && !charges.includes(charge)) charges.push(charge);
  }
  return charges.join(', ');
}

export default function AnalysisPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [draftSnapshot] = useState(() => readDraft());
  const formData = location.state?.formData || draftSnapshot.formData;
  const [corePrecedents, setCorePrecedents] = useState([]);
  const [selectedPrecedentIds, setSelectedPrecedentIds] = useState(draftSnapshot.selectedPrecedentIds || []);
  const [coreAnswers, setCoreAnswers] = useState(draftSnapshot.issueAnswers || {});
  const [usage, setUsage] = useState(location.state?.usage || null);
  const [isMeaningfulCase, setIsMeaningfulCase] = useState(true);
  const [invalidReason, setInvalidReason] = useState('');
  const [loading, setLoading] = useState(Boolean(formData));
  const [submitting, setSubmitting] = useState(false);
  const [statusMessage, setStatusMessage] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    if (!formData) return;
    let cancelled = false;

    async function loadAnalysis() {
      setLoading(true);
      setError('');
      try {
        const requestBody = toRequestBody(formData);
        const cacheKey = JSON.stringify(requestBody);
        const cachedData = readCachedResult('issueResult', cacheKey);
        if (cachedData) {
          analysisCache.set(cacheKey, Promise.resolve(cachedData));
        } else if (!analysisCache.has(cacheKey)) {
          analysisCache.set(cacheKey, fetch(`${API_BASE_URL}/api/references/analyze`, {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody),
          }).then(async (response) => {
            const data = await response.json();
            if (response.status === 401) return { unauthorized: true };
            if (!response.ok) throw new Error(formatApiError(data, '사건 분석에 실패했습니다.'));
            return pollReferenceJob(data.job_id, setStatusMessage);
          }));
        }

        const data = await analysisCache.get(cacheKey);
        if (cancelled) return;
        if (data?.unauthorized) {
          navigate('/login');
          return;
        }
        if (!cachedData) writeCachedResult('issueResult', cacheKey, data);

        setIsMeaningfulCase(data.is_meaningful_case !== false);
        setInvalidReason(data.invalid_reason || '');
        const precedents = data.similar_precedents?.length ? data.similar_precedents : (data.similar_precedent ? [data.similar_precedent] : []);
        setCorePrecedents(precedents);
        setSelectedPrecedentIds((prev) => {
          const validIds = precedents.map(referenceKey).filter(Boolean);
          const prevValid = prev.filter((id) => validIds.includes(id));
          if (prevValid.length) return prevValid;
          const savedValid = (draftSnapshot.selectedPrecedentIds || []).filter((id) => validIds.includes(id));
          if (savedValid.length) return savedValid;
          return validIds;
        });
        setCoreAnswers((prev) => prev || draftSnapshot.issueAnswers || {});
        setUsage({
          limit: data.usage_limit,
          used: data.usage_used,
          remaining: data.usage_remaining,
        });
      } catch (err) {
        if (!cancelled) setError(err.message || '사건 분석 중 오류가 발생했습니다.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadAnalysis();
    return () => {
      cancelled = true;
    };
  }, [formData, navigate]);

  useEffect(() => {
    if (!formData) return;
    writeDraft({ formData, issueAnswers: coreAnswers, selectedPrecedentIds });
  }, [formData, coreAnswers, selectedPrecedentIds]);

  if (!formData) {
    return (
      <div className="min-h-screen bg-[#f7f8f5] px-4 py-12 text-center text-[#111111]">
        <h1 className="text-2xl font-semibold tracking-normal">입력된 사건 내용이 없습니다</h1>
        <button onClick={() => navigate('/form')} className="mt-6 rounded-full bg-[#111111] px-5 py-3 font-semibold text-white">작성 화면으로 이동</button>
      </div>
    );
  }

  const selectedReferences = selectedReferenceTexts(corePrecedents, selectedPrecedentIds, coreAnswers);
  const selectedChargeName = selectedChargeText(corePrecedents, selectedPrecedentIds);
  const canGenerate = isMeaningfulCase && !loading && !submitting && (!corePrecedents.length || selectedPrecedentIds.length > 0);

  const handleGenerate = async () => {
    if (!canGenerate) return;
    setSubmitting(true);
    setError('');
    setStatusMessage('작업을 접수하고 있습니다.');

    try {
      writeDraft({ formData, issueAnswers: coreAnswers, selectedPrecedentIds });
      const payload = {
        ...toRequestBody(formData),
        charge_name: selectedChargeName,
        legal_references: selectedReferences,
      };
      const response = await fetch(`${API_BASE_URL}/api/complaints/generate-async`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (response.status === 401) {
        navigate('/login');
        return;
      }
      if (!response.ok) throw new Error(formatApiError(data, '고소장 생성에 실패했습니다.'));

      const job = await pollJob(data.job_id, setStatusMessage);
      navigate('/result', {
        state: {
          ...job,
          formData,
          selectedChargeName,
          selectedReferences,
          factImprovementItems: [],
          reasonImprovementItems: [],
          usage: {
            limit: data.usage_limit,
            used: data.usage_used,
            remaining: data.usage_remaining,
          },
        },
      });
    } catch (err) {
      setError(err.message || '알 수 없는 오류가 발생했습니다.');
    } finally {
      setSubmitting(false);
      setStatusMessage('');
    }
  };

  return (
    <div className="min-h-screen bg-[#f7f8f5] px-4 py-8 text-left text-[#111111]">
      <main className="mx-auto max-w-4xl">
        <AuthBar />
        <StepIndicator current={2} />
        <header className="mb-7">
          <p className="text-sm font-semibold text-[#50534e]">유사 판례</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-normal text-[#111111]">고소장에 반영할 판례를 선택해주세요</h1>
          <p className="mt-3 text-sm leading-6 text-[#5f625d]">입력한 사건과 가까운 판례를 찾았습니다. 참고할 판례를 선택하고, 필요한 내용만 보완해주세요.</p>
          {usage && (
            <p className="mt-3 inline-flex rounded-full border border-[#d7d9d2] bg-[#eef2e8] px-4 py-2 text-sm font-semibold text-[#3d4a35]">
              오늘 남은 AI 요청 {usage.remaining}회 / {usage.limit}회
            </p>
          )}
        </header>

        {loading && (
          <div className="rounded-[6px] border border-[#d7d9d2] bg-[#fbfbf8] p-5 text-sm font-semibold text-[#3d4a35]">
            입력한 사건 내용을 바탕으로 가까운 판례를 찾고 있습니다.
          </div>
        )}

        {!loading && !isMeaningfulCase && (
          <div className="rounded-[6px] border border-amber-200 bg-amber-50 p-5 text-sm leading-6 text-amber-900">
            <p className="font-semibold">입력 내용만으로는 고소장 초안을 작성하기 어렵습니다.</p>
            <p className="mt-1">{invalidReason || '누가, 언제, 어디서, 어떤 행위를 했는지 구체적으로 입력해주세요.'}</p>
          </div>
        )}

        {!loading && isMeaningfulCase && (
          <>
            {corePrecedents.length ? (
              <section className="space-y-4">
                {corePrecedents.map((precedent) => {
                  const id = referenceKey(precedent);
                  const selected = selectedPrecedentIds.includes(id);
                  return (
                    <article key={id} className={`rounded-[6px] border bg-[#fbfbf8] p-5 shadow-[0_18px_44px_rgba(30,32,27,0.06)] ${selected ? 'border-[#111111]' : 'border-[#d7d9d2]'}`}>
                      <label className="flex items-start gap-3">
                        <input
                          type="checkbox"
                          checked={selected}
                          onChange={(event) => {
                            setSelectedPrecedentIds((prev) => {
                              if (event.target.checked) return [...new Set([...prev, id])];
                              return prev.filter((item) => item !== id);
                            });
                          }}
                          className="mt-1 h-4 w-4 accent-[#111111]"
                        />
                        <span>
                          <span className="block text-xl font-semibold text-[#111111]">유사 판례</span>
                          <span className="mt-2 block text-sm leading-6 text-[#5f625d]">선택한 판례는 고소이유에 참고자료로 반영됩니다.</span>
                        </span>
                      </label>

                      {precedent.question && (
                        <>
                          <p className="mt-4 text-base font-semibold leading-7 text-[#111111]">{precedent.question}</p>
                          <textarea
                            value={coreAnswers[id] || ''}
                            onChange={(event) => setCoreAnswers((prev) => ({ ...prev, [id]: event.target.value }))}
                            rows={5}
                            placeholder="답변을 입력하세요"
                            className="mt-4 w-full resize-y rounded-[4px] border border-[#d7d9d2] bg-white px-3 py-2 text-sm leading-6 text-[#111111] outline-none transition placeholder:text-[#8b8e86] focus:border-[#111111] focus:ring-2 focus:ring-[#e9efe3]"
                          />
                        </>
                      )}

                      <div className="mt-5 rounded-[4px] border border-[#e1e2dd] bg-white p-4">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="text-sm font-semibold text-[#6b6e66]">참고 판례</p>
                          {precedent.source_url && (
                            <a href={precedent.source_url} target="_blank" rel="noreferrer" className="text-sm font-semibold text-[#3d4a35] underline underline-offset-4">
                              원문 보기
                            </a>
                          )}
                        </div>
                        <p className="mt-2 text-base font-semibold leading-6 text-[#111111]">{precedent.title}</p>

                        {precedent.issue && (
                          <div className="mt-4">
                            <p className="text-xs font-semibold text-[#6b6e66]">쟁점</p>
                            <p className="mt-2 whitespace-pre-wrap break-keep text-sm leading-6 text-[#22231f]">{precedent.issue}</p>
                          </div>
                        )}

                        {precedent.summary && (
                          <div className="mt-4">
                            <p className="text-xs font-semibold text-[#6b6e66]">판례 요약</p>
                            <p className="mt-2 whitespace-pre-wrap break-keep text-sm leading-6 text-[#5f625d]">{precedent.summary}</p>
                          </div>
                        )}
                      </div>
                    </article>
                  );
                })}
              </section>
            ) : (
              <div className="rounded-[6px] border border-[#d7d9d2] bg-[#fbfbf8] p-5 text-sm leading-6 text-[#5f625d]">
                가까운 판례를 찾지 못했습니다. 입력한 내용만으로 초안을 작성할 수 있습니다.
              </div>
            )}

            <div className="mt-5 space-y-3">
              {error && <div className="rounded-[4px] border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
              {statusMessage && !error && <div className="rounded-[4px] border border-[#cbd8bd] bg-[#eef2e8] px-4 py-3 text-sm text-[#3d4a35]">{statusMessage}</div>}
              <button onClick={handleGenerate} disabled={!canGenerate} className="w-full rounded-full bg-[#111111] px-4 py-3 text-base font-semibold text-white transition hover:bg-[#30302d] disabled:cursor-not-allowed disabled:bg-[#9a9d96]">
                {submitting ? 'AI가 초안 작성 중...' : '고소장 초안 작성'}
              </button>
              <button
                type="button"
                onClick={() => navigate('/form', { state: { formData } })}
                className="w-full rounded-full border border-[#d7d9d2] bg-white px-4 py-3 text-base font-semibold text-[#32342f] transition hover:bg-[#eef2e8]"
              >
                돌아가기
              </button>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
