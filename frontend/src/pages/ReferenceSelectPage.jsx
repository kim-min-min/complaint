import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import AuthBar from '../components/AuthBar';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';
const POLL_INTERVAL_MS = 2000;
const POLL_TIMEOUT_MS = 120000;
const referenceSearchCache = new Map();

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
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

function formatApiError(data, fallback = '고소장 생성에 실패했습니다.') {
  const detail = data?.detail;
  if (Array.isArray(detail)) return detail.map((item) => item?.msg).filter(Boolean).join('\n') || fallback;
  if (typeof detail === 'string') return detail;
  if (detail && typeof detail === 'object') return detail.message || JSON.stringify(detail);
  return fallback;
}

function referenceText(reference) {
  return `${reference.title}: ${reference.summary}`;
}

function buildPayload(formData, selectedCharge, selectedReferences) {
  return {
    complainant_name: formData.complainantName,
    accused_name: formData.accusedName,
    incident_date: formData.incidentDate,
    incident_location: formData.incidentLocation,
    incident_description: formData.incidentDescription,
    evidence_summary: formData.evidenceSummary,
    requested_punishment: formData.requestedPunishment,
    charge_name: selectedCharge,
    legal_references: selectedReferences,
  };
}

export default function ReferenceSelectPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const formData = location.state?.formData;
  const [candidates, setCandidates] = useState([]);
  const [selectedChargeId, setSelectedChargeId] = useState('');
  const [selectedReferences, setSelectedReferences] = useState([]);
  const [usage, setUsage] = useState(location.state?.usage || null);
  const [searchKeywords, setSearchKeywords] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [factImprovementItems, setFactImprovementItems] = useState([]);
  const [reasonImprovementItems, setReasonImprovementItems] = useState([]);
  const [isMeaningfulCase, setIsMeaningfulCase] = useState(true);
  const [invalidReason, setInvalidReason] = useState('');
  const [loadingReferences, setLoadingReferences] = useState(Boolean(formData));
  const [submitting, setSubmitting] = useState(false);
  const [statusMessage, setStatusMessage] = useState('');
  const [error, setError] = useState('');

  const selectedCharge = candidates.find((candidate) => candidate.id === selectedChargeId);
  const precedents = (selectedCharge?.references || []).slice(0, 3);
  const canGenerate = isMeaningfulCase && Boolean(selectedCharge);

  useEffect(() => {
    if (!formData) return;
    let cancelled = false;

    async function loadReferences() {
      setLoadingReferences(true);
      setError('');
      try {
        const requestBody = {
          complainant_name: formData.complainantName,
          accused_name: formData.accusedName,
          incident_date: formData.incidentDate,
          incident_location: formData.incidentLocation,
          incident_description: formData.incidentDescription,
          evidence_summary: formData.evidenceSummary,
          requested_punishment: formData.requestedPunishment,
        };
        const cacheKey = JSON.stringify(requestBody);
        if (!referenceSearchCache.has(cacheKey)) {
          referenceSearchCache.set(cacheKey, fetch(`${API_BASE_URL}/api/references/search`, {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody),
          }).then(async (response) => {
            const data = await response.json();
            return { response, data };
          }));
        }

        const { response, data } = await referenceSearchCache.get(cacheKey);
        if (cancelled) return;
        if (response.status === 401) {
          navigate('/login');
          return;
        }
        if (!response.ok) throw new Error(formatApiError(data, '참고자료 조회에 실패했습니다.'));

        const nextCandidates = data.candidates || [];
        setCandidates(nextCandidates);
        setSelectedChargeId(nextCandidates[0]?.id || '');
        setSelectedReferences([]);
        setSearchKeywords(data.search_keywords || []);
        setSearchQuery(data.search_query || '');
        setFactImprovementItems(data.fact_improvement_items || []);
        setReasonImprovementItems(data.reason_improvement_items || []);
        setIsMeaningfulCase(data.is_meaningful_case !== false);
        setInvalidReason(data.invalid_reason || '');
        setUsage({
          limit: data.usage_limit,
          used: data.usage_used,
          remaining: data.usage_remaining,
        });
      } catch (err) {
        if (!cancelled) setError(err.message || '참고자료 조회 중 오류가 발생했습니다.');
      } finally {
        if (!cancelled) setLoadingReferences(false);
      }
    }

    loadReferences();
    return () => {
      cancelled = true;
    };
  }, [formData, navigate]);

  if (!formData) {
    return (
      <div className="min-h-screen bg-slate-50 px-4 py-12 text-center text-slate-900">
        <h1 className="text-2xl font-bold tracking-normal">입력된 사건 내용이 없습니다</h1>
        <button onClick={() => navigate('/')} className="mt-6 rounded-lg bg-blue-700 px-5 py-3 font-bold text-white">작성 화면으로 이동</button>
      </div>
    );
  }

  const toggleReference = (reference) => {
    const text = referenceText(reference);
    setSelectedReferences((prev) => (
      prev.includes(text)
        ? prev.filter((item) => item !== text)
        : [...prev, text]
    ));
  };

  const handleGenerate = async () => {
    if (!canGenerate) return;
    setSubmitting(true);
    setError('');
    setStatusMessage('작업을 접수하고 있습니다.');

    try {
      const payload = buildPayload(formData, selectedCharge?.label || '', selectedReferences);
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
      if (!response.ok) throw new Error(formatApiError(data));

      const job = await pollJob(data.job_id, setStatusMessage);
      navigate('/result', {
        state: {
          ...job,
          formData,
          selectedChargeName: selectedCharge?.label || '',
          selectedReferences,
          factImprovementItems,
          reasonImprovementItems,
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
    <div className="min-h-screen bg-slate-50 px-4 py-8 text-left text-slate-900">
      <main className="mx-auto max-w-4xl">
        <AuthBar />
        <header className="mb-6">
          <p className="text-sm font-semibold text-blue-700">참고자료 선택</p>
          <h1 className="mt-2 text-3xl font-bold tracking-normal text-slate-950">초안에 반영할 자료를 직접 선택하세요</h1>
          <p className="mt-3 text-sm leading-6 text-slate-600">죄명 후보는 AI가 참고용으로 정리하고, 판례 후보는 별도 검색 결과로 보여드립니다. 최종 반영 여부는 사용자가 직접 선택합니다.</p>
          {usage && (
            <p className="mt-3 inline-flex rounded-md border border-blue-100 bg-blue-50 px-3 py-2 text-sm font-semibold text-blue-800">
              오늘 남은 AI 요청 {usage.remaining}회 / {usage.limit}회
            </p>
          )}
        </header>

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,1fr)_320px]">
          <section className="space-y-5">
            {loadingReferences && (
              <div className="rounded-lg border border-blue-200 bg-blue-50 p-5 text-sm font-semibold text-blue-800">
                사건 내용을 바탕으로 죄명 후보와 참고자료를 불러오는 중입니다.
              </div>
            )}
            {!loadingReferences && !isMeaningfulCase && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-5 text-sm leading-6 text-amber-900">
                <p className="font-bold">입력 내용만으로는 고소장 초안을 작성하기 어렵습니다.</p>
                <p className="mt-1">{invalidReason || '누가, 언제, 어디서, 어떤 행위를 했는지 구체적으로 입력해주세요.'}</p>
              </div>
            )}
            <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="text-lg font-bold text-slate-950">참고 가능한 죄명 후보</h2>
              <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
                {candidates.map((candidate) => (
                  <label key={candidate.id} className={`flex cursor-pointer items-start gap-3 rounded-lg border p-4 transition ${selectedChargeId === candidate.id ? 'border-blue-600 bg-blue-50' : 'border-slate-200 bg-white hover:bg-slate-50'}`}>
                    <input
                      type="radio"
                      name="charge"
                      checked={selectedChargeId === candidate.id}
                      onChange={() => {
                        setSelectedChargeId(candidate.id);
                        setSelectedReferences([]);
                      }}
                      className="mt-1 h-4 w-4"
                    />
                    <span>
                      <span className="block font-bold text-slate-900">{candidate.label}</span>
                      {candidate.reason && <span className="mt-1 block text-xs leading-5 text-slate-500">{candidate.reason}</span>}
                    </span>
                  </label>
                ))}
                {!loadingReferences && candidates.length === 0 && (
                  <p className="text-sm text-slate-500">표시할 죄명 후보가 없습니다. 입력 내용을 조금 더 자세히 적어주세요.</p>
                )}
              </div>
            </div>

            <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="text-lg font-bold text-slate-950">관련 판례 참고자료</h2>
              <p className="mt-1 text-xs leading-5 text-slate-500">사건 내용과 가까운 판례를 최대 3개까지 보여드립니다.</p>
              <div className="mt-4 space-y-3">
                {precedents.map((reference) => {
                  const text = referenceText(reference);
                  return (
                    <label key={reference.id} className={`flex cursor-pointer gap-3 rounded-lg border p-4 transition ${selectedReferences.includes(text) ? 'border-blue-600 bg-blue-50' : 'border-slate-200 bg-white hover:bg-slate-50'}`}>
                      <input
                        type="checkbox"
                        checked={selectedReferences.includes(text)}
                        onChange={() => toggleReference(reference)}
                        className="mt-1 h-4 w-4"
                      />
                      <span className="min-w-0 text-sm leading-6 text-slate-800">
                        <span className="block break-keep font-bold leading-6">{reference.title}</span>
                        <span className="mt-2 block whitespace-pre-wrap break-keep text-slate-600">{reference.summary}</span>
                      </span>
                    </label>
                  );
                })}
                {!loadingReferences && precedents.length === 0 && (
                  <p className="text-sm text-slate-500">선택한 죄명에 연결된 참고자료가 없습니다.</p>
                )}
              </div>
            </div>
          </section>

          <aside className="space-y-4">
            <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="text-base font-bold text-slate-950">사건 요약</h2>
              <dl className="mt-3 space-y-3 text-sm">
                <div>
                  <dt className="font-semibold text-slate-500">고소인</dt>
                  <dd className="mt-1 text-slate-900">{formData.complainantName}</dd>
                </div>
                <div>
                  <dt className="font-semibold text-slate-500">상대방</dt>
                  <dd className="mt-1 text-slate-900">{formData.accusedName}</dd>
                </div>
                <div>
                  <dt className="font-semibold text-slate-500">사건 내용</dt>
                  <dd className="mt-1 line-clamp-6 whitespace-pre-wrap text-slate-900">{formData.incidentDescription}</dd>
                </div>
              </dl>
            </div>

            {(searchQuery || searchKeywords.length > 0) && (
              <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
                <h2 className="text-base font-bold text-slate-950">검색용 정리</h2>
                {searchQuery && <p className="mt-2 text-sm leading-6 text-slate-700">{searchQuery}</p>}
                {searchKeywords.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {searchKeywords.map((keyword) => (
                      <span key={keyword} className="rounded-md bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-700">{keyword}</span>
                    ))}
                  </div>
                )}
              </div>
            )}

            {error && <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
            {statusMessage && !error && <div className="rounded-md border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800">{statusMessage}</div>}

            <button onClick={handleGenerate} disabled={submitting || loadingReferences || !canGenerate} className="w-full rounded-lg bg-blue-700 px-4 py-3 text-base font-bold text-white transition hover:bg-blue-800 disabled:cursor-not-allowed disabled:bg-slate-400">
              {submitting ? 'AI가 초안 작성 중...' : '선택한 참고자료로 초안 작성'}
            </button>
            <button
              type="button"
              onClick={() => navigate('/', { state: { formData } })}
              className="w-full rounded-lg border border-slate-300 bg-white px-4 py-3 text-base font-bold text-slate-700 transition hover:bg-slate-100"
            >
              돌아가기
            </button>
          </aside>
        </div>
      </main>
    </div>
  );
}
