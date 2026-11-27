import type { ReactNode } from 'react';
import { DEFAULT_LOCALE } from '@/shared/config';
import '../styles/globals.css';

interface RootLayoutProps {
  children: ReactNode;
}

export const RootLayout = ({ children }: RootLayoutProps): ReactNode => (
  <html lang={DEFAULT_LOCALE}>
    <body>{children}</body>
  </html>
);
