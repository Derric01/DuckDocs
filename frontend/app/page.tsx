import { ArrowRight, FileSearch, LockKeyhole, ScanText, ShieldCheck } from 'lucide-react';
import Link from 'next/link';
import { Badge, Button } from '@/components/ui';

/**
 * Each pillar's tint carries the same meaning it has everywhere else in the
 * app: accent marks citations/evidence, success marks the local/private
 * guarantee, and the image hue marks OCR — it is the same colour a scanned
 * page gets in the library. Decoration that happens to be true.
 */
const PILLARS = [
  {
    icon: FileSearch,
    tint: 'border-accent/25 bg-accent-muted text-accent',
    title: 'Evidence is an object',
    body: 'Every claim carries a citation that opens the exact passage it came from — page, lines, and confidence included.',
  },
  {
    icon: LockKeyhole,
    tint: 'border-success/25 bg-success-muted text-success',
    title: 'Local by default',
    body: 'Documents, the search index, and OCR all run on this machine. No account, no telemetry, no background uploads.',
  },
  {
    icon: ScanText,
    tint: 'border-kind-image/25 bg-kind-image/10 text-kind-image',
    title: 'Scans are first-class',
    body: 'Scanned PDFs and photographed pages are recognized on-device with no page cap, and low-confidence text is labeled rather than hidden.',
  },
];

const STEPS = [
  {
    title: 'Ingest',
    tint: 'border-kind-code/25 bg-kind-code/10 text-kind-code',
    body: 'Files are parsed page by page. Anything without a text layer goes through local OCR.',
  },
  {
    title: 'Summarize',
    tint: 'border-kind-image/25 bg-kind-image/10 text-kind-image',
    body: 'Each document gets a summary on arrival, labeled with how it was produced.',
  },
  {
    title: 'Ground',
    tint: 'border-success/25 bg-success-muted text-success',
    body: 'A model drafts only from retrieved passages. Unsupported claims are refused, not smoothed over.',
  },
  {
    title: 'Verify',
    tint: 'border-accent/25 bg-accent-muted text-accent',
    body: 'Open any citation to read the source page and judge it yourself.',
  },
];

export default function LandingPage() {
  return (
    <main className="min-h-[100dvh] bg-background">
      <header className="sticky top-0 z-20 flex h-14 items-center justify-between gap-6 border-b border-border bg-background/90 px-6 backdrop-blur-sm">
        <Link href="/" className="rounded font-display text-lg leading-none text-foreground">
          DuckDocs
        </Link>
        <nav aria-label="Sections" className="flex items-center gap-1">
          <a
            href="#principles"
            className="hidden h-8 items-center rounded px-2.5 text-sm text-muted-foreground transition-colors hover:text-foreground sm:inline-flex"
          >
            Principles
          </a>
          <a
            href="#how"
            className="hidden h-8 items-center rounded px-2.5 text-sm text-muted-foreground transition-colors hover:text-foreground sm:inline-flex"
          >
            How it works
          </a>
          <Button asChild variant="primary" size="sm" className="ml-2">
            <Link href="/intelligence">Open workspace</Link>
          </Button>
        </nav>
      </header>

      <section className="mx-auto max-w-3xl px-6 pb-20 pt-24 max-sm:pt-14">
        {/* The hero runs in the serif. A document tool should look like it
            belongs to the same world as the documents it reads. */}
        <h1 className="text-balance font-display text-5xl leading-[1.08] text-foreground max-sm:text-3xl">
          Answers you can trace back to <em className="italic">the page they came from</em>
        </h1>
        <p className="mt-6 max-w-xl text-lg leading-relaxed text-muted-foreground max-sm:text-md">
          DuckDocs turns your own documents into a private, searchable workspace. Ask in plain language and get an
          answer that cites its sources — or an honest refusal when the evidence is not there.
        </p>
        <div className="mt-9 flex flex-wrap gap-2.5">
          <Button asChild variant="primary" size="lg">
            <Link href="/intelligence">
              Open workspace
              <ArrowRight className="size-4" aria-hidden />
            </Link>
          </Button>
          <Button asChild size="lg">
            <Link href="/library">Add documents</Link>
          </Button>
        </div>
        <p className="mt-7 inline-flex items-center gap-1.5 text-xs text-muted-foreground">
          <LockKeyhole className="size-3.5" aria-hidden />
          Runs entirely on your machine
        </p>

        <figure className="mt-16 overflow-hidden rounded-lg border border-border bg-card">
          <figcaption className="flex items-center justify-between border-b border-border bg-muted/40 px-4 py-2">
            <span className="eyebrow">Grounded answer</span>
            <Badge tone="success">
              <ShieldCheck className="size-3" aria-hidden />
              Cited
            </Badge>
          </figcaption>
          <div className="p-5">
            <p className="text-md leading-relaxed text-foreground">
              Records must remain on the local machine for 18 months before archival review.
            </p>
            <div className="mt-4 inline-flex items-center gap-2 rounded border border-border px-2.5 py-1.5">
              <span className="grid size-[18px] place-items-center rounded-sm border border-accent/25 bg-accent-muted font-mono text-[10px] text-accent">
                1
              </span>
              <span className="text-xs text-foreground">retention-policy.pdf</span>
              <span className="font-mono text-2xs text-muted-foreground">p2 · 94%</span>
            </div>
          </div>
        </figure>
      </section>

      <section id="principles" className="border-t border-border py-20">
        <div className="mx-auto max-w-4xl px-6">
          <h2 className="font-display text-3xl text-foreground">Built for documents you actually have to trust</h2>
          <p className="mt-3 max-w-2xl text-md leading-relaxed text-muted-foreground">
            Cloud assistants answer fluently but hide where the answer came from, and they want your files. DuckDocs
            closes that gap: one local library, retrieval you can audit, and uncertainty stated plainly.
          </p>
          <div className="mt-10 grid gap-px overflow-hidden rounded-lg border border-border bg-border sm:grid-cols-3">
            {PILLARS.map((pillar) => {
              const Icon = pillar.icon;
              return (
                <article key={pillar.title} className="bg-card p-5">
                  <span className={`kind-mark mb-4 size-9 ${pillar.tint}`}>
                    <Icon className="size-4" strokeWidth={1.6} aria-hidden />
                  </span>
                  <h3 className="text-sm font-semibold text-foreground">{pillar.title}</h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{pillar.body}</p>
                </article>
              );
            })}
          </div>
        </div>
      </section>

      <section id="how" className="border-t border-border py-20">
        <div className="mx-auto max-w-4xl px-6">
          <h2 className="font-display text-3xl text-foreground">How a question becomes a grounded answer</h2>
          <p className="mt-3 max-w-2xl text-md leading-relaxed text-muted-foreground">
            Four stages, with a mandatory checkpoint before anything reaches you.
          </p>
          <ol className="mt-10 grid gap-x-6 gap-y-8 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map((step, index) => (
              <li key={step.title} className="border-t border-border pt-4">
                <span
                  className={`inline-flex h-5 items-center rounded-sm border px-1.5 font-mono text-2xs tabular-nums ${step.tint}`}
                >
                  {String(index + 1).padStart(2, '0')}
                </span>
                <h3 className="mt-2.5 text-sm font-semibold text-foreground">{step.title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{step.body}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <footer className="border-t border-border py-8">
        <div className="mx-auto flex max-w-4xl flex-wrap items-center justify-between gap-4 px-6 text-xs text-muted-foreground">
          <span>DuckDocs — private, evidence-aware document intelligence.</span>
          <Button asChild size="sm">
            <Link href="/intelligence">
              Open workspace
              <ArrowRight className="size-3.5" aria-hidden />
            </Link>
          </Button>
        </div>
      </footer>
    </main>
  );
}
