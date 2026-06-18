/**
 * cap-evolve brand mark: a capybara silhouette resting atop an ascending
 * fitness curve (echoing the cumulative-best chart). Duotone, theme-aware via
 * currentColor + the accent token. `state="live"` adds a soft amber pulse,
 * disabled automatically under prefers-reduced-motion (global CSS guard).
 */
type Props = {
  size?: number
  state?: 'idle' | 'live'
  className?: string
  title?: string
}

export function Capybara({ size = 32, state = 'idle', className = '', title = 'cap-evolve' }: Props) {
  return (
    <span
      className={`relative inline-flex shrink-0 ${className}`}
      style={{ width: size, height: size }}
    >
      {state === 'live' && (
        <span
          aria-hidden
          className="absolute inset-0 rounded-full animate-pulse-ring"
          style={{ background: 'var(--accent)' }}
        />
      )}
      <svg
        width={size}
        height={size}
        viewBox="0 0 48 48"
        role="img"
        aria-label={title}
        className="relative"
      >
        <title>{title}</title>
        {/* ascending fitness curve */}
        <path
          d="M4 40 L16 34 L26 24 L36 14 L44 8"
          fill="none"
          stroke="var(--accent)"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          opacity="0.9"
        />
        <circle cx="44" cy="8" r="2.6" fill="var(--accent)" />
        {/* capybara body */}
        <g fill="currentColor">
          <ellipse cx="22" cy="33" rx="13" ry="8.5" />
          {/* head */}
          <ellipse cx="34" cy="28" rx="7.5" ry="6.5" />
          {/* snout */}
          <ellipse cx="40.5" cy="29.5" rx="3.2" ry="2.6" />
          {/* ears */}
          <circle cx="31" cy="22" r="1.8" />
          <circle cx="36" cy="22" r="1.8" />
          {/* legs */}
          <rect x="14" y="38" width="2.8" height="6" rx="1.4" />
          <rect x="26" y="38" width="2.8" height="6" rx="1.4" />
        </g>
        {/* eye */}
        <circle cx="34" cy="26.5" r="1" fill="var(--bg)" />
      </svg>
    </span>
  )
}
