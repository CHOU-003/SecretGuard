import Logo from '../common/Logo.jsx';
import UserMenu from './UserMenu.jsx';
import { useAuth } from '../../context/AuthContext.jsx';
import { capitalize } from '../../utils/format.js';

export default function Topbar() {
  const { user } = useAuth();

  return (
    <header className="flex min-h-26.5 items-center justify-between gap-4 border-b border-rim/60 px-6 lg:px-8">
      <Logo className="lg:hidden" />

      <div className="hidden lg:block">
        <h1 className="text-2xl font-bold text-fg">{capitalize(user?.username)}</h1>
        <p className="text-sm text-fg/80">Giám sát và phát hiện rò rỉ mã nguồn theo thời gian thực.</p>
      </div>

      <UserMenu />
    </header>
  );
}