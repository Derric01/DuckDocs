import Link from 'next/link';
import {
  ArrowRight,
  FileSearch,
  FolderOpen,
  LockKeyhole,
  MessageSquareQuote,
  Scale,
  Settings2,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';

const surfaces = [
  {
    href: '/library',
    title: 'Library',
    body: 'Upload PDFs, Office files, text, and more. DuckDocs indexes pages locally and tracks ingestion status.',
    icon: FolderOpen,
  },
  {
    href: '/intelligence',
    title: 'Intelligence',
    body: 'Ask grounded questions. Answers must cite retrieved passages or refuse when evidence is missing.',
    icon: MessageSquareQuote,
  },
  {
    href: '/review',
    title: 'Review',
    body: 'Inspect citations, compare versions, and keep annotation work next to the source passage.',
    icon: Scale,
  },
  {
    href: '/settings',
    title: 'Settings',
    body: 'Choose local Ollama models or optional remote providers. Secrets stay on this machine.',
    icon: Settings2,
  },
];

const flow = [
  {
    title: 'Ingest',
    body: 'Documents are parsed, chunked, and indexed with page and line anchors so every hit stays traceable.',
  },
  {
    title: 'Retrieve',
    body: 'Questions search by meaning against your local vector index, with keyword fallback when models are offline.',
  },
  {
    title: 'Generate',
    body: 'A chat model drafts only from retrieved context. It is never treated as the source of truth.',
  },
  {
    title: 'Ground',
    body: 'The grounding gate checks citations against supplied evidence. Unsupported claims become a clear refusal.',
  },
];

export default function LandingPage() {
  return (
    <main className="landing">
      <div className="landing-atmosphere" aria-hidden="true" />

      <header className="landing-top glass-panel">
        <div className="landing-brand" aria-label="DuckDocs">
          <span className="brand-mark">D</span>
          <div className="landing-brand-copy">
            <span className="landing-brand-name">DuckDocs</span>
            <span className="landing-brand-tag">Local evidence workspace</span>
          </div>
        </div>
        <nav className="landing-top-nav" aria-label="Landing">
          <a href="#how">How it works</a>
          <a href="#surfaces">Workspace</a>
          <a href="#privacy">Privacy</a>
          <Link className="button button-primary landing-cta-compact" href="/intelligence">
            Open workspace
            <ArrowRight size={14} strokeWidth={1.8} aria-hidden="true" />
          </Link>
        </nav>
      </header>

      <section className="landing-hero">
        <div className="landing-copy">
          <h1>DuckDocs</h1>
          <p className="landing-lede">
            A private document intelligence workspace. Search and ask against your own library, then verify every answer
            against the exact passage it came from.
          </p>
          <div className="landing-actions">
            <Link className="button button-primary landing-cta" href="/intelligence">
              Open workspace
              <ArrowRight size={15} strokeWidth={1.8} aria-hidden="true" />
            </Link>
            <Link className="button button-secondary landing-cta glass-chip" href="/library">
              Add documents
            </Link>
          </div>
          <p className="landing-boundary" role="note">
            <LockKeyhole size={14} strokeWidth={1.8} aria-hidden="true" />
            <span>Local by default. Nothing leaves this machine unless you configure a provider.</span>
          </p>
        </div>

        <aside className="landing-preview glass-panel" aria-label="Grounded answer preview">
          <div className="landing-preview-head">
            <span className="pane-kicker">Evidence object</span>
            <span className="landing-preview-status">
              <span className="live-indicator" />
              Grounded
            </span>
          </div>
          <div className="landing-preview-source">
            <strong>retention-policy.md</strong>
            <span className="mono">Page 02 · Lines 18-24</span>
          </div>
          <blockquote className="landing-preview-quote">
            Falcon records must stay on the local machine for 18 months before archival review.
          </blockquote>
          <div className="landing-preview-meta">
            <span>
              <ShieldCheck size={13} strokeWidth={1.8} aria-hidden="true" />
              Citation locked to source
            </span>
            <span className="mono">ev_falcon_02</span>
          </div>
        </aside>
      </section>

      <section className="landing-section" id="why">
        <div className="landing-section-inner">
          <h2>Built for serious document work</h2>
          <p className="landing-section-lede">
            Folders, email attachments, scans, and policy drafts rarely live in one searchable system. Cloud AI tools
            answer fluently but hide provenance, or send sensitive files off-machine. DuckDocs closes that gap: one local
            library, meaning-aware retrieval, and answers you can audit.
          </p>
          <ul className="landing-pillars">
            <li className="glass-panel">
              <FileSearch size={18} strokeWidth={1.7} aria-hidden="true" />
              <strong>Evidence is an object</strong>
              <span>Every generated answer exposes a path to its source. Citations open the inspector at the anchor.</span>
            </li>
            <li className="glass-panel">
              <LockKeyhole size={18} strokeWidth={1.7} aria-hidden="true" />
              <strong>Local-first is visible</strong>
              <span>The product tells you what leaves the machine. The default path needs no account and no cloud.</span>
            </li>
            <li className="glass-panel">
              <Sparkles size={18} strokeWidth={1.7} aria-hidden="true" />
              <strong>Models are assistants</strong>
              <span>Providers are swappable. The model drafts; the grounding gate decides what you see.</span>
            </li>
          </ul>
        </div>
      </section>

      <section className="landing-section" id="how">
        <div className="landing-section-inner">
          <h2>How a question becomes a grounded answer</h2>
          <p className="landing-section-lede">
            DuckDocs is not a chat wrapper around PDFs. Ingestion, retrieval, generation, and provenance are first-class
            stages with a single mandatory checkpoint.
          </p>
          <ol className="landing-flow">
            {flow.map((step) => (
              <li key={step.title} className="glass-panel">
                <strong>{step.title}</strong>
                <span>{step.body}</span>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="landing-section" id="surfaces">
        <div className="landing-section-inner">
          <h2>Four surfaces, one workflow</h2>
          <p className="landing-section-lede">
            Ask, inspect, annotate, compare, and export stay connected. Conversation should lead to action, not a dead-end
            chat transcript.
          </p>
          <div className="landing-surfaces">
            {surfaces.map((surface) => {
              const Icon = surface.icon;
              return (
                <Link key={surface.href} href={surface.href} className="landing-surface glass-panel">
                  <Icon size={18} strokeWidth={1.7} aria-hidden="true" />
                  <strong>{surface.title}</strong>
                  <span>{surface.body}</span>
                  <em>
                    Open {surface.title}
                    <ArrowRight size={13} strokeWidth={1.8} aria-hidden="true" />
                  </em>
                </Link>
              );
            })}
          </div>
        </div>
      </section>

      <section className="landing-section" id="privacy">
        <div className="landing-section-inner landing-privacy glass-panel">
          <div>
            <h2>Who it is for</h2>
            <p>
              Consultants, researchers, policy analysts, legal and compliance teams, engineers, and anyone who needs a
              private library with verifiable answers. Density is for daily experts; honesty is for trust.
            </p>
          </div>
          <div>
            <h2>What runs locally</h2>
            <p>
              The default stack is FastAPI, Postgres metadata, Chroma retrieval, and Ollama models on your machine. Cloud
              providers are optional and explicit. Honest states cover loading, low confidence, refusal, and provider
              failure.
            </p>
          </div>
        </div>
      </section>

      <footer className="landing-footer">
        <div className="landing-footer-inner">
          <div>
            <strong>DuckDocs</strong>
            <p>Private, evidence-aware document intelligence.</p>
          </div>
          <Link className="button button-primary landing-cta" href="/intelligence">
            Enter workspace
            <ArrowRight size={15} strokeWidth={1.8} aria-hidden="true" />
          </Link>
        </div>
      </footer>
    </main>
  );
}
