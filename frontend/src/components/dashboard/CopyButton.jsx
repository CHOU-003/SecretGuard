import { useEffect, useRef, useState } from 'react';
import { CopyIcon, CheckIcon } from '../common/icons.jsx';

export default function CopyButton({ value, label = 'Sao chép' }) {
  const [copied, setCopied] = useState(false);
  const timer = useRef();

  useEffect(() => () => clearTimeout(timer.current), []);

  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      clearTimeout(timer.current);
      timer.current = setTimeout(() => setCopied(false), 1500);
    } catch {
      /* trình duyệt chặn clipboard -> bỏ qua */
    }
  }

  return (
    <button
      type="button"
      onClick={copy}
      aria-label={copied ? 'Đã sao chép' : label}
      title={copied ? 'Đã sao chép' : label}
      className="rounded-md p-1 text-brand-sky/80 transition hover:text-brand-sky focus-visible:outline-2 focus-visible:outline-brand-sky"
    >
      {copied ? <CheckIcon className="h-4.5 w-4.5 text-ok" /> : <CopyIcon className="h-4.5 w-4.5" />}
    </button>
  );
}
