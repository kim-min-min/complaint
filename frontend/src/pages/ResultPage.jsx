import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

export default function ResultPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [loading, setLoading] = useState(true);
  const [complaintText, setComplaintText] = useState("");

  // 폼에서 넘어온 데이터 (없을 경우를 대비해 예외 처리)
  const formData = location.state?.formData || {};

  useEffect(() => {
    // MVP 단계에서는 2초 후 결과가 나오는 것처럼 시뮬레이션
    // 나중에 여기서 FastAPI의 결과를 가져오는 폴링(Polling) 로직이 들어갑니다.
    const timer = setTimeout(() => {
      const mockResult = `
[고 소 장]

고 소 인 : ${formData.complainantName || '홍길동'}
피고소인 : ${formData.accusedName || '성명불상'}

1. 고소 취지
고소인은 피고소인을 정보통신망법 위반(사기) 혐의로 고소하오니, 철저히 조사하여 엄벌에 처해 주시기 바랍니다.

2. 범죄 사실
피고소인은 ${formData.incidentDate || '최근'}경 ${formData.incidentLocation || '불상의 장소'}에서 다음과 같은 행위를 하였습니다.
${formData.incidentDescription || '입력된 피해 내용이 여기에 들어갑니다.'}

3. 증거 자료
현재 고소인이 확보한 증거는 다음과 같습니다.
- ${formData.evidenceSummary || '입력된 증거 내역'}

4. 결어
고소인은 위와 같은 피해 사실에 대하여 강력한 처벌을 원하며, 추후 수사 과정에서 필요한 자료 제출에 적극 협조하겠습니다.
      `;
      setComplaintText(mockResult.trim());
      setLoading(false);
    }, 2500);

    return () => clearTimeout(timer);
  }, [formData]);

  const handleCopy = () => {
    navigator.clipboard.writeText(complaintText);
    alert("고소장 내용이 복사되었습니다!");
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center p-4">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4"></div>
        <h2 className="text-xl font-bold text-gray-800">AI가 고소장을 작성 중입니다...</h2>
        <p className="text-gray-500 mt-2 text-center text-sm">
          판례 데이터를 분석하여 전문적인 법률 문장으로 변환하고 있습니다.<br />
          잠시만 기다려 주세요.
        </p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col items-center p-4 py-10">
      <div className="max-w-2xl w-full">
        {/* 상단 알림 바 */}
        <div className="bg-green-50 border border-green-200 rounded-xl p-4 mb-6 flex items-center shadow-sm">
          <div className="bg-green-500 rounded-full p-1 mr-3">
            <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <span className="text-green-800 font-medium text-sm">AI 고소장 초안 작성이 완료되었습니다!</span>
        </div>

        {/* 결과지 카드 */}
        <div className="bg-white rounded-2xl shadow-xl overflow-hidden border border-gray-200">
          <div className="bg-gray-800 px-6 py-4 flex justify-between items-center text-white">
            <span className="font-semibold text-sm">고소장 미리보기</span>
            <span className="text-xs text-gray-400">PDF 다운로드 가능(준비중)</span>
          </div>
          
          <div className="p-8 md:p-12 font-serif text-gray-800 leading-relaxed whitespace-pre-wrap min-h-[400px]">
            {complaintText}
          </div>

          <div className="p-6 bg-gray-50 border-t border-gray-100 grid grid-cols-2 gap-4">
            <button
              onClick={handleCopy}
              className="bg-white border border-gray-300 hover:bg-gray-100 text-gray-700 font-bold py-3 px-4 rounded-xl transition duration-200 shadow-sm flex items-center justify-center"
            >
              텍스트 복사하기
            </button>
            <button
              onClick={() => navigate('/')}
              className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-4 rounded-xl transition duration-200 shadow-sm flex items-center justify-center"
            >
              처음으로 돌아가기
            </button>
          </div>
        </div>
        
        <p className="mt-6 text-center text-xs text-gray-400 leading-relaxed px-4">
          본 서류는 AI가 생성한 초안으로, 법적 효력을 보장하지 않습니다.<br />
          제출 전 반드시 법률 전문가의 검토를 받으시길 권장합니다.
        </p>
      </div>
    </div>
  );
}