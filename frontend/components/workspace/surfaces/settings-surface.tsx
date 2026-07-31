'use client';

import { Cpu, LockKeyhole, Monitor, Moon, Plus, ShieldCheck, Sparkles, Sun } from 'lucide-react';
import { useEffect, useState } from 'react';
import {
  Badge,
  Button,
  Dialog,
  EmptyState,
  Field,
  Input,
  Segmented,
  Switch,
  useToast,
} from '@/components/ui';
import { useWorkspace } from '@/components/workspace/workspace-provider';
import { duckDocsApi, type ProviderConfigRecord } from '@/lib/api/client';
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

  const chooseTheme = (next: ThemeChoice) => {
    setTheme(next);
    applyTheme(next);
  };

  const chooseDensity = (next: Density) => {
    setDensity(next);
    applyDensity(next);
  };

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
    <div className="surface surface-narrow">
      <header className="surface-head">
        <div className="surface-head-row">
          <div>
            <h2>Settings</h2>
            <p>Control which models run, how the workspace looks, and what is allowed to leave this machine.</p>
          </div>
        </div>
      </header>

      <div className="settings-stack">
        <section className="settings-section">
          <header>
            <h3>Models</h3>
            <p>
              DuckDocs answers from your local evidence index. A model only drafts the wording — remote providers
              are opt-in and never enabled by default.
            </p>
          </header>

          <div className="head-actions" style={{ marginBottom: 'var(--space-4)' }}>
            <Button icon={Plus} onClick={() => void configureOllama()}>
              Configure Ollama
            </Button>
            <Button icon={Plus} onClick={() => setRemoteOpen(true)}>
              Add remote provider
            </Button>
          </div>

          {providersLoading ? (
            <p className="inline-state">Loading providers…</p>
          ) : providers.length === 0 ? (
            <EmptyState
              icon={Sparkles}
              title="No providers configured"
              description="DuckDocs falls back to built-in extractive answers and keyword retrieval, which need no model at all."
            />
          ) : (
            providers.map((provider) => (
              <ProviderRow
                key={provider.id}
                provider={provider}
                testing={testing === provider.id}
                onTest={() => void testProvider(provider.id)}
              />
            ))
          )}
        </section>

        <section className="settings-section">
          <header>
            <h3>Appearance</h3>
            <p>Dark is designed for long review sessions; comfortable density increases row height.</p>
          </header>

          <div className="setting-row">
            <div className="setting-copy">
              <strong>Theme</strong>
              <p>Follow the system setting, or pin one.</p>
            </div>
            <Segmented
              label="Theme"
              value={theme}
              onChange={chooseTheme}
              options={[
                { value: 'light', label: 'Light', icon: Sun },
                { value: 'dark', label: 'Dark', icon: Moon },
                { value: 'system', label: 'System', icon: Monitor },
              ]}
            />
          </div>

          <div className="setting-row">
            <div className="setting-copy">
              <strong>Comfortable density</strong>
              <p>Taller rows and more spacing in dense tables.</p>
            </div>
            <Switch
              label="Comfortable density"
              checked={density === 'comfortable'}
              onChange={(next) => chooseDensity(next ? 'comfortable' : 'dense')}
            />
          </div>
        </section>

        <section className="settings-section">
          <header>
            <h3>Processing</h3>
            <p>How documents are turned into searchable, citable evidence.</p>
          </header>

          <div className="callout">
            <Cpu size={18} strokeWidth={1.7} aria-hidden="true" />
            <div>
              <h3>On-device OCR</h3>
              <p>
                Scanned PDFs and images are recognized locally with PaddleOCR, falling back to Tesseract when its
                model weights are unavailable. Every page is processed — there is no page cap or quota — and each
                passage keeps its confidence score so low-quality recognition is labeled rather than hidden.
                Configure the engine and languages with <code className="mono">DUCKDOCS_OCR_ENGINE</code> and{' '}
                <code className="mono">DUCKDOCS_OCR_LANGUAGES</code>.
              </p>
            </div>
          </div>
        </section>

        <section className="settings-section">
          <header>
            <h3>Privacy</h3>
            <p>What runs locally, and what would leave this machine.</p>
          </header>

          <div className="callout">
            <LockKeyhole size={18} strokeWidth={1.7} aria-hidden="true" />
            <div>
              <h3>Your data boundary</h3>
              <p>
                Files, the evidence index, and OCR all stay on this machine. There is no analytics, telemetry, or
                crash reporting. A remote provider only receives text if you configure one, and it is labeled
                wherever it is used.
              </p>
            </div>
          </div>
        </section>
      </div>

      <RemoteProviderDialog
        open={remoteOpen}
        onClose={() => setRemoteOpen(false)}
        onSaved={async () => {
          setRemoteOpen(false);
          await refreshProviders();
          notify('Remote provider saved locally.', 'success');
        }}
        onError={(message) => notify(message, 'error')}
      />
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
    <div className="provider-row">
      <span className="provider-avatar" aria-hidden="true">
        {label.slice(0, 1)}
      </span>
      <div className="provider-copy">
        <div className="provider-title-row">
          <strong>{label}</strong>
          {provider.isDefault ? <Badge tone="accent">Default</Badge> : null}
          <Badge tone={provider.local ? 'neutral' : 'warning'}>{provider.local ? 'Local' : 'Remote'}</Badge>
        </div>
        <p>
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
 * Replaces the previous window.prompt() chain, which could not be styled,
 * validated, or cancelled cleanly, and showed the API key in a native dialog.
 */
function RemoteProviderDialog({
  open,
  onClose,
  onSaved,
  onError,
}: {
  open: boolean;
  onClose: () => void;
  onSaved: () => Promise<void>;
  onError: (message: string) => void;
}) {
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
    <Dialog
      open={open}
      onClose={onClose}
      title="Add a remote provider"
      description="Text you ask about will be sent to this provider. It stays opt-in and is labeled wherever it is used."
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="primary" loading={saving} onClick={() => void save()}>
            Save provider
          </Button>
        </>
      }
    >
      <Field label="Model name" hint="For example gpt-4.1-mini.">
        {(id) => <Input id={id} value={modelName} onChange={(event) => setModelName(event.target.value)} />}
      </Field>
      <Field label="Base URL" hint="Leave blank for OpenAI. Set it for any OpenAI-compatible endpoint.">
        {(id) => (
          <Input
            id={id}
            value={baseUrl}
            placeholder="https://…"
            onChange={(event) => setBaseUrl(event.target.value)}
          />
        )}
      </Field>
      <Field label="API key" hint="Stored on this machine and never written to logs.">
        {(id) => (
          <Input
            id={id}
            type="password"
            value={apiKey}
            autoComplete="off"
            onChange={(event) => setApiKey(event.target.value)}
          />
        )}
      </Field>
      <p className="field-hint">
        <ShieldCheck size={12} strokeWidth={1.8} style={{ display: 'inline', verticalAlign: -2 }} aria-hidden="true" />{' '}
        Local providers remain the default until you explicitly change it.
      </p>
    </Dialog>
  );
}
