import { useAuth } from '../../context/AuthContext.jsx';

export default function DashboardLayout({ title, children }) {
  const { user, logout } = useAuth();

  return (
    <div className="flex min-h-screen bg-ink">
      <aside className="hidden w-56 shrink-0 border-r border-line px-5 py-6 sm:block">
        <div className="mb-8 flex items-center gap-2.5">
          <span className="h-2.5 w-2.5 bg-safe" />
          <span className="font-mono text-base tracking-tight text-text">SecretGuard</span>
        </div>
        <nav className="space-y-1 text-sm">
          <div className="border border-line bg-surface px-3 py-2 text-text">Tổng quan</div>
        </nav>
      </aside>

      <div className="flex-1">
        <header className="flex items-center justify-between border-b border-line px-6 py-4">
          <h1 className="text-lg font-medium text-text">{title}</h1>
          <div className="flex items-center gap-4 text-sm">
            <span className="text-muted">{user?.username}</span>
            <button onClick={logout} className="text-muted hover:text-text">
              Đăng xuất
            </button>
          </div>
        </header>

        <main className="px-6 py-6">{children}</main>
      </div>
    </div>
  );
}