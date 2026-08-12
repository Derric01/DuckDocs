import type { Metadata } from 'next';
import { Inter, JetBrains_Mono, Newsreader } from 'next/font/google';
import { THEME_BOOTSTRAP } from '@/lib/theme';
import './globals.css';

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
});

/**
 * The display face. A serif for titles is what separates a document tool from
 * a dashboard — it borrows authority from print, where the source material
 * comes from. Used for page titles and the landing hero only; never for UI
 * chrome, which stays in the sans.
 */
const newsreader = Newsreader({
  subsets: ['latin'],
  variable: '--font-display',
  display: 'swap',
  weight: ['400', '500'],
  style: ['normal', 'italic'],
});

const jetbrains = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-mono-jetbrains',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'DuckDocs — Evidence-aware document intelligence',
  description:
    'A local-first workspace for searching and asking questions across your own documents, with every answer traceable to the passage it came from.',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${inter.variable} ${newsreader.variable} ${jetbrains.variable}`}
    >
      <head>
        {/* Applies the stored theme before first paint so a reload never flashes. */}
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOTSTRAP }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
