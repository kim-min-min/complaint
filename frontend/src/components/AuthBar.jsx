import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

export default function AuthBar() {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);

  useEffect(() => {
    let ignore = false;

    async function loadUser() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
          credentials: 'include',
        });
        if (!response.ok) return;
        const data = await response.json();
        if (!ignore) setUser(data);
      } catch {
        if (!ignore) setUser(null);
      }
    }

    loadUser();
    return () => {
      ignore = true;
    };
  }, []);

  const handleLogout = async () => {
    await fetch(`${API_BASE_URL}/api/auth/logout`, {
      method: 'POST',
      credentials: 'include',
    }).catch(() => {});
    navigate('/login', { replace: true });
  };

  return (
    <div className="mb-6 flex items-center justify-end gap-3 text-sm text-slate-600">
      {user?.nickname && <span className="font-semibold text-slate-700">{user.nickname}</span>}
      <button
        type="button"
        onClick={handleLogout}
        className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-bold text-slate-700 hover:bg-slate-100"
      >
        로그아웃
      </button>
    </div>
  );
}
