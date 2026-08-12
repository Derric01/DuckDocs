import { NextRequest, NextResponse } from 'next/server';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const upstreamBase = (process.env.DUCKDOCS_API_URL ?? 'http://127.0.0.1:8000/api/v1').replace(/\/$/, '');

/**
 * Headers that are per-connection rather than per-resource. Forwarding these
 * either confuses the upstream fetch (a copied `host` would point it at
 * itself) or duplicates something the runtime already sets correctly.
 */
const HOP_BY_HOP = new Set([
  'host',
  'connection',
  'keep-alive',
  'transfer-encoding',
  'upgrade',
  'proxy-authenticate',
  'proxy-authorization',
  'te',
  'trailer',
]);

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const target = new URL(`${upstreamBase}/${path.join('/')}`);
  request.nextUrl.searchParams.forEach((value, key) => {
    target.searchParams.set(key, value);
  });

  // A transparent passthrough, not an allowlist: Range/If-Range on the way in
  // is what lets a browser's native PDF viewer page through a large document
  // (GET /documents/{id}/file), and Content-Disposition/Cache-Control on the
  // way back is what makes that response safe (HTML forced to download
  // rather than rendering inline) and cacheable (immutable page images). An
  // allowlist of one header silently drops whichever of those the next
  // endpoint turns out to need.
  const headers = new Headers();
  request.headers.forEach((value, key) => {
    if (!HOP_BY_HOP.has(key.toLowerCase())) headers.set(key, value);
  });

  const init: RequestInit = {
    method: request.method,
    headers,
    cache: 'no-store',
  };

  if (request.method !== 'GET' && request.method !== 'HEAD') {
    init.body = await request.arrayBuffer();
  }

  try {
    const upstream = await fetch(target, init);
    const responseHeaders = new Headers();
    upstream.headers.forEach((value, key) => {
      if (!HOP_BY_HOP.has(key.toLowerCase())) responseHeaders.set(key, value);
    });

    return new NextResponse(upstream.body, {
      status: upstream.status,
      headers: responseHeaders,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Upstream API unreachable';
    return NextResponse.json(
      {
        error: {
          code: 'API_UNREACHABLE',
          message: `DuckDocs API proxy failed: ${message}`,
          suggested_action: 'Confirm the backend is running on port 8000.',
          retryable: true,
        },
      },
      { status: 502 },
    );
  }
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
export const OPTIONS = proxy;
