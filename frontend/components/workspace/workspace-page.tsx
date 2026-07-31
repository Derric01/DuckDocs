'use client';

/**
 * One entry point per route: providers, shell chrome, then the surface.
 * Routes stay thin server components that name their surface.
 */

import { ToastProvider } from '@/components/ui';
import { AppShell } from '@/components/workspace/app-shell';
import { WorkspaceProvider } from '@/components/workspace/workspace-provider';
import { AskSurface } from '@/components/workspace/surfaces/ask-surface';
import { LibrarySurface } from '@/components/workspace/surfaces/library-surface';
import { ReviewSurface } from '@/components/workspace/surfaces/review-surface';
import { SettingsSurface } from '@/components/workspace/surfaces/settings-surface';
import type { Surface } from '@/lib/types';

const SURFACES: Record<Surface, () => React.JSX.Element> = {
  intelligence: AskSurface,
  library: LibrarySurface,
  review: ReviewSurface,
  settings: SettingsSurface,
};

export function WorkspacePage({ surface }: { surface: Surface }) {
  const Surface = SURFACES[surface];
  return (
    <ToastProvider>
      <WorkspaceProvider>
        <AppShell surface={surface}>
          <Surface />
        </AppShell>
      </WorkspaceProvider>
    </ToastProvider>
  );
}
