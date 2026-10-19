import { Suspense } from "react";

import { CategoryNav, CategoryNavView } from "@/components/CategoryNav";

export default function ExploreLayout({ children }: LayoutProps<"/explore">) {
  return (
    <div className="mx-auto grid w-full max-w-7xl grid-cols-[minmax(0,1fr)] gap-8 px-4 py-8 sm:px-6 lg:grid-cols-[230px_minmax(0,1fr)]">
      <aside className="min-w-0 lg:sticky lg:top-24 lg:self-start">
        <p className="eyebrow mb-3 hidden lg:block">Categories</p>
        <Suspense fallback={<CategoryNavView path="" />}>
          <CategoryNav />
        </Suspense>
      </aside>
      <div className="min-w-0">{children}</div>
    </div>
  );
}
