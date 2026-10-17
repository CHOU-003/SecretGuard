import { NavLink } from 'react-router-dom';
import Logo from '../common/Logo.jsx';
import SidebarPromo from './SidebarPromo.jsx';
import { NAV_ITEMS } from '../../constants/navigation.js';

const base = 'flex items-center gap-3 rounded-xl px-4 py-3 text-base font-medium transition';

export default function Sidebar() {
  return (
    <aside className="sticky top-0 hidden h-screen w-71.25 shrink-0 flex-col border-r border-rim/60 bg-sidebar lg:flex">
      <div className="flex h-26.5 items-center border-b border-rim/60 px-6">
        <Logo tagline="Scan · Detect · Protect" />
      </div>

      <nav className="space-y-2 px-3 py-4" aria-label="Điều hướng chính">
        {NAV_ITEMS.map(({ label, to, icon: Icon, soon }) =>
          soon ? (
            <div key={to} aria-disabled="true" className={`${base} cursor-not-allowed text-fg/45`}>
              <Icon className="h-6 w-6" />
              {label}
              <span className="ml-auto rounded-full bg-white/5 px-2 py-0.5 text-xs">Sắp có</span>
            </div>
          ) : (
            <NavLink
              key={to}
              to={to}
              end
              className={({ isActive }) =>
                `${base} ${
                  isActive
                    ? 'bg-nav text-white shadow-[0_8px_24px_-8px_rgba(47,91,255,0.7)]'
                    : 'text-fg/85 hover:bg-white/5'
                }`
              }
            >
              <Icon className="h-6 w-6" />
              {label}
            </NavLink>
          ),
        )}
      </nav>

      <div className="mt-auto p-5">
        <SidebarPromo />
      </div>
    </aside>
  );
}