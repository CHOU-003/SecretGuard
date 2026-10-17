export default function TextField({
  id,
  label,
  icon: Icon,
  rightSlot,
  className = '',
  ...props
}) {
  return (
    <div className={className}>
      <label htmlFor={id} className="mb-2 block text-sm font-medium text-fg/90">
        {label}
      </label>
      <div className="relative">
        {Icon && (
          <Icon className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-fg-muted" />
        )}
        <input
          id={id}
          className={`h-12 w-full rounded-xl border border-field bg-night/60 text-sm text-fg outline-none transition placeholder:text-fg-muted/80 focus:border-brand-sky focus:ring-2 focus:ring-brand-sky/25 ${
            Icon ? 'pl-12' : 'pl-4'
          } ${rightSlot ? 'pr-12' : 'pr-4'}`}
          {...props}
        />
        {rightSlot && (
          <div className="absolute right-3 top-1/2 -translate-y-1/2">{rightSlot}</div>
        )}
      </div>
    </div>
  );
}