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
import { IconButton, Skeleton } from '@/components/ui';
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
    <div className="viewer" onKeyDown={onKeyDown} tabIndex={-1}>
      <div className="viewer-toolbar">
        <div className="viewer-pager">
          <IconButton
            icon={ChevronLeft}
            label="Previous page"
            size={15}
            disabled={page <= 1}
            onClick={() => goTo(page - 1)}
          />
          <span className="viewer-page-label">
            <input
              type="number"
              className="viewer-page-input mono"
              value={page}
              min={1}
              max={pageCount}
              aria-label={`Page number, ${pageCount} total`}
              onChange={(event) => {
                const next = Number.parseInt(event.target.value, 10);
                if (!Number.isNaN(next)) goTo(next);
              }}
            />
            <span className="mono">/ {pageCount}</span>
          </span>
          <IconButton
            icon={ChevronRight}
            label="Next page"
            size={15}
            disabled={page >= pageCount}
            onClick={() => goTo(page + 1)}
          />
        </div>

        <div className="viewer-zoom">
          <IconButton icon={Minus} label="Zoom out" size={15} onClick={() => stepZoom(-1)} />
          <button
            className="viewer-zoom-value mono"
            onClick={() => setFit('width')}
            title="Reset to fit width (0)"
            aria-label={`Zoom ${Math.round(scale * 100)} percent. Reset to fit width.`}
          >
            {/* A raw percentage while fitting reads as broken ("29%") even
                though it is accurate; name the mode instead. */}
            {fit === 'custom' ? `${Math.round(scale * 100)}%` : fit === 'page' ? 'Fit page' : 'Fit'}
          </button>
          <IconButton icon={Plus} label="Zoom in" size={15} onClick={() => stepZoom(1)} />
          <IconButton
            icon={Maximize2}
            label="Fit page"
            size={15}
            aria-pressed={fit === 'page'}
            onClick={() => setFit(fit === 'page' ? 'width' : 'page')}
          />
        </div>
      </div>

      <div className="viewer-viewport" ref={viewportRef}>
        {status === 'error' ? (
          <div className="viewer-message">
            <AlertCircle size={16} strokeWidth={1.8} aria-hidden="true" />
            <p>This page could not be rendered.</p>
            <button className="btn btn-secondary btn-sm" onClick={() => setStatus('loading')}>
              <RotateCw size={13} strokeWidth={1.8} aria-hidden="true" />
              Retry
            </button>
          </div>
        ) : (
          <div
            className="viewer-canvas"
            style={
              naturalSize
                ? { width: naturalSize.width * scale, height: naturalSize.height * scale }
                : undefined
            }
          >
            {status === 'loading' ? (
              <div className="viewer-skeleton" aria-hidden="true">
                <Skeleton height={naturalSize ? naturalSize.height * scale : 420} />
              </div>
            ) : null}

            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              key={src}
              src={src}
              alt={`${documentName}, page ${page}`}
              className="viewer-image"
              data-state={status}
              draggable={false}
              onLoad={(event) => {
                const image = event.currentTarget;
                setNaturalSize({ width: image.naturalWidth, height: image.naturalHeight });
                setStatus('ready');
              }}
              onError={() => setStatus('error')}
            />

            {highlight && status === 'ready' ? (
              <span
                className="viewer-highlight"
                aria-hidden="true"
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

      <p className="viewer-hint mono">← → page · +/− zoom · 0 fit</p>
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
