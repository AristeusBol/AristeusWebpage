import type { HTMLAttributes, ReactNode } from 'react'
import { useState, useRef, useEffect } from 'react'
import { createPortal } from 'react-dom'

interface TooltipPropsBase {
  content: ReactNode
  position?: 'top' | 'bottom' | 'left' | 'right'
  delay?: number
}

export interface TooltipProps extends TooltipPropsBase, Omit<HTMLAttributes<HTMLDivElement>, 'content'> {}

const positionClasses = {
  top: 'bottom-full left-1/2 -translate-x-1/2 mb-2',
  bottom: 'top-full left-1/2 -translate-x-1/2 mt-2',
  left: 'right-full top-1/2 -translate-y-1/2 mr-2',
  right: 'left-full top-1/2 -translate-y-1/2 ml-2',
}

const arrowClasses = {
  top: 'top-full left-1/2 -translate-x-1/2 border-t-[var(--text-primary)] border-l-transparent border-r-transparent',
  bottom: 'bottom-full left-1/2 -translate-x-1/2 border-b-[var(--text-primary)] border-l-transparent border-r-transparent',
  left: 'left-full top-1/2 -translate-y-1/2 border-l-[var(--text-primary)] border-t-transparent border-b-transparent',
  right: 'right-full top-1/2 -translate-y-1/2 border-r-[var(--text-primary)] border-t-transparent border-b-transparent',
}

export function Tooltip({
  content,
  children,
  position = 'top',
  delay = 200,
  className = '',
  ...props
}: TooltipProps) {
  const [isVisible, setIsVisible] = useState(false)
  const timeoutRef = useRef<number | undefined>(undefined)
  const childRef = useRef<HTMLDivElement>(null)

  const show = () => {
    timeoutRef.current = window.setTimeout(() => setIsVisible(true), delay)
  }

  const hide = () => {
    if (timeoutRef.current) window.clearTimeout(timeoutRef.current)
    setIsVisible(false)
  }

  useEffect(() => {
    return () => {
      if (timeoutRef.current) window.clearTimeout(timeoutRef.current)
    }
  }, [])

  const tooltipContent = isVisible ? (
    <div
      className={`
        fixed z-50 px-3 py-1.5
        bg-[var(--text-primary)] text-[var(--text-inverse)]
        text-xs font-medium rounded-lg shadow-lg
        whitespace-nowrap animate-fade-in
        ${positionClasses[position]}
        ${className}
      `}
      role="tooltip"
    >
      {content}
      <div
        className={`
          absolute w-0 h-0 border-4 border-transparent
          ${arrowClasses[position]}
        `}
        aria-hidden="true"
      />
    </div>
  ) : null

  return (
    <div
      ref={childRef}
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
      {...props}
    >
      {children}
      {typeof window !== 'undefined' && createPortal(tooltipContent, document.body)}
    </div>
  )
}