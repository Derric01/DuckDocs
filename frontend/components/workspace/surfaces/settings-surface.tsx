'use client';

import { Cpu, LockKeyhole, Monitor, Moon, Plus, ShieldCheck, Sparkles, Sun } from 'lucide-react';
import { useEffect, useId, useState } from 'react';
import {
  Badge,
  Button,
  Dialog,
  DialogContent,
  EmptyState,
  Field,
  Input,
  Switch,
  Tabs,
  TabsList,
  TabsTrigger,
  useToast,
} from '@/components/ui';
import { useWorkspace } from '@/components/workspace/workspace-provider';
import { duckDocsApi, type ProviderConfigRecord } from '@/lib/api/client';
import { cn } from '@/lib/utils';
import { applyDensity, applyTheme, readDensity, readTheme, type Density, type ThemeChoice } from '@/lib/theme';

const PROVIDER_LABEL: Record<string, string> = {
  ollama: 'Ollama',
  extractive: 'Built-in extractive',
  keyword: 'Keyword index',
  openai: 'OpenAI',
  openai_compatible: 'OpenAI-compatible',
  anthropic: 'Anthropic',
  gemini: 'Gemini',
};

export function SettingsSurface() {
  const { providers, providersLoading, refreshProviders, connection } = useWorkspace();
  const { notify } = useToast();

  const [theme, setTheme] = useState<ThemeChoice>('system');
  const [density, setDensity] = useState<Density>('dense');
  const [testing, setTesting] = useState<string | null>(null);
  const [remoteOpen, setRemoteOpen] = useState(false);

  useEffect(() => {
    setTheme(readTheme());
    setDensity(readDensity());
  }, []);

  useEffect(() => {
    if (connection !== 'offline') void refreshProviders();
  }, [connection, refreshProviders]);

  const configureOllama = async () => {
    if (connection === 'offline') {
      notify('Start the DuckDocs API to configure providers.', 'error');
      return;
    }
    try {
      await duckDocsApi.createProviderConfig({
        role: 'chat',
        providerType: 'ollama',
        modelName: 'llama3.2:1b',
        baseUrl: 'http://ollama:11434',
        isDefault: true,
      });
      await duckDocsApi.createProviderConfig({
        role: 'embedding',
        providerType: 'ollama',
        modelName: 'nomic-embed-text',
        baseUrl: 'http://ollama:11434',
        isDefault: true,
      });
      await refreshProviders();
      notify('Ollama configured as the default chat and embedding provider.', 'success');
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Could not configure Ollama.', 'error');
    }
  };

  const testProvider = async (id: string) => {
    setTesting(id);
    try {
      const result = await duckDocsApi.testProviderConfig(id);
      notify(
        result.reachable
          ? `Reachable${result.latency_ms != null ? ` in ${Math.round(result.latency_ms)} ms` : ''}.`
          : `Unreachable${result.error ? `: ${result.error}` : '.'}`,
        result.reachable ? 'success' : 'error',
      );
      await refreshProviders();
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Provider test failed.', 'error');
    } finally {
      setTesting(null);
    }
  };

  return (
    <div className="mx-auto max-w-3xl px-8 pb-16 pt-8 max-sm:px-4 max-sm:pt-5">
      <header className="mb-8 border-b border-border pb-5">
        <h2 className="font-display text-3xl text-foreground">Settings</h2>
        <p className="mt-1.5 max-w-prose text-sm text-muted-foreground">
          Control which models run, how the workspace looks, and what is allowed to leave this machine.
        </p>
      </header>

      <div className="space-y-10">
        <Section
          icon={Sparkles}
          title="Models"
          description="DuckDocs answers from your local evidence index. A model only drafts the wording — remote providers are opt-in and never enabled by default."
        >
          <div className="mb-4 flex flex-wrap gap-2">
            <Button onClick={() => void configureOllama()}>
              <Plus className="size-3.5" aria-hidden />
              Configure Ollama
            </Button>
            <Button onClick={() => setRemoteOpen(true)}>
              <Plus className="size-3.5" aria-hidden />
              Add remote provider
            </Button>
          </div>

          {providersLoading ? (
            <p className="py-3 text-sm text-muted-foreground">Loading providers…</p>
          ) : providers.length === 0 ? (
            <EmptyState
              icon={Sparkles}
              title="No providers configured"
              description="DuckDocs falls back to built-in extractive answers and keyword retrieval, which need no model at all."
            />
          ) : (
            <div className="overflow-hidden rounded-lg border border-border bg-card">
              {providers.map((provider) => (
                <ProviderRow
                  key={provider.id}
                  provider={provider}
                  testing={testing === provider.id}
                  onTest={() => void testProvider(provider.id)}
                />
              ))}
            </div>
          )}
        </Section>

        <Section icon={Moon} title="Appearance" description="Dark is designed for long review sessions.">
          <div className="overflow-hidden rounded-lg border border-border bg-card">
            <div className="table-row-hairline flex min-h-[56px] items-center justify-between gap-4 px-4">
              <div>
                <p className="text-sm font-medium text-foreground">Theme</p>
                <p className="mt-0.5 text-xs text-muted-foreground">Follow the system setting, or pin one.</p>
              </div>
              <Tabs
                value={theme}
                onValueChange={(value) => {
                  setTheme(value as ThemeChoice);
                  applyTheme(value as ThemeChoice);
                }}
              >
                <TabsList>
                  <TabsTrigger value="light">
                    <Sun className="size-3.5" aria-hidden />
                    Light
                  </TabsTrigger>
                  <TabsTrigger value="dark">
                    <Moon className="size-3.5" aria-hidden />
                    Dark
                  </TabsTrigger>
                  <TabsTrigger value="system">
                    <Monitor className="size-3.5" aria-hidden />
                    Auto
                  </TabsTrigger>
                </TabsList>
              </Tabs>
            </div>

            <div className="table-row-hairline flex min-h-[56px] items-center justify-between gap-4 px-4">
              <div>
                <p className="text-sm font-medium text-foreground">Comfortable density</p>
                <p className="mt-0.5 text-xs text-muted-foreground">Taller rows and more spacing.</p>
              </div>
              <Switch
                aria-label="Comfortable density"
                checked={density === 'comfortable'}
                onCheckedChange={(checked) => {
                  const next: Density = checked ? 'comfortable' : 'dense';
                  setDensity(next);
                  applyDensity(next);
                }}
              />
            </div>
          </div>
        </Section>

        <Section icon={Cpu} title="Processing" description="How documents become searchable, citable evidence.">
          <Callout icon={Cpu} title="On-device OCR">
            Scanned PDFs and images are recognized locally with RapidOCR, falling back to Tesseract when its
            bundled models are unavailable. Every page is processed — there is no page cap or quota — and each
            passage keeps its confidence score so low-quality recognition is labeled rather than hidden. Configure
            with <code className="rounded-sm border border-border bg-muted px-1 py-0.5 font-mono text-2xs">DUCKDOCS_OCR_ENGINE</code>{' '}
            and{' '}
            <code className="rounded-sm border border-border bg-muted px-1 py-0.5 font-mono text-2xs">DUCKDOCS_OCR_LANGUAGES</code>.
          </Callout>
        </Section>

        <Section icon={LockKeyhole} title="Privacy" description="What runs locally, and what would leave this machine.">
          <Callout icon={LockKeyhole} title="Your data boundary">
            Files, the evidence index, and OCR all stay on this machine. There is no analytics, telemetry, or crash
            reporting. A remote provider only receives text if you configure one, and it is labeled wherever it is
            used.
          </Callout>
        </Section>
      </div>

      <Dialog open={remoteOpen} onOpenChange={setRemoteOpen}>
        <RemoteProviderDialog
          onSaved={async () => {
            setRemoteOpen(false);
            await refreshProviders();
            notify('Remote provider saved locally.', 'success');
          }}
          onError={(message) => notify(message, 'error')}
        />
      </Dialog>
    </div>
  );
}

function Section({
  icon: Icon,
  title,
  description,
  children,
}: {
  icon: typeof Cpu;
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <header className="mb-3">
        <h3 className="flex items-center gap-2 text-base font-semibold text-foreground">
          <Icon className="size-4 text-muted-foreground" strokeWidth={1.8} aria-hidden />
          {title}
        </h3>
        <p className="mt-1 max-w-prose text-sm text-muted-foreground">{description}</p>
      </header>
      {children}
    </section>
  );
}

function Callout({
  icon: Icon,
  title,
  children,
}: {
  icon: typeof Cpu;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex gap-3.5 rounded-lg border border-border bg-card p-4">
      <span className="grid size-8 shrink-0 place-items-center rounded-sm border border-border bg-muted text-muted-foreground">
        <Icon className="size-4" strokeWidth={1.7} aria-hidden />
      </span>
      <div>
        <h4 className="text-sm font-semibold text-foreground">{title}</h4>
        <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{children}</p>
      </div>
    </div>
  );
}

function ProviderRow({
  provider,
  testing,
  onTest,
}: {
  provider: ProviderConfigRecord;
  testing: boolean;
  onTest: () => void;
}) {
  const label = PROVIDER_LABEL[provider.providerType] ?? provider.providerType;
  return (
    <div className="table-row-hairline flex min-h-[64px] items-center gap-3 px-4 py-2.5">
      {/* Tinted the same way the Local/Remote badge beside it reads: this is
          the one place local-vs-remote is worth a colour, not decoration. */}
      <span
        className={cn(
          'grid size-8 shrink-0 place-items-center rounded-sm border text-xs font-semibold',
          provider.local
            ? 'border-success/25 bg-success-muted text-success'
            : 'border-accent/25 bg-accent-muted text-accent',
        )}
      >
        {label.slice(0, 1)}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-sm font-medium text-foreground">{label}</span>
          {provider.isDefault ? <Badge tone="accent">Default</Badge> : null}
          <Badge tone={provider.local ? 'neutral' : 'warning'}>{provider.local ? 'Local' : 'Remote'}</Badge>
        </div>
        <p className="mt-0.5 truncate font-mono text-2xs text-muted-foreground">
          {provider.modelName || 'No model set'}
          {provider.baseUrl ? ` · ${provider.baseUrl}` : ''}
        </p>
      </div>
      <Badge tone={provider.connected ? 'success' : 'neutral'}>
        {provider.connected ? 'Connected' : 'Not connected'}
      </Badge>
      <Button size="sm" onClick={onTest} loading={testing}>
        Test
      </Button>
    </div>
  );
}

/**
 * Replaces the earlier window.prompt() chain, which could not be styled or
 * validated and showed the API key in a native dialog.
 */
function RemoteProviderDialog({
  onSaved,
  onError,
}: {
  onSaved: () => Promise<void>;
  onError: (message: string) => void;
}) {
  const modelId = useId();
  const urlId = useId();
  const keyId = useId();

  const [modelName, setModelName] = useState('gpt-4.1-mini');
  const [baseUrl, setBaseUrl] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [saving, setSaving] = useState(false);

  const save = async () => {
    if (!apiKey.trim()) {
      onError('An API key is required.');
      return;
    }
    setSaving(true);
    try {
      await duckDocsApi.createProviderConfig({
        role: 'chat',
        providerType: baseUrl.trim() ? 'openai_compatible' : 'openai',
        modelName: modelName.trim() || 'gpt-4.1-mini',
        baseUrl: baseUrl.trim() || null,
        apiKey: apiKey.trim(),
        isDefault: false,
      });
      setApiKey('');
      await onSaved();
    } catch (error) {
      onError(error instanceof Error ? error.message : 'Could not save the provider.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <DialogContent
      title="Add a remote provider"
      description="Text you ask about will be sent to this provider. It stays opt-in and is labeled wherever it is used."
      footer={
        <Button variant="primary" loading={saving} onClick={() => void save()}>
          Save provider
        </Button>
      }
    >
      <Field label="Model name" hint="For example gpt-4.1-mini." htmlFor={modelId}>
        <Input id={modelId} value={modelName} onChange={(event) => setModelName(event.target.value)} />
      </Field>
      <Field
        label="Base URL"
        hint="Leave blank for OpenAI. Set it for any OpenAI-compatible endpoint."
        htmlFor={urlId}
      >
        <Input
          id={urlId}
          value={baseUrl}
          placeholder="https://…"
          onChange={(event) => setBaseUrl(event.target.value)}
        />
      </Field>
      <Field label="API key" hint="Stored on this machine and never written to logs." htmlFor={keyId}>
        <Input
          id={keyId}
          type="password"
          value={apiKey}
          autoComplete="off"
          onChange={(event) => setApiKey(event.target.value)}
        />
      </Field>
      <p className="flex items-start gap-1.5 text-xs text-muted-foreground">
        <ShieldCheck className="mt-px size-3.5 shrink-0" aria-hidden />
        Local providers remain the default until you explicitly change it.
      </p>
    </DialogContent>
  );
}
