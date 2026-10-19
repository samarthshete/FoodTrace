"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { CATEGORIES } from "@/lib/explore";

const ALL = { id: "", label: "Top foods", emoji: "✦" };

/** Explore's category list: a sidebar on desktop, scrolling chips on phones. */
export function CategoryNav() {
  return <CategoryNavView path={usePathname()} />;
}

export function CategoryNavView({ path }: { path: string }) {
  const items = [ALL, ...CATEGORIES];
  const href = (id: string) => (id ? `/explore/${id}` : "/explore");
  return (
    <nav aria-label="Categories">
      <ul className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 lg:mx-0 lg:flex-col lg:gap-0.5 lg:overflow-visible lg:px-0">
        {items.map((c) => {
          const active = path === href(c.id);
          return (
            <li key={c.id || "all"} className="shrink-0">
              <Link
                href={href(c.id)}
                aria-current={active ? "page" : undefined}
                className={`flex items-center gap-3 rounded-full px-3.5 py-2 text-sm font-medium whitespace-nowrap transition lg:rounded-xl ${
                  active
                    ? "bg-zinc-900 text-white lg:bg-zinc-100 lg:text-zinc-900"
                    : "bg-zinc-100 text-zinc-700 hover:text-zinc-900 lg:bg-transparent lg:hover:bg-zinc-50"
                }`}
              >
                <span aria-hidden="true" className="w-5 text-center">
                  {c.emoji}
                </span>
                {c.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
