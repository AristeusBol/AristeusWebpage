import type { HTMLAttributes, ReactNode } from 'react'
import { forwardRef } from 'react'

export interface TabItem {
  value: string
  label: string
  icon?: ReactNode
  disabled?: boolean
}

interface TabsPropsBase {
  tabs: TabItem[]
  value: string
  onChange: (value: string) => void
  variant?: 'default' | 'underline' | 'pills'
  fullWidth?: boolean
}

export interface TabsProps extends TabsPropsBase, Omit<HTMLAttributes<HTMLDivElement>, 'onChange'> {}

const variantClasses = {
  default: 'bg-[var(--bg-secondary)] rounded-xl p-1',
  underline: 'border-b border-[var(--border-subtle)]',
  pills: 'gap-1',
}

const tabVariantClasses = {
  default: `
    rounded-lg px-4 py-2 text-sm font-medium
    text-[var(--text-secondary)]
    hover:text-[var(--text-primary)] hover:bg-[var(--bg-card)]
    data-[state=active]:bg-[var(--gg-green-dark)] data-[state=active]:text-white
    transition-all duration-200
  `,
  underline: `
    px-4 py-3 text-sm font-medium -mb-px
    text-[var(--text-secondary)]
    hover:text-[var(--text-primary)]
    data-[state=active]:text-[var(--gg-green-dark)] data-[state=active]:border-b-2 data-[state=active]:border-[var(--gg-green-dark)]
    border-b-2 border-transparent
    transition-all duration-200
  `,
  pills: `
    rounded-xl px-4 py-2 text-sm font-medium
    text-[var(--text-secondary)]
    hover:text-[var(--text-primary)] hover:bg-[var(--bg-secondary)]
    data-[state=active]:bg-[var(--gg-green-dark)] data-[state=active]:text-white
    transition-all duration-200
  `,
}

export const Tabs = forwardRef<HTMLDivElement, TabsProps>(
  ({ tabs, value, onChange, variant = 'default', fullWidth = false, className = '', children, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={`
          ${variantClasses[variant]}
          ${fullWidth ? 'w-full' : 'inline-flex'}
          ${className}
        `}
        role="tablist"
        {...props}
      >
        {tabs.map((tab) => (
          <button
            key={tab.value}
            role="tab"
            aria-selected={value === tab.value}
            aria-controls={`panel-${tab.value}`}
            id={`tab-${tab.value}`}
            disabled={tab.disabled}
            onClick={() => !tab.disabled && onChange(tab.value)}
            className={`
              flex items-center justify-center gap-2 whitespace-nowrap
              disabled:opacity-50 disabled:cursor-not-allowed
              focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--gg-green-mid)] focus-visible:ring-offset-2
              ${tabVariantClasses[variant]}
              ${fullWidth && 'flex-1'}
            `}
            data-state={value === tab.value ? 'active' : 'inactive'}
          >
            {tab.icon && <span aria-hidden="true">{tab.icon}</span>}
            {tab.label}
          </button>
        ))}
        {children}
      </div>
    )
  }
)
Tabs.displayName = 'Tabs'

export interface TabPanelProps extends HTMLAttributes<HTMLDivElement> {
  value: string
  activeValue: string
}
export const TabPanel = forwardRef<HTMLDivElement, TabPanelProps>(
  ({ value, activeValue, className = '', children, ...props }, ref) => {
    if (value !== activeValue) return null

    return (
      <div
        ref={ref}
        role="tabpanel"
        id={`panel-${value}`}
        aria-labelledby={`tab-${value}`}
        className={`animate-fade-in ${className}`}
        {...props}
      >
        {children}
      </div>
    )
  }
)
TabPanel.displayName = 'TabPanel'