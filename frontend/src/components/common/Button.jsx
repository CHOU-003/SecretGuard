import { SpinnerIcon } from './icons.jsx';

export default function Button({
  icon: Icon,
  loading = false,
  disabled = false,
  children,
  className = '',
  ...props
}) {
  return (
    <button
      disabled={disabled || loading}
      className={`flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-linear-to-r from-brand-violet to-brand-sky text-sm font-semibold text-white transition hover:brightness-110 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-sky disabled:cursor-not-allowed disabled:opacity-60 ${className}`}
      {...props}
    >
      {loading ? <SpinnerIcon className="h-5 w-5" /> : Icon && <Icon className="h-5 w-5" />}
      {children}
    </button>
  );
}