'use client';

/**
 * Drag handle for the evidence panel.
 *
 * The panel doubles as a document viewer, so a fixed width is either too
 * narrow to read a page or too wide for the conversation. Width persists per
 * browser and is also adjustable from the keyboard, since a pointer-only
 * resize would be inaccessible.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

const STORAGE_KEY = 'duckdocs.panelWidth';
export const PANEL_MIN = 320;
export const PANEL_MAX = 880;
export const PANEL_DEFAULT = 420;

export function readPanelWidth(): number {
  if (typeof window === 'undefined') return PANEL_DEFAULT;
  const stored = Number.parseInt(window.localStorage.getItem(STORAGE_KEY) ?? '', 10);
  if (Number.isNaN(stored)) return PANEL_DEFAULT;
  return Math.min(PANEL_MAX, Math.max(PANEL_MIN, stored));
}

export function usePanelWidth(): [number, (width: number) => void] {
  const [width, setWidthState] = useState(PANEL_DEFAULT);

  // Read after mount: localStorage is unavailable during SSR and reading it
  // in the initial state would cause a hydration mismatch.
  useEffect(() => {
    setWidthState(readPanelWidth());
  }, []);

  const setWidth = useCallback((next: number) => {
    const clamped = Math.min(PANEL_MAX, Math.max(PANEL_MIN, Math.round(next)));
    setWidthState(clamped);
    try {
      window.localStorage.setItem(STORAGE_KEY, String(clamped));
    } catch {
      // Private browsing / storage disabled: resizing still works this session.
    }
  }, []);

  return [width, setWidth];
}

export function ResizeHandle({
  width,
  onResize,
}: {
  width: number;
  onResize: (width: number) => void;
}) {
  const [dragging, setDragging] = useState(false);
  const frame = useRef<number | null>(null);

  useEffect(() => {
    if (!dragging) return;

    const onMove = (event: PointerEvent) => {
      // Coalesce to one update per frame; pointermove fires far more often
      // than the panel can usefully repaint.
      if (frame.current !== null) return;
      frame.current = window.requestAnimationFrame(() => {
        frame.current = null;
        onResize(window.innerWidth - event.clientX);
      });
    };
    const stop = () => setDragging(false);

    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', stop);
    window.addEventListener('pointercancel', stop);
    // Stop text selection and cursor flicker while dragging.
    document.body.style.userSelect = 'none';
    document.body.style.cursor = 'col-resize';

    return () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', stop);
      window.removeEventListener('pointercancel', stop);
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
      if (frame.current !== null) window.cancelAnimationFrame(frame.current);
      frame.current = null;
    };
  }, [dragging, onResize]);

  return (
    <div
      className="resize-handle"
      data-dragging={dragging}
      role="separator"
      aria-orientation="vertical"
      aria-label="Resize evidence panel"
      aria-valuenow={width}
      aria-valuemin={PANEL_MIN}
      aria-valuemax={PANEL_MAX}
      tabIndex={0}
      onPointerDown={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDoubleClick={() => onResize(PANEL_DEFAULT)}
      onKeyDown={(event) => {
        if (event.key === 'ArrowLeft') {
          event.preventDefault();
          onResize(width + 24);
        } else if (event.key === 'ArrowRight') {
          event.preventDefault();
          onResize(width - 24);
        } else if (event.key === 'Home') {
          event.preventDefault();
          onResize(PANEL_DEFAULT);
        }
      }}
    />
  );
}
