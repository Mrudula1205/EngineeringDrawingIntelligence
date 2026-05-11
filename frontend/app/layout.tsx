import type { ReactNode } from "react";

import "./globals.css";

export const metadata = {
  title: "DocIntelligence",
  description: "Sheet metal drawing extraction",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="page-shell">
          <header className="app-header">
            <div className="brand">
              <span className="brand-dot" aria-hidden="true" />
              <div>
                <p className="brand-title">DocIntelligence</p>
                <p className="brand-subtitle">Sheet metal drawing extraction</p>
              </div>
            </div>
            <nav className="header-actions">
              <a className="header-link" href="https://cloud.google.com/" target="_blank" rel="noreferrer">
                GCP Console
              </a>
            </nav>
          </header>
          <main className="app-main">{children}</main>
        </div>
      </body>
    </html>
  );
}
