import type { Metadata } from 'next';
import { JetBrains_Mono, Sora } from 'next/font/google';
import './globals.css';

const sora = Sora({
  subsets: ['latin'],
  variable: '--font-sora',
  display: 'swap',
});

const jetbrains = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'DuckDocs | Evidence-aware document intelligence',
  description:
    'Local-first workspace for searching, asking, reviewing, and exporting from your document library with grounded citations.',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" data-theme="dark" data-density="dense" className={`${sora.variable} ${jetbrains.variable}`}>
      <body>{children}</body>
    </html>
  );
}
