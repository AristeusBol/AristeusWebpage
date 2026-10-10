import type { TableHTMLAttributes, TdHTMLAttributes, ThHTMLAttributes, HTMLAttributes } from 'react'
import { forwardRef } from 'react'

export interface TableProps extends TableHTMLAttributes<HTMLTableElement> {
  variant?: 'default' | 'scientific' | 'bordered'
}

const variantClasses = {
  default: 'w-full border-collapse',
  scientific: 'w-full border-collapse font-data text-sm',
  bordered: 'w-full border-collapse',
}

export const Table = forwardRef<HTMLTableElement, TableProps>(
  ({ variant = 'default', className = '', children, ...props }, ref) => {
    return (
      <div className="overflow-x-auto">
        <table
          ref={ref}
          className={`${variantClasses[variant]} ${className}`}
          {...props}
        >
          {children}
        </table>
      </div>
    )
  }
)
Table.displayName = 'Table'

export interface TheadProps extends HTMLAttributes<HTMLTableSectionElement> {}
export const Thead = forwardRef<HTMLTableSectionElement, TheadProps>(
  ({ className = '', children, ...props }, ref) => (
    <thead ref={ref} className={className} {...props}>
      {children}
    </thead>
  )
)
Thead.displayName = 'Thead'

export interface TbodyProps extends HTMLAttributes<HTMLTableSectionElement> {}
export const Tbody = forwardRef<HTMLTableSectionElement, TbodyProps>(
  ({ className = '', children, ...props }, ref) => (
    <tbody ref={ref} className={className} {...props}>
      {children}
    </tbody>
  )
)
Tbody.displayName = 'Tbody'

export interface TrProps extends HTMLAttributes<HTMLTableRowElement> {
  clickable?: boolean
  selected?: boolean
  active?: boolean
}
export const Tr = forwardRef<HTMLTableRowElement, TrProps>(
  ({ clickable = false, selected = false, active = false, className = '', children, ...props }, ref) => (
    <tr
      ref={ref}
      className={`
        ${clickable ? 'cursor-pointer transition-colors' : ''}
        ${selected ? 'bg-[var(--gg-green-dark)]/5' : ''}
        ${active ? 'bg-[var(--gg-green-dark)]/10' : ''}
        ${clickable && !selected && !active ? 'hover:bg-[var(--bg-secondary)]' : ''}
        ${className}
      `}
      {...props}
    >
      {children}
    </tr>
  )
)
Tr.displayName = 'Tr'

export interface ThProps extends ThHTMLAttributes<HTMLTableCellElement> {
  width?: string
}
export const Th = forwardRef<HTMLTableCellElement, ThProps>(
  ({ width, className = '', children, ...props }, ref) => (
    <th
      ref={ref}
      style={{ width }}
      className={`
        px-4 py-3 text-left font-semibold text-[var(--text-primary)]
        border-b-2 border-[var(--text-primary)]
        uppercase tracking-wider text-xs
        ${className}
      `}
      {...props}
    >
      {children}
    </th>
  )
)
Th.displayName = 'Th'

export interface TdProps extends TdHTMLAttributes<HTMLTableCellElement> {
  numeric?: boolean
}
export const Td = forwardRef<HTMLTableCellElement, TdProps>(
  ({ numeric = false, className = '', children, ...props }, ref) => (
    <td
      ref={ref}
      className={`
        px-4 py-3 text-[var(--text-primary)]
        border-b border-[var(--border-subtle)]
        ${numeric ? 'text-right font-data tabular-nums' : ''}
        ${className}
      `}
      {...props}
    >
      {children}
    </td>
  )
)
Td.displayName = 'Td'

export interface CaptionProps extends HTMLAttributes<HTMLTableCaptionElement> {}
export const Caption = forwardRef<HTMLTableCaptionElement, CaptionProps>(
  ({ className = '', children, ...props }, ref) => (
    <caption ref={ref} className={`sr-only ${className}`} {...props}>
      {children}
    </caption>
  )
)
Caption.displayName = 'Caption'