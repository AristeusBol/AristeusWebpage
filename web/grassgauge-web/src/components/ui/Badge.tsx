import type { HTMLAttributes } from 'react'
import { forwardRef } from 'react'

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'gg' | 'cv' | 'success' | 'warning' | 'danger' | 'neutral'
  size?: 'sm' | 'md' | 'lg'
  dot?: boolean
}

const variantClasses = {
  default: 'bg-[var(--bg-secondary)] text-[var(--text-primary)] border border-[var(--border-subtle)]',
  gg: 'bg-[var(--gg-green-dark)]/10 text-[var(--gg-green-dark)] border border-[var(--gg-green-dark)]/20',
  cv: 'bg-[var(--cv-gold)]/10 text-[var(--cv-gold)] border border-[var(--cv-gold)]/20',
  success: 'bg-green-500/10 text-green-700 dark:text-green-300 border border-green-500/20',
  warning: 'bg-yellow-500/10 text-yellow-700 dark:text-yellow-300 border border-yellow-500/20',
  danger: 'bg-red-500/10 text-red-700 dark:text-red-300 border border-red-500/20',
  neutral: 'bg-gray-500/10 text-gray-700 dark:text-gray-300 border border-gray-500/20',
}

const sizeClasses = {
  sm: 'px-2 py-0.5 text-xs gap-1',
  md: 'px-2.5 py-1 text-sm gap-1.5',
  lg: 'px-3 py-1.5 text-base gap-2',
}

export const Badge = forwardRef<HTMLSpanElement, BadgeProps>(
  ({ variant = 'default', size = 'md', dot = false, className = '', children, ...props }, ref) => {
    return (
      <span
        ref={ref}
        className={`
          inline-flex items-center font-medium rounded-full border
          transition-colors duration-200
          ${variantClasses[variant]}
          ${sizeClasses[size]}
          ${className}
        `}
        {...props}
      >
        {dot && (
          <span
            className={`
              w-1.5 h-1.5 rounded-full
              ${variant === 'gg' && 'bg-[var(--gg-green-dark)]'}
              ${variant === 'cv' && 'bg-[var(--cv-gold)]'}
              ${variant === 'success' && 'bg-green-500'}
              ${variant === 'warning' && 'bg-yellow-500'}
              ${variant === 'danger' && 'bg-red-500'}
              ${variant === 'neutral' && 'bg-gray-500'}
              ${variant === 'default' && 'bg-[var(--text-secondary)]'}
            `}
            aria-hidden="true"
          />
        )}
        {children}
      </span>
    )
  }
)

Badge.displayName = 'Badge'