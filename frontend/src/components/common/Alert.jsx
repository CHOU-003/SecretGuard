export default function Alert({ children }) {
  if (!children) return null;
  return (
    <div
      role="alert"
      className="rounded-xl border border-red-400/40 bg-red-500/10 px-4 py-3 text-sm text-red-300"
    >
      {children}
    </div>
  );
}