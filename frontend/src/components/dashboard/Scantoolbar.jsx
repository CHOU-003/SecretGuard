import { useRef, useState } from 'react';
import { SearchIcon, CalendarIcon, CheckIcon } from '../common/icons.jsx';
import { TIME_RANGES } from '../../constants/scanFilters.js';
import { useClickOutside } from '../../hooks/useClickOutside.js';

const control =
  'h-12 rounded-xl border border-field bg-night/60 text-sm text-fg outline-none transition';

export default function ScanToolbar({ query, onQueryChange, range, onRangeChange }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useClickOutside(ref, () => setOpen(false), open);
  const current = TIME_RANGES.find((r) => r.value === range) ?? TIME_RANGES[0];

  return (
    <div className="flex flex-col gap-3 sm:flex-row">
      <label className="relative block sm:w-72">
        <span className="sr-only">Tìm kiếm theo commit hoặc branch</span>
        <SearchIcon className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-brand-sky" />
        <input
          type="search"
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          placeholder="Tìm kiếm theo commit, branch..."
          className={`${control} w-full pl-12 pr-4 placeholder:text-fg-muted focus:border-brand-sky focus:ring-2 focus:ring-brand-sky/25`}
        />
      </label>

      <div ref={ref} className="relative">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-haspopup="listbox"
          aria-expanded={open}
          className={`${control} flex w-full items-center justify-center gap-2.5 px-4 hover:border-brand-sky/60 focus-visible:outline-2 focus-visible:outline-brand-sky`}
        >
          <CalendarIcon className="h-5 w-5" />
          {range === 'all' ? 'Lọc theo thời gian' : current.label}
        </button>

        {open && (
          <ul
            role="listbox"
            className="absolute right-0 top-full z-20 mt-2 w-52 rounded-xl border border-rim bg-panel p-1.5 shadow-xl"
          >
            {TIME_RANGES.map((r) => (
              <li key={r.value} role="option" aria-selected={r.value === range}>
                <button
                  type="button"
                  onClick={() => {
                    onRangeChange(r.value);
                    setOpen(false);
                  }}
                  className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm text-fg hover:bg-white/5"
                >
                  {r.label}
                  {r.value === range && <CheckIcon className="h-4 w-4 text-brand-sky" />}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}