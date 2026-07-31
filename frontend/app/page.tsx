import { ArrowRight, FileSearch, LockKeyhole, ScanText, ShieldCheck } from 'lucide-react';
import Link from 'next/link';

const PILLARS = [
  {
    icon: FileSearch,
    title: 'Evidence is an object',
    body: 'Every claim in an answer carries a citation that opens the exact passage it came from — page, lines, and confidence included.',
  },
  {
    icon: LockKeyhole,
    title: 'Local by default',
    body: 'Documents, the search index, and OCR all run on this machine. No account, no telemetry, no background uploads.',
  },
  {
    icon: ScanText,
    title: 'Scans are first-class',
    body: 'Scanned PDFs and photographed pages are recognized on-device with no page cap, and low-confidence text is labeled rather than hidden.',
  },
];

const STEPS = [
  { title: 'Ingest', body: 'Files are parsed page by page. Anything without a text layer is sent through local OCR.' },
  { title: 'Retrieve', body: 'Questions search by meaning against a local index, with keyword fallback when no model is running.' },
  { title: 'Ground', body: 'A model drafts only from retrieved passages. Unsupported claims are refused, not smoothed over.' },
  { title: 'Verify', body: 'Open any citation to read the source passage and judge it yourself.' },
];

export default function LandingPage() {
  return (
    <main className="landing">
      <header className="landing-nav">
        <Link href="/" className="brand">
          <span className="brand-mark" aria-hidden="true">
            D
          </span>
          <span>
            <span className="brand-name">DuckDocs</span>
          </span>
        </Link>
        <nav className="landing-nav-links" aria-label="Sections">
          <a href="#principles">Principles</a>
          <a href="#how">How it works</a>
          <Link className="btn btn-primary btn-sm" href="/intelligence">
            Open workspace
          </Link>
        </nav>
      </header>

      <section className="landing-inner hero">
        <h1>Answers you can trace back to the page they came from</h1>
        <p className="hero-lede">
          DuckDocs turns your own documents into a private, searchable workspace. Ask a question in plain language and
          get an answer that cites its sources — or an honest refusal when the evidence is not there.
        </p>
        <div className="hero-actions">
          <Link className="btn btn-primary btn-lg" href="/intelligence">
            Open workspace
            <ArrowRight size={15} strokeWidth={1.8} aria-hidden="true" />
          </Link>
          <Link className="btn btn-secondary btn-lg" href="/library">
            Add documents
          </Link>
        </div>
        <p className="hero-note">
          <LockKeyhole size={13} strokeWidth={1.8} aria-hidden="true" />
          Runs entirely on your machine
        </p>

        <div className="hero-preview">
          <div className="hero-preview-head">
            <span className="kicker">Grounded answer</span>
            <span className="badge badge-success">
              <ShieldCheck size={11} strokeWidth={2} aria-hidden="true" />
              Cited
            </span>
          </div>
          <div className="hero-preview-body">
            <p className="hero-preview-answer">
              Records must remain on the local machine for 18 months before archival review.
              <span className="citation-chip" aria-hidden="true">
                1
              </span>
            </p>
            <div className="citation-list">
              <span className="citation-source">
                <span className="ord" aria-hidden="true">
                  1
                </span>
                <span className="name">retention-policy.pdf</span>
                <span className="mono">p2 · 94%</span>
              </span>
            </div>
          </div>
        </div>
      </section>

      <section className="landing-section" id="principles">
        <div className="landing-inner">
          <h2>Built for documents you actually have to trust</h2>
          <p>
            Cloud assistants answer fluently but hide where the answer came from, and they want your files. DuckDocs
            closes that gap: one local library, retrieval you can audit, and uncertainty stated plainly.
          </p>
          <div className="feature-grid">
            {PILLARS.map((pillar) => {
              const Icon = pillar.icon;
              return (
                <article className="feature" key={pillar.title}>
                  <Icon size={18} strokeWidth={1.7} aria-hidden="true" />
                  <strong>{pillar.title}</strong>
                  <p>{pillar.body}</p>
                </article>
              );
            })}
          </div>
        </div>
      </section>

      <section className="landing-section" id="how">
        <div className="landing-inner">
          <h2>How a question becomes a grounded answer</h2>
          <p>Four stages, with a mandatory checkpoint before anything reaches you.</p>
          <div className="step-grid">
            {STEPS.map((step) => (
              <article className="step" key={step.title}>
                <strong>{step.title}</strong>
                <p>{step.body}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <footer className="landing-inner landing-foot">
        <span>DuckDocs — private, evidence-aware document intelligence.</span>
        <Link className="btn btn-secondary btn-sm" href="/intelligence">
          Open workspace
          <ArrowRight size={13} strokeWidth={1.8} aria-hidden="true" />
        </Link>
      </footer>
    </main>
  );
}
