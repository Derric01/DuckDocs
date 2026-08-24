'use client';

import { AlertCircle, Check, X } from 'lucide-react';
import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from 'react';
import { cn } from '@/lib/utils';

export interface ToastMessage {
  id: number;
  text: string;
  tone: 'info' | 'success' | 'error';
}

interface ToastContextValue {
  notify: (text: string, tone?: ToastMessage['tone']) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [messages, setMessages] = useState<ToastMessage[]>([]);
  const counter = useRef(0);

  const dismiss = useCallback((id: number) => {
    setMessages((current) => current.filter((message) => message.id !== id));
  }, []);

  const notify = useCallback(
    (text: string, tone: ToastMessage['tone'] = 'info') => {
      counter.current += 1;
      const id = counter.current;
      // Cap the stack so a burst of failures cannot bury the interface.
      setMessages((current) => [...current.slice(-2), { id, text, tone }]);
      window.setTimeout(() => dismiss(id), tone === 'error' ? 6000 : 3600);
    },
    [dismiss],
  );

  const value = useMemo(() => ({ notify }), [notify]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        role="region"
        aria-label="Notifications"
        className="pointer-events-none fixed inset-x-0 bottom-5 z-[60] flex flex-col items-center gap-2 px-4"
      >
        {messages.map((message) => (
          <div
            key={message.id}
            role="status"
            className={cn(
              'pointer-events-auto flex w-full max-w-md animate-slide-up items-center gap-3',
              'rounded-lg border border-border bg-popover px-3.5 py-2.5 text-sm shadow-lg',
            )}
          >
            <span
              className={cn(
                'grid size-5 shrink-0 place-items-center rounded-sm border',
                message.tone === 'error'
                  ? 'border-destructive/20 bg-destructive-muted text-destructive'
                  : message.tone === 'success'
                    ? 'border-success/20 bg-success-muted text-success'
                    : 'border-accent/20 bg-accent-muted text-accent',
              )}
            >
              {message.tone === 'error' ? (
                <AlertCircle className="size-3.5" aria-hidden />
              ) : (
                <Check className="size-3.5" aria-hidden />
              )}
            </span>
            <span className="min-w-0 flex-1 text-foreground">{message.text}</span>
            <button
              onClick={() => dismiss(message.id)}
              aria-label="Dismiss"
              className="grid size-6 shrink-0 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              <X className="size-3.5" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (!context) throw new Error('useToast must be used inside ToastProvider');
  return context;
}
