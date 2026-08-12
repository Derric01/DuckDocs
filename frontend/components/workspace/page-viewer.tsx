'use client';

/**
 * Rendered page viewer for the evidence panel.
 *
 * Only the page currently in view is requested. Nothing pre-renders the whole
 * document, so a 500-page PDF costs exactly the same as a 2-page one — which
 * is why no virtualization layer is needed here. Page images are served with
 * an immutable cache header, so revisiting a page is instant.
 */

import {
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  Maximize2,
  Minus,
  Plus,
  RotateCw,
} from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Button, Skeleton } from '@/components/ui';
import { cn } from '@/lib/utils';
import { duckDocsApi } from '@/lib/api/client';
import type { BBox } from '@/lib/types';

type FitMode = 'width' | 'page' | 'custom';

const ZOOM_STEPS = [0.5, 0.75, 1, 1.25, 1.5, 2, 3];
const MIN_ZOOM = 0.25;
const MAX_ZOOM = 4;

export interface PageViewerProps {
  documentId: string;
  documentName: string;
  pageCount: number;
  /** Page to show, 1-indexed. Changing this jumps the viewer. */
  page: number;
  onPageChange: (page: number) => void;
  /** Normalized [x, y, w, h] region to highlight on the current page. */
  highlight?: BBox | null;
}

export function PageViewer({
  documentId,
  documentName,
  pageCount,
  page,
  onPageChange,
  highlight,
}: PageViewerProps) {
  const [zoom, setZoom] = useState(1);
  const [fit, setFit] = useState<FitMode>('width');
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [naturalSize, setNaturalSize] = useState<{ width: number; height: number } | null>(null);

  const viewportRef = useRef<HTMLDivElement>(null);
  const [viewport, setViewport] = useState<{ width: number; height: number }>({ width: 0, height: 0 });

  const src = useMemo(() => duckDocsApi.pageImageUrl(documentId, page), [documentId, page]);

  // Reset transient state when the page or document changes; keep the user's
  // zoom preference, which should persist as they page through.
  useEffect(() => {
    setStatus('loading');
  }, [src]);

  // Track the viewport so fit-to-width / fit-to-page stay correct on resize
  // and when the panel is resized.
  useEffect(() => {
    const node = viewportRef.current;
    if (!node || typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      const { width, height } = entry.contentRect;
      setViewport({ width, height });
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  const goTo = useCallback(
    (next: number) => {
      const clamped = Math.max(1, Math.min(pageCount, next));
      if (clamped !== page) onPageChange(clamped);
    },
    [page, pageCount, onPageChange],
  );

  const applyZoom = useCallback((next: number) => {
    setFit('custom');
    setZoom(Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, next)));
  }, []);

  const stepZoom = useCallback(
    (direction: 1 | -1) => {
      const current = effectiveScale({ fit, zoom, naturalSize, viewport });
      const candidates = direction === 1 ? ZOOM_STEPS : [...ZOOM_STEPS].reverse();
      const next = candidates.find((step) => (direction === 1 ? step > current + 0.01 : step < current - 0.01));
      applyZoom(next ?? (direction === 1 ? MAX_ZOOM : MIN_ZOOM));
    },
    [applyZoom, fit, zoom, naturalSize, viewport],
  );

  const scale = effectiveScale({ fit, zoom, naturalSize, viewport });

  const onKeyDown = (event: React.KeyboardEvent) => {
    // Don't hijack typing in any embedded control.
    if ((event.target as HTMLElement).closest('input, textarea')) return;

    switch (event.key) {
      case 'ArrowRight':
      case 'PageDown':
        event.preventDefault();
        goTo(page + 1);
        break;
      case 'ArrowLeft':
      case 'PageUp':
        event.preventDefault();
        goTo(page - 1);
        break;
      case 'Home':
        event.preventDefault();
        goTo(1);
        break;
      case 'End':
        event.preventDefault();
        goTo(pageCount);
        break;
      case '+':
      case '=':
        event.preventDefault();
        stepZoom(1);
        break;
      case '-':
        event.preventDefault();
        stepZoom(-1);
        break;
      case '0':
        event.preventDefault();
        setFit('width');
        break;
      default:
        break;
    }
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col" onKeyDown={onKeyDown} tabIndex={-1}>
      <div className="material sticky top-0 z-10 flex shrink-0 items-center justify-between gap-2 border-b border-border px-2 py-1.5">
        <div className="flex items-center gap-0.5">
          <Button
            variant="ghost" size="sm" className="size-8 p-0"
            aria-label="Previous page" disabled={page <= 1} onClick={() => goTo(page - 1)}
          >
            <ChevronLeft className="size-4" />
          </Button>
          <span className="flex items-center gap-1 text-xs text-muted-foreground">
            <input
              type="number" value={page} min={1} max={pageCount}
              aria-label={`Page number, ${pageCount} total`}
              onChange={(event) => {
                const next = Number.parseInt(event.target.value, 10);
                if (!Number.isNaN(next)) goTo(next);
              }}
              className="h-7 w-10 rounded-md bg-transparent text-center font-mono text-xs tabular-nums text-foreground outline-none transition-colors hover:bg-muted focus:bg-secondary"
            />
            <span className="font-mono tabular-nums">/ {pageCount}</span>
          </span>
          <Button
            variant="ghost" size="sm" className="size-8 p-0"
            aria-label="Next page" disabled={page >= pageCount} onClick={() => goTo(page + 1)}
          >
            <ChevronRight className="size-4" />
          </Button>
        </div>

        <div className="flex items-center gap-0.5">
          <Button variant="ghost" size="sm" className="size-8 p-0" aria-label="Zoom out" onClick={() => stepZoom(-1)}>
            <Minus className="size-4" />
          </Button>
          <button
            onClick={() => setFit('width')}
            title="Reset to fit width (0)"
            aria-label={`Zoom ${Math.round(scale * 100)} percent. Reset to fit width.`}
            className="h-7 min-w-[52px] rounded-md px-1.5 font-mono text-2xs tabular-nums text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            {/* A raw percentage while fitting reads as broken ("29%") even
                though it is accurate; name the mode instead. */}
            {fit === 'custom' ? `${Math.round(scale * 100)}%` : fit === 'page' ? 'Fit page' : 'Fit'}
          </button>
          <Button variant="ghost" size="sm" className="size-8 p-0" aria-label="Zoom in" onClick={() => stepZoom(1)}>
            <Plus className="size-4" />
          </Button>
          <Button
            variant={fit === 'page' ? 'subtle' : 'ghost'} size="sm" className="size-8 p-0"
            aria-label="Fit page" aria-pressed={fit === 'page'}
            onClick={() => setFit(fit === 'page' ? 'width' : 'page')}
          >
            <Maximize2 className="size-4" />
          </Button>
        </div>
      </div>

      <div ref={viewportRef} className="flex-1 overflow-auto overscroll-contain bg-background p-4">
        {status === 'error' ? (
          <div className="flex flex-col items-center gap-3 px-4 py-16 text-center">
            <AlertCircle className="size-5 text-muted-foreground" aria-hidden />
            <p className="text-sm text-muted-foreground">This page could not be rendered.</p>
            <Button size="sm" onClick={() => setStatus('loading')}>
              <RotateCw className="size-3.5" aria-hidden />
              Retry
            </Button>
          </div>
        ) : (
          <div
            className="gpu relative mx-auto overflow-hidden rounded-lg shadow-lg"
            style={naturalSize ? { width: naturalSize.width * scale, height: naturalSize.height * scale } : undefined}
          >
            {status === 'loading' ? (
              <Skeleton
                className="absolute inset-0 rounded-lg"
                style={{ height: naturalSize ? naturalSize.height * scale : 460 }}
              />
            ) : null}

            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              key={src}
              src={src}
              alt={`${documentName}, page ${page}`}
              draggable={false}
              onLoad={(event) => {
                const image = event.currentTarget;
                setNaturalSize({ width: image.naturalWidth, height: image.naturalHeight });
                setStatus('ready');
              }}
              onError={() => setStatus('error')}
              className={cn(
                'block h-full w-full rounded-lg transition-opacity duration-200 ease-spring',
                status === 'ready' ? 'opacity-100' : 'opacity-0',
              )}
            />

            {highlight && status === 'ready' ? (
              <span
                aria-hidden
                className="pointer-events-none absolute z-10 animate-scale-in rounded-[3px] bg-primary/25 ring-2 ring-primary shadow-[0_0_0_9999px_rgba(0,0,0,0.3)]"
                style={{
                  left: `${highlight[0] * 100}%`,
                  top: `${highlight[1] * 100}%`,
                  width: `${highlight[2] * 100}%`,
                  height: `${highlight[3] * 100}%`,
                }}
              />
            ) : null}
          </div>
        )}
      </div>

      <p className="shrink-0 border-t border-border px-3 py-1.5 text-center font-mono text-2xs text-muted-foreground/70">
        ← → page · +/− zoom · 0 fit
      </p>
    </div>
  );
}

function effectiveScale({
  fit,
  zoom,
  naturalSize,
  viewport,
}: {
  fit: FitMode;
  zoom: number;
  naturalSize: { width: number; height: number } | null;
  viewport: { width: number; height: number };
}): number {
  if (fit === 'custom' || !naturalSize || viewport.width === 0) return zoom;
  // Leave a small gutter so the page never touches the panel edge.
  const widthScale = (viewport.width - 24) / naturalSize.width;
  if (fit === 'width') return Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, widthScale));
  const heightScale = (viewport.height - 24) / naturalSize.height;
  return Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, Math.min(widthScale, heightScale)));
}
