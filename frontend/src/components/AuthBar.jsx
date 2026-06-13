import { useNavigate } from 'react-router-dom';
import { clearDraft } from '../draftStorage';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

export default function AuthBar() {
  const navigate = useNavigate();

  const handleLogout = async () => {
    await fetch(`${API_BASE_URL}/api/auth/logout`, {
      method: 'POST',
      credentials: 'include',
    }).catch(() => {});
    clearDraft();
    navigate('/login', { replace: true });
  };

  return (
    <div className="mb-6 flex items-center justify-end text-sm text-[#64675f]">
      <button
        type="button"
        onClick={handleLogout}
        className="rounded-full border border-[#d7d9d2] bg-[#fbfbf8] px-4 py-2 text-sm font-semibold text-[#32342f] transition hover:border-[#111111]"
      >
        로그아웃
      </button>
    </div>
  );
}
