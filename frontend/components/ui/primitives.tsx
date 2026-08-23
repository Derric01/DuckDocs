'use client';

/**
 * Remaining primitives, grouped in one module because each is small and they
 * are almost always imported together.
 */

import * as DialogPrimitive from '@radix-ui/react-dialog';
import * as ProgressPrimitive from '@radix-ui/react-progress';
import * as SeparatorPrimitive from '@radix-ui/react-separator';
import * as SwitchPrimitive from '@radix-ui/react-switch';
import * as TabsPrimitive from '@radix-ui/react-tabs';
import * as TooltipPrimitive from '@radix-ui/react-tooltip';
import { cva, type VariantProps } from 'class-variance-authority';
import { X, type LucideIcon } from 'lucide-react';
import {
  forwardRef,
  type ComponentPropsWithoutRef,
  type ElementRef,
  type HTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
} from 'react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

/* -- Card ---------------------------------------------------------------- */

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn('rounded-lg border border-border bg-card text-card-foreground', className)} {...props} />
  );
}

/* -- Badge --------------------------------------------------------------- */

/**
 * A chip is a tinted fill with a hairline of its own hue. Both together mean
 * the tone survives at 11px, where a fill alone goes muddy and a border alone
 * disappears.
 */
const badgeVariants = cva(
  'inline-flex items-center gap-1 rounded border px-1.5 py-[3px] text-2xs font-medium leading-none whitespace-nowrap',
  {
    variants: {
      tone: {
        neutral: 'border-border bg-muted text-muted-foreground',
        primary: 'border-border-strong bg-primary-muted text-primary',
        accent: 'border-accent/25 bg-accent-muted text-accent',
        success: 'border-success/20 bg-success-muted text-success',
        warning: 'border-warning/25 bg-warning-muted text-warning',
        destructive: 'border-destructive/20 bg-destructive-muted text-destructive',
        outline: 'border-border text-muted-foreground',
      },
    },
    defaultVariants: { tone: 'neutral' },
  },
);

export function Badge({
  className,
  tone,
  icon: Icon,
  spinning,
  children,
  ...props
}: HTMLAttributes<HTMLSpanElement> &
  VariantProps<typeof badgeVariants> & { icon?: LucideIcon; spinning?: boolean }) {
  return (
    <span className={cn(badgeVariants({ tone }), className)} {...props}>
      {Icon ? <Icon className={cn('size-3', spinning && 'animate-spin')} aria-hidden /> : null}
      {children}
    </span>
  );
}

/* -- Input --------------------------------------------------------------- */

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className, ...props }, ref) {
    return (
      <input
        ref={ref}
        className={cn(
          'h-9 w-full rounded-md border border-input bg-card px-2.5 text-md text-foreground',
          'transition-colors duration-fast',
          'placeholder:text-muted-foreground/80',
          'focus:border-ring focus-visible:ring-1 focus-visible:ring-ring focus-visible:ring-offset-0',
          'disabled:opacity-50',
          className,
        )}
        {...props}
      />
    );
  },
);

export function Field({
  label,
  hint,
  error,
  htmlFor,
  children,
}: {
  label: string;
  hint?: string;
  error?: string;
  htmlFor: string;
  children: ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={htmlFor} className="eyebrow block text-foreground">
        {label}
      </label>
      {children}
      {error ? (
        <p role="alert" className="text-xs text-destructive">
          {error}
        </p>
      ) : hint ? (
        <p className="text-xs leading-snug text-muted-foreground">{hint}</p>
      ) : null}
    </div>
  );
}

/* -- Separator ----------------------------------------------------------- */

export const Separator = forwardRef<
  ElementRef<typeof SeparatorPrimitive.Root>,
  ComponentPropsWithoutRef<typeof SeparatorPrimitive.Root>
>(function Separator({ className, orientation = 'horizontal', decorative = true, ...props }, ref) {
  return (
    <SeparatorPrimitive.Root
      ref={ref}
      decorative={decorative}
      orientation={orientation}
      className={cn(
        'shrink-0 bg-border',
        orientation === 'horizontal' ? 'h-px w-full' : 'h-full w-px',
        className,
      )}
      {...props}
    />
  );
});

/* -- Switch -------------------------------------------------------------- */

export const Switch = forwardRef<
  ElementRef<typeof SwitchPrimitive.Root>,
  ComponentPropsWithoutRef<typeof SwitchPrimitive.Root>
>(function Switch({ className, ...props }, ref) {
  return (
    <SwitchPrimitive.Root
      ref={ref}
      className={cn(
        // Tighter than the iOS switch it replaces: this UI is dense, and a
        // 51px track dominated every settings row it sat in.
        'peer inline-flex h-[22px] w-[38px] shrink-0 cursor-pointer items-center rounded-full border border-transparent',
        'transition-colors duration-fast',
        'data-[state=checked]:bg-primary data-[state=unchecked]:border-input data-[state=unchecked]:bg-muted',
        'disabled:cursor-not-allowed disabled:opacity-50',
        className,
      )}
      {...props}
    >
      <SwitchPrimitive.Thumb
        className={cn(
          'pointer-events-none block size-[18px] rounded-full shadow-sm ring-0',
          'transition-transform duration-fast ease-spring',
          'data-[state=checked]:translate-x-[18px] data-[state=checked]:bg-primary-foreground',
          'data-[state=unchecked]:translate-x-0.5 data-[state=unchecked]:bg-card',
        )}
      />
    </SwitchPrimitive.Root>
  );
});

/* -- Tabs ---------------------------------------------------------------- */

export const Tabs = TabsPrimitive.Root;

export const TabsList = forwardRef<
  ElementRef<typeof TabsPrimitive.List>,
  ComponentPropsWithoutRef<typeof TabsPrimitive.List>
>(function TabsList({ className, ...props }, ref) {
  return (
    <TabsPrimitive.List
      ref={ref}
      className={cn(
        // Underlined tabs rather than a segmented pill: they sit flush with the
        // rule below them, which is how a ruled layout stays ruled.
        'inline-flex items-center gap-4 border-b border-border',
        className,
      )}
      {...props}
    />
  );
});

export const TabsTrigger = forwardRef<
  ElementRef<typeof TabsPrimitive.Trigger>,
  ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>
>(function TabsTrigger({ className, ...props }, ref) {
  return (
    <TabsPrimitive.Trigger
      ref={ref}
      className={cn(
        'relative -mb-px inline-flex h-8 items-center justify-center gap-1.5 border-b-2 border-transparent px-0.5',
        'text-xs font-medium text-muted-foreground transition-colors duration-fast',
        'hover:text-foreground',
        'data-[state=active]:border-foreground data-[state=active]:text-foreground',
        className,
      )}
      {...props}
    />
  );
});

export const TabsContent = TabsPrimitive.Content;

/* -- Progress ------------------------------------------------------------ */

export function Progress({ value, label, className }: { value: number; label?: string; className?: string }) {
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <ProgressPrimitive.Root
      value={clamped}
      aria-label={label ?? 'Progress'}
      className={cn('relative h-1 w-full overflow-hidden rounded-sm bg-muted', className)}
    >
      <ProgressPrimitive.Indicator
        className="h-full rounded-sm bg-accent transition-transform duration-slow ease-spring"
        style={{ transform: `translateX(-${100 - clamped}%)` }}
      />
    </ProgressPrimitive.Root>
  );
}

/* -- Skeleton ------------------------------------------------------------ */

export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      aria-hidden
      className={cn(
        'animate-shimmer rounded-md bg-[linear-gradient(90deg,hsl(var(--muted))_25%,hsl(var(--secondary))_37%,hsl(var(--muted))_63%)] bg-[length:200%_100%]',
        className,
      )}
      {...props}
    />
  );
}

/* -- Tooltip ------------------------------------------------------------- */

export const TooltipProvider = TooltipPrimitive.Provider;

export function Tooltip({ content, children }: { content: string; children: ReactNode }) {
  return (
    <TooltipPrimitive.Root>
      <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Content
          sideOffset={6}
          className={cn(
            'z-50 rounded border border-border bg-popover px-2 py-1 text-2xs text-popover-foreground shadow-md',
            'animate-scale-in',
          )}
        >
          {content}
        </TooltipPrimitive.Content>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  );
}

/* -- Dialog -------------------------------------------------------------- */

export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;

export function DialogContent({
  title,
  description,
  children,
  footer,
  className,
}: {
  title: string;
  description?: string;
  children?: ReactNode;
  footer?: ReactNode;
  className?: string;
}) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-50 animate-fade-in bg-black/40 backdrop-blur-[2px]" />
      <DialogPrimitive.Content
        className={cn(
          'fixed left-1/2 top-1/2 z-50 w-[calc(100%-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2',
          'animate-scale-in rounded-xl border border-border bg-popover p-6 shadow-xl',
          className,
        )}
      >
        <div className="mb-5 flex items-start justify-between gap-4">
          <div className="space-y-1">
            <DialogPrimitive.Title className="font-display text-xl text-foreground">
              {title}
            </DialogPrimitive.Title>
            {description ? (
              <DialogPrimitive.Description className="text-sm leading-snug text-muted-foreground">
                {description}
              </DialogPrimitive.Description>
            ) : null}
          </div>
          <DialogPrimitive.Close asChild>
            <Button variant="ghost" size="sm" className="-mr-1.5 -mt-1 size-8 p-0" aria-label="Close">
              <X className="size-4" />
            </Button>
          </DialogPrimitive.Close>
        </div>
        {children ? <div className="space-y-4">{children}</div> : null}
        {footer ? <div className="mt-6 flex justify-end gap-2">{footer}</div> : null}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}

/* -- EmptyState ---------------------------------------------------------- */

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
}: {
  icon: LucideIcon;
  title: string;
  description: string;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn('mx-auto flex max-w-sm flex-col items-center px-4 py-16 text-center', className)}>
      <div className="mb-4 grid size-11 place-items-center rounded-lg border border-border bg-card text-muted-foreground">
        <Icon className="size-[18px]" strokeWidth={1.5} aria-hidden />
      </div>
      <h3 className="font-display text-xl text-foreground">{title}</h3>
      <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{description}</p>
      {action ? <div className="mt-6">{action}</div> : null}
    </div>
  );
}

/* -- Kbd ----------------------------------------------------------------- */

export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-sm border border-border bg-muted px-1 font-mono text-[10px] text-muted-foreground">
      {children}
    </kbd>
  );
}
