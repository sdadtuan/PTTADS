import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'PTT Client Portal',
  description: 'Campaign performance and approvals for PTT agency clients',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="vi">
      <body>{children}</body>
    </html>
  );
}
