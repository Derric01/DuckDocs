import type { Metadata } from 'next';
import { Inter, JetBrains_Mono } from 'next/font/google';
import { THEME_BOOTSTRAP } from '@/lib/theme';
import './globals.css';

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
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
    <html lang="en" suppressHydrationWarning className={`${inter.variable} ${jetbrains.variable}`}>
      <head>
        {/* Applies the stored theme before first paint so a reload never flashes. */}
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOTSTRAP }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
