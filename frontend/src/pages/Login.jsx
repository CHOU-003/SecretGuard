import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext.jsx';

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const { login } = useAuth();
  const navigate = useNavigate();

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(username, password);
      navigate('/', { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-ink px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex items-center gap-2.5">
          <span className="h-2.5 w-2.5 bg-safe" />
          <span className="font-mono text-lg tracking-tight text-text">SecretGuard</span>
        </div>

        <div className="border border-line bg-surface p-6">
          <h1 className="text-lg font-medium text-text">Đăng nhập quản trị</h1>
          <p className="mt-1 text-sm text-muted">
            Truy cập bảng điều khiển giám sát secret scanning.
          </p>

          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            <div>
              <label className="mb-1.5 block text-sm text-muted" htmlFor="username">
                Tên đăng nhập
              </label>
              <input
                id="username"
                type="text"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                className="w-full border border-line bg-surface2 px-3 py-2 text-text outline-none focus:border-brand"
              />
            </div>

            <div>
              <label className="mb-1.5 block text-sm text-muted" htmlFor="password">
                Mật khẩu
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full border border-line bg-surface2 px-3 py-2 text-text outline-none focus:border-brand"
              />
            </div>

            {error && (
              <div className="border border-critical/40 bg-critical/10 px-3 py-2 text-sm text-critical">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-brand px-3 py-2 font-medium text-ink transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {loading ? 'Đang đăng nhập...' : 'Đăng nhập'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}