"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { CompassIcon, MicIcon, ScanIcon, SearchIcon } from "./Icons";

export const TABS = [
  { href: "/explore", label: "Explore", Icon: CompassIcon },
  { href: "/scan", label: "Scan", Icon: ScanIcon },
  { href: "/lookup", label: "Lookup", Icon: SearchIcon },
  { href: "/assistant", label: "Assistant", Icon: MicIcon },
] as const;

function isActive(path: string, href: string): boolean {
  return path === href || path.startsWith(`${href}/`);
}

/** Desktop: tabs in the header. */
export function HeaderTabs() {
  return <HeaderTabsView path={usePathname()} />;
}

// The URL is request-time data: these render without a highlight until it streams in.
export function HeaderTabsView({ path }: { path: string }) {
  return (
    <nav aria-label="App" className="hidden items-center gap-1 rounded-full bg-zinc-100/80 p-1 md:flex">
      {TABS.map(({ href, label, Icon }) => {
        const active = isActive(path, href);
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={`flex items-center gap-2 rounded-full px-4 py-1.5 text-sm font-medium transition ${
              active ? "bg-white text-zinc-900 shadow-sm ring-1 ring-zinc-200" : "text-zinc-600 hover:text-zinc-900"
            }`}
          >
            <Icon className="h-4 w-4" />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}

/** Phones: a bottom tab bar, like a native app. */
export function BottomTabs() {
  return <BottomTabsView path={usePathname()} />;
}

export function BottomTabsView({ path }: { path: string }) {
  return (
    <nav
      aria-label="App tabs"
      className="fixed inset-x-0 bottom-0 z-30 border-t border-zinc-200 bg-white/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden"
    >
      <ul className="grid grid-cols-4">
        {TABS.map(({ href, label, Icon }) => {
          const active = isActive(path, href);
          return (
            <li key={href}>
              <Link
                href={href}
                aria-current={active ? "page" : undefined}
                className={`flex flex-col items-center gap-1 py-2.5 text-[11px] font-medium ${
                  active ? "text-emerald-700" : "text-zinc-600"
                }`}
              >
                <Icon className="h-5 w-5" />
                {label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
