import { useEffect } from 'react';

// Đóng popover khi bấm ra ngoài hoặc nhấn Esc.
export function useClickOutside(ref, handler, active = true) {
  useEffect(() => {
    if (!active) return undefined;
    const onPointer = (e) => {
      if (ref.current && !ref.current.contains(e.target)) handler();
    };
    const onKey = (e) => {
      if (e.key === 'Escape') handler();
    };
    document.addEventListener('mousedown', onPointer);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onPointer);
      document.removeEventListener('keydown', onKey);
    };
  }, [ref, handler, active]);
}
