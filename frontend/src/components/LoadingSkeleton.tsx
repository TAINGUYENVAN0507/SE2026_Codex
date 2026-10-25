export function LoadingSkeleton({
  label,
  kind = 'transcript',
}: {
  label: string
  kind?: 'list' | 'transcript' | 'summary'
}) {
  return (
    <div
      className={`loading-skeleton loading-${kind}`}
      role="status"
      aria-busy="true"
      aria-label={label}
    >
      <span className="sr-only">{label}</span>
      <div aria-hidden="true">
        {Array.from({ length: kind === 'list' ? 4 : 3 }, (_, i) => (
          <div className="skeleton-block" key={i}>
            <i className="skeleton-bar short" />
            <i className="skeleton-bar" />
            <i className="skeleton-bar medium" />
          </div>
        ))}
      </div>
    </div>
  )
}
