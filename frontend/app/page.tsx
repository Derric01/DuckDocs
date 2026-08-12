import { ArrowRight, FileSearch, LockKeyhole, ScanText, ShieldCheck } from 'lucide-react';
import Link from 'next/link';
import { Badge, Button } from '@/components/ui';
import { cn } from '@/lib/utils';

const PILLARS = [
  {
    icon: FileSearch,
    tile: 'bg-primary',
    title: 'Evidence is an object',
    body: 'Every claim carries a citation that opens the exact passage it came from — page, lines, and confidence included.',
  },
  {
    icon: LockKeyhole,
    tile: 'bg-ios-green',
    title: 'Local by default',
    body: 'Documents, the search index, and OCR all run on this machine. No account, no telemetry, no background uploads.',
  },
  {
    icon: ScanText,
    tile: 'bg-ios-purple',
    title: 'Scans are first-class',
    body: 'Scanned PDFs and photographed pages are recognized on-device with no page cap, and low-confidence text is labeled rather than hidden.',
  },
];

const STEPS = [
  { title: 'Ingest', body: 'Files are parsed page by page. Anything without a text layer goes through local OCR.' },
  { title: 'Summarize', body: 'Each document gets a summary on arrival, labeled with how it was produced.' },
  { title: 'Ground', body: 'A model drafts only from retrieved passages. Unsupported claims are refused, not smoothed over.' },
  { title: 'Verify', body: 'Open any citation to read the source page and judge it yourself.' },
];

const STEP_TILES = ['bg-primary', 'bg-ios-purple', 'bg-ios-teal', 'bg-ios-green'];

export default function LandingPage() {
  return (
    <main className="min-h-[100dvh] bg-background">
      <header className="material sticky top-0 z-20 flex h-14 items-center justify-between gap-6 border-b border-border px-6">
        <Link href="/" className="flex items-center gap-2.5">
          <span className="icon-tile size-7 bg-gradient-to-br from-ios-orange to-ios-pink text-xs font-bold">
            D
          </span>
          <span className="text-sm font-semibold tracking-tight">DuckDocs</span>
        </Link>
        <nav aria-label="Sections" className="flex items-center gap-1">
          <a
            href="#principles"
            className="hidden h-9 items-center rounded-lg px-3 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground sm:inline-flex"
          >
            Principles
          </a>
          <a
            href="#how"
            className="hidden h-9 items-center rounded-lg px-3 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground sm:inline-flex"
          >
            How it works
          </a>
          <Button asChild variant="primary" size="sm">
            <Link href="/intelligence">Open workspace</Link>
          </Button>
        </nav>
      </header>

      <section className="mx-auto max-w-4xl px-6 pb-16 pt-24 text-center max-sm:pt-14">
        <h1 className="text-balance mx-auto max-w-3xl text-5xl font-bold leading-[1.05] tracking-[-0.03em] max-sm:text-3xl">
          Answers you can trace back to{' '}
          <span className="bg-gradient-to-br from-ios-orange via-ios-pink to-ios-purple bg-clip-text text-transparent">
            the page they came from
          </span>
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-muted-foreground max-sm:text-base">
          DuckDocs turns your own documents into a private, searchable workspace. Ask in plain language and get an
          answer that cites its sources — or an honest refusal when the evidence is not there.
        </p>
        <div className="mt-9 flex flex-wrap justify-center gap-3">
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
        <p className="mt-8 inline-flex items-center gap-1.5 text-xs text-muted-foreground">
          <LockKeyhole className="size-3.5" aria-hidden />
          Runs entirely on your machine
        </p>

        <div className="mx-auto mt-16 max-w-xl overflow-hidden rounded-2xl bg-card text-left shadow-xl ring-1 ring-inset ring-border">
          <div className="flex items-center justify-between border-b border-border bg-secondary/60 px-4 py-2.5">
            <span className="text-2xs font-semibold uppercase tracking-wider text-muted-foreground">
              Grounded answer
            </span>
            <Badge tone="success">
              <ShieldCheck className="size-3" aria-hidden />
              Cited
            </Badge>
          </div>
          <div className="p-5">
            <p className="text-sm leading-relaxed text-foreground">
              Records must remain on the local machine for 18 months before archival review.
            </p>
            <div className="mt-4 inline-flex items-center gap-2 rounded-lg bg-secondary px-2.5 py-1.5">
              <span className="grid size-5 place-items-center rounded bg-primary/15 font-mono text-[10px] text-primary">
                1
              </span>
              <span className="text-xs text-muted-foreground">retention-policy.pdf</span>
              <span className="font-mono text-2xs text-muted-foreground/70">p2 · 94%</span>
            </div>
          </div>
        </div>
      </section>

      <section id="principles" className="border-t border-border py-20">
        <div className="mx-auto max-w-4xl px-6">
          <h2 className="text-2xl font-bold tracking-tight">Built for documents you actually have to trust</h2>
          <p className="mt-3 max-w-2xl text-base leading-relaxed text-muted-foreground">
            Cloud assistants answer fluently but hide where the answer came from, and they want your files. DuckDocs
            closes that gap: one local library, retrieval you can audit, and uncertainty stated plainly.
          </p>
          <div className="mt-8 grid gap-4 sm:grid-cols-3">
            {PILLARS.map((pillar) => {
              const Icon = pillar.icon;
              return (
                <article
                  key={pillar.title}
                  className="rounded-2xl bg-card p-5 shadow-sm transition-all duration-200 ease-spring hover:-translate-y-0.5 hover:shadow-lg"
                >
                  <span className={`icon-tile mb-4 size-10 ${pillar.tile}`}>
                    <Icon className="size-5" strokeWidth={2} aria-hidden />
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
          <h2 className="text-2xl font-bold tracking-tight">How a question becomes a grounded answer</h2>
          <p className="mt-3 max-w-2xl text-base leading-relaxed text-muted-foreground">
            Four stages, with a mandatory checkpoint before anything reaches you.
          </p>
          <ol className="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map((step, index) => (
              <li key={step.title}>
                <span
                  className={cn(
                    'inline-grid size-7 place-items-center rounded-lg font-mono text-xs font-semibold text-white',
                    STEP_TILES[index] ?? 'bg-ios-gray',
                  )}
                >
                  {index + 1}
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
