/**
 * cap-evolve brand mark — the capybara logo. `state="live"` adds a soft amber
 * pulse ring (disabled under prefers-reduced-motion via the global CSS guard).
 * Served from /cap-evolve-logo.png (public/, downscaled to 256px).
 */
type Props = {
  size?: number
  state?: 'idle' | 'live'
  className?: string
  title?: string
}

export function BrandLogo({ size = 32, state = 'idle', className = '', title = 'cap-evolve' }: Props) {
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
      <img
        src="/cap-evolve-logo.png"
        width={size}
        height={size}
        alt={title}
        className="relative rounded-full"
        loading="eager"
        decoding="async"
      />
    </span>
  )
}
