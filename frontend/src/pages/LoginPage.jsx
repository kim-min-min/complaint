import React from 'react';

export default function LoginPage() {
  // 1. 카카오 개발자 센터에서 발급받은 REST API 키와 리다이렉트 URI
  const KAKAO_CLIENT_ID = "YOUR_REST_API_KEY"; 
  const REDIRECT_URI = "http://localhost:3000/auth/kakao/callback";
  
  // 2. 카카오 인증 페이지 URL 생성
  const KAKAO_AUTH_URL = `https://kauth.kakao.com/oauth/authorize?client_id=${KAKAO_CLIENT_ID}&redirect_uri=${REDIRECT_URI}&response_type=code`;

  const handleLogin = () => {
    // 실제 운영 시 카카오 로그인 페이지로 이동
    window.location.href = KAKAO_AUTH_URL;
  };

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-lg p-10 text-center">
        
        {/* 서비스 아이콘 (문서 모양) */}
        <div className="mb-8">
          <div className="w-20 h-20 bg-blue-600 rounded-3xl mx-auto mb-6 flex items-center justify-center shadow-lg transform rotate-3">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-12 w-12 text-white -rotate-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <h1 className="text-3xl font-extrabold text-gray-900 tracking-tight">나홀로 소송</h1>
          <p className="text-blue-600 font-semibold mt-1">AI 법률 어시스턴트</p>
        </div>

        <div className="mb-10 text-gray-500 text-sm leading-relaxed">
          어렵고 복잡한 법률 서류 작성,<br />
          AI가 당신의 이야기를 전문적인 문장으로 바꿔드립니다.<br />
          지금 바로 로그인을 통해 시작해 보세요.
        </div>

        {/* 카카오 로그인 버튼 */}
        <button
          onClick={handleLogin}
          className="w-full bg-[#FEE500] hover:bg-[#FDE100] text-[#191919] font-bold py-4 px-6 rounded-xl flex items-center justify-center transition-all duration-200 active:scale-[0.98] shadow-sm"
        >
          <svg className="w-6 h-6 mr-3" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 3c-4.97 0-9 3.185-9 7.115 0 2.558 1.707 4.8 4.315 6.055-.177.65-.638 2.35-.731 2.723-.117.46.166.454.349.33.143-.097 2.274-1.543 3.18-2.155.603.085 1.233.132 1.887.132 4.97 0 9-3.185 9-7.115S16.97 3 12 3z" />
          </svg>
          카카오 계정으로 로그인
        </button>

        <div className="mt-8 pt-8 border-t border-gray-100 flex justify-center space-x-6 text-xs text-gray-400">
          <button className="hover:underline">이용약관</button>
          <button className="hover:underline">개인정보 처리방침</button>
          <button className="hover:underline">고객센터</button>
        </div>
      </div>
    </div>
  );
}