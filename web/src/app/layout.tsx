import type { Metadata, Viewport } from "next";

import { Inter } from "next/font/google";
import Link from "next/link";
import { Suspense } from "react";

import { BottomTabs, BottomTabsView, HeaderTabs, HeaderTabsView } from "@/components/AppNav";
import { ProductFooter as SiteFooter } from "@/components/ProductView";
import { RegisterServiceWorker } from "@/components/RegisterServiceWorker";
import { UserMenu } from "@/components/UserMenu";
import { PRODUCT_INITIALS, PRODUCT_NAME, PRODUCT_TAGLINE } from "@/lib/brand";

import "./globals.css";

// Self-hosted at build time by next/font: no request to Google at runtime.
const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });

export const metadata: Metadata = {
  title: { default: PRODUCT_NAME, template: `%s · ${PRODUCT_NAME}` },
  description: PRODUCT_TAGLINE,
  applicationName: PRODUCT_NAME,
  appleWebApp: { capable: true, title: PRODUCT_NAME, statusBarStyle: "default" },
};

export const viewport: Viewport = {
  themeColor: "#ffffff",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`h-full antialiased ${inter.variable}`}>
      <body className="flex min-h-full flex-col">
        <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 btn-primary">
          Skip to content
        </a>
        <header className="sticky top-0 z-30 border-b border-zinc-200/80 bg-white/85 backdrop-blur-md">
          <div className="mx-auto flex h-16 w-full max-w-7xl items-center justify-between gap-4 px-4 sm:px-6">
            <Link href="/" className="flex items-center gap-2.5 font-semibold tracking-tight">
              <span aria-hidden="true" className="grid h-8 w-8 place-items-center rounded-xl bg-emerald-700 text-sm font-bold text-white shadow-sm">
                {PRODUCT_INITIALS}
              </span>
              <span>{PRODUCT_NAME}</span>
            </Link>
            <Suspense fallback={<HeaderTabsView path="" />}>
              <HeaderTabs />
            </Suspense>
            <div className="flex items-center gap-4">
              <Link href="/methodology" className="hidden text-sm font-medium text-zinc-600 hover:text-zinc-900 lg:block">
                How it works
              </Link>
              {/* Reads the URL (to return after sign-in), so it must be inside Suspense. */}
              <Suspense fallback={null}>
                <UserMenu />
              </Suspense>
            </div>
          </div>
        </header>
        <main id="main" className="w-full flex-1">
          {children}
        </main>
        <SiteFooter />
        <Suspense fallback={<BottomTabsView path="" />}>
          <BottomTabs />
        </Suspense>
        <RegisterServiceWorker />
      </body>
    </html>
  );
}
