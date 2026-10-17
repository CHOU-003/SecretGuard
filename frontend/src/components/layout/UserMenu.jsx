import { useRef, useState } from 'react';
import { useAuth } from '../../context/AuthContext.jsx';
import { useClickOutside } from '../../hooks/useClickOutside.js';
import { ChevronDownIcon, LogoutIcon } from '../common/icons.jsx';

export default function UserMenu() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useClickOutside(ref, () => setOpen(false), open);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="rounded-lg px-1 text-left focus-visible:outline-2 focus-visible:outline-brand-sky"
      >
        <span className="flex items-center gap-1.5 font-semibold text-fg">
          {user?.username}
          <ChevronDownIcon className="h-4 w-4 text-fg-muted" />
        </span>
        <span className="mt-0.5 flex items-center gap-1.5 text-xs text-fg-muted">
          <span className="h-2 w-2 rounded-full bg-ok" />
          Online
        </span>
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 top-full z-20 mt-3 w-44 rounded-xl border border-rim bg-panel p-1.5 shadow-xl"
        >
          <button
            type="button"
            role="menuitem"
            onClick={logout}
            className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-fg transition hover:bg-white/5"
          >
            <LogoutIcon className="h-4 w-4" />
            Đăng xuất
          </button>
        </div>
      )}
    </div>
  );
}