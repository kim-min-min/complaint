import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';

export default function ComplaintForm() {
  const navigate = useNavigate();
  
  // 상태 관리: 6가지 핵심 정보 수집
  const [formData, setFormData] = useState({
    complainantName: '',
    accusedName: '',
    incidentDescription: '',
    incidentDate: '',
    incidentLocation: '',
    evidenceSummary: ''
  });

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    // 1. FastAPI 백엔드 전송 및 RabbitMQ 연동 로직이 들어갈 자리입니다.
    // const response = await fetch('http://localhost:8000/generate', { ... });
    
    console.log('AI 분석을 위해 전송될 데이터:', formData);
    
    // 2. 전송 성공 시 결과 대기 페이지 또는 결과 확인 페이지로 이동
    alert('핵심 정보가 접수되었습니다. AI가 법률 양식에 맞게 초안을 작성합니다!');
    // navigate('/result', { state: { formData } }); // 결과 페이지가 준비되면 주석 해제
  };

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="max-w-xl w-full bg-white rounded-2xl shadow-lg p-6 md:p-8">
        
        <div className="mb-8 text-center">
          <h2 className="text-2xl font-bold text-gray-800">나홀로 소송 AI 도우미</h2>
          <p className="text-gray-500 mt-2 text-sm">
            복잡한 법률 용어는 AI에게 맡기고,<br/>있었던 일만 편하게 적어주세요.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          
          {/* 그룹 1: 인적 사항 */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1">내 이름 (고소인)</label>
              <input
                type="text"
                name="complainantName"
                value={formData.complainantName}
                onChange={handleChange}
                placeholder="예: 홍길동"
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1">상대방 이름 (피고소인)</label>
              <input
                type="text"
                name="accusedName"
                value={formData.accusedName}
                onChange={handleChange}
                placeholder="예: 이몽룡 (모르면 '성명불상')"
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition"
                required
              />
            </div>
          </div>

          {/* 그룹 2: 사건 개요 */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1">발생 일시</label>
              <input
                type="text"
                name="incidentDate"
                value={formData.incidentDate}
                onChange={handleChange}
                placeholder="예: 2026년 4월 10일경"
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition"
              />
            </div>
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1">발생 장소</label>
              <input
                type="text"
                name="incidentLocation"
                value={formData.incidentLocation}
                onChange={handleChange}
                placeholder="예: 당근마켓 채팅창 등"
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition"
              />
            </div>
          </div>

          {/* 그룹 3: 상세 설명 */}
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-1">어떤 피해를 입으셨나요?</label>
            <textarea
              name="incidentDescription"
              value={formData.incidentDescription}
              onChange={handleChange}
              rows="4"
              placeholder="시간 순서대로 있었던 일을 편하게 적어주세요."
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition resize-none"
              required
            ></textarea>
          </div>

          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-1">확보하신 증거가 있나요?</label>
            <textarea
              name="evidenceSummary"
              value={formData.evidenceSummary}
              onChange={handleChange}
              rows="2"
              placeholder="예: 송금 내역서 캡처, 카카오톡 대화 내용"
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition resize-none"
            ></textarea>
          </div>

          {/* 제출 버튼 */}
          <button
            type="submit"
            className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-4 rounded-xl transition duration-200 shadow-md"
          >
            AI 고소장 초안 만들기
          </button>
          
        </form>
      </div>
    </div>
  );
}