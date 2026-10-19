import Link from "next/link";

import type { Alternatives, Breakdown, Product, Recalls } from "@/lib/api";
import { PRODUCT_INITIALS, PRODUCT_NAME, PRODUCT_TAGLINE } from "@/lib/brand";
import {
  bandStyle,
  classLabel,
  componentBars,
  dataBadge,
  groupBreakdown,
  isRescaled,
  missingWords,
} from "@/lib/present";

import { AlternativesStrip } from "./AlternativesStrip";
import { ProductAccount } from "./ProductAccount";
import { RecallBanner } from "./RecallBanner";
import { VoicePanel } from "./VoicePanel";

const BADGE_STYLES = {
  complete: "bg-emerald-50 text-emerald-900",
  partial: "bg-amber-50 text-amber-900",
  limited: "bg-rose-50 text-rose-900",
};

export function ProductFooter() {
  return (
    <footer className="mt-16 border-t border-zinc-200 bg-zinc-50/60 pb-24 md:pb-0">
      <div className="mx-auto grid w-full max-w-6xl gap-8 px-4 py-10 text-sm text-zinc-600 sm:px-6 md:grid-cols-[2fr_1fr_1fr]">
        <div className="flex flex-col gap-2">
          <p className="flex items-center gap-2 font-semibold text-zinc-900">
            <span aria-hidden="true" className="grid h-6 w-6 place-items-center rounded-lg bg-emerald-700 text-xs text-white">
              {PRODUCT_INITIALS}
            </span>
            {PRODUCT_NAME}
          </p>
          <p>{PRODUCT_TAGLINE}</p>
          <p className="max-w-sm">
            A 0–100 health score for US groceries where every point traces back to a rule and a cited source.
          </p>
          <p>Educational information, not medical advice.</p>
        </div>
        <nav aria-label="Site" className="flex flex-col gap-2">
          <p className="font-semibold text-zinc-900">Learn</p>
          <Link href="/methodology" className="hover:text-zinc-900">
            How the score works
          </Link>
          <Link href="/about" className="hover:text-zinc-900">
            About
          </Link>
          <Link href="/privacy" className="hover:text-zinc-900">
            Privacy
          </Link>
        </nav>
        <div className="flex flex-col gap-2">
          <p className="font-semibold text-zinc-900">Data</p>
          <p>
            Data from{" "}
            <a className="underline hover:text-zinc-900" href="https://world.openfoodfacts.org">
              Open Food Facts (ODbL)
            </a>
            .
          </p>
          <p>Recalls from openFDA. Additive status from the FDA.</p>
        </div>
      </div>
    </footer>
  );
}

const RING_COLORS: Record<string, string> = {
  excellent: "stroke-emerald-600",
  good: "stroke-lime-600",
  mediocre: "stroke-amber-500",
  poor: "stroke-rose-600",
};

/** A 0–100 ring gauge; decorative, the number beside it carries the meaning. */
export function ScoreRing({ total, bandId, size = 112 }: { total: number; bandId?: string; size?: number }) {
  const r = 42;
  const c = 2 * Math.PI * r;
  return (
    <svg aria-hidden="true" width={size} height={size} viewBox="0 0 100 100" className="shrink-0 -rotate-90">
      <circle cx="50" cy="50" r={r} fill="none" strokeWidth="9" className="stroke-zinc-100" />
      <circle
        cx="50"
        cy="50"
        r={r}
        fill="none"
        strokeWidth="9"
        strokeLinecap="round"
        strokeDasharray={c}
        strokeDashoffset={c * (1 - Math.max(0, Math.min(100, total)) / 100)}
        className={(bandId && RING_COLORS[bandId]) || "stroke-zinc-400"}
      />
    </svg>
  );
}

function ScoreHeader({ product }: { product: Product }) {
  const { score } = product;
  if (score.status === "not_scored") {
    const missing = missingWords(score.missing_inputs).join(", ");
    return (
      <div className="rounded-2xl bg-zinc-50 p-5 ring-1 ring-zinc-200">
        <p className="text-2xl font-semibold">Not scored</p>
        <p className="mt-1 text-sm text-zinc-600">The label data is missing {missing}.</p>
      </div>
    );
  }
  return (
    <div className="flex items-center gap-5">
      <div className="relative">
        <ScoreRing total={score.total ?? 0} bandId={score.band?.id} />
        <p className="absolute inset-0 grid place-items-center text-3xl font-semibold tabular-nums">{score.total}</p>
      </div>
      <div>
        <p className="text-sm text-zinc-600">
          Health score <span>/ 100</span>
        </p>
        <p className={`mt-1 inline-block rounded-full px-3 py-1 text-base font-semibold ring-1 ${bandStyle(score.band?.id)}`}>
          {score.band?.label}
        </p>
      </div>
    </div>
  );
}

/** PAGE-17: full additive marks mean no EFSA-rated risk, not no additives. */
function unratedNote(product: Product): string | null {
  const additives = product.score.components.additives;
  const count = product.additives?.length ?? 0;
  if (!additives.known || additives.value !== 1 || count === 0) return null;
  return count === 1
    ? "Its 1 additive has no EFSA risk rating."
    : `None of its ${count} additives has an EFSA risk rating.`;
}

function ComponentBars({ product }: { product: Product }) {
  const bars = componentBars(product.score);
  return (
    <section aria-labelledby="components-heading" className="card flex flex-col gap-4 p-5">
      <h2 id="components-heading" className="text-base font-semibold">
        What makes up the score
      </h2>
      <ul className="flex flex-col gap-3">
        {bars.map((bar) => (
          <li key={bar.component}>
            <div className="flex justify-between text-sm">
              <span className="font-medium">{bar.label}</span>
              <span>{bar.known ? `${bar.points} of ${bar.weight}` : "No data"}</span>
            </div>
            <div
              className="mt-1.5 h-2 overflow-hidden rounded-full bg-zinc-100"
              role="presentation"
            >
              <div
                className="h-full rounded-full bg-emerald-600"
                style={{ width: `${Math.round(bar.fraction * 100)}%` }}
              />
            </div>
            {bar.component === "additives" && unratedNote(product) && (
              <p className="mt-1 text-sm text-zinc-600">{unratedNote(product)}</p>
            )}
          </li>
        ))}
      </ul>
      {isRescaled(product.score) && (
        <p className="text-sm text-zinc-600">
          Some data is missing, so the total is worked out from the parts we have.
        </p>
      )}
    </section>
  );
}

export function ProductView({
  product,
  breakdown,
  alternatives,
  recalls,
}: {
  product: Product;
  breakdown: Breakdown;
  alternatives?: Alternatives | null;
  recalls?: Recalls | null;
}) {
  const { score } = product;
  const badge = dataBadge(score.confidence);
  const groups = groupBreakdown(breakdown.score, product.additives);
  const missing = missingWords(score.missing_inputs);

  return (
    <article className="flex flex-col gap-6">
      <nav aria-label="Breadcrumb" className="text-sm text-zinc-600">
        <Link href="/explore" className="hover:text-zinc-900">
          Explore
        </Link>
        <span aria-hidden="true"> / </span>
        <span className="text-zinc-900">{product.name ?? "Product"}</span>
      </nav>

      {product.stale && (
        <p role="status" className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">
          Showing saved data. We couldn&apos;t refresh it from Open Food Facts just now.
        </p>
      )}

      {Object.values(product.source_by_field ?? {}).includes("contribution") && (
        <p className="rounded-xl bg-sky-50 p-3 text-sm text-sky-900">
          Added by a user from a label photo. Not yet checked.
        </p>
      )}

      <RecallBanner data={recalls} />

      <div className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="flex min-w-0 flex-col gap-6">
          <section className="card flex flex-col gap-6 p-6">
            <header className="flex gap-5">
              {product.image_url && (
                // Product photos come from Open Food Facts; next/image would need a remote allowlist.
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={product.image_url}
                  alt=""
                  className="h-28 w-28 shrink-0 rounded-xl bg-zinc-50 object-contain p-2 ring-1 ring-zinc-200"
                />
              )}
              <div className="min-w-0">
                {product.brand && <p className="text-sm font-medium text-emerald-700">{product.brand}</p>}
                <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{product.name ?? "Unnamed product"}</h1>
                <p className="mt-1 text-sm text-zinc-600">Barcode {product.gtin}</p>
              </div>
            </header>

            <div className="flex flex-col gap-4 border-t border-zinc-100 pt-6">
              <ScoreHeader product={product} />
              <div className="flex flex-wrap gap-2 text-sm">
                <span className={`rounded-full px-3 py-1 font-medium ${BADGE_STYLES[badge.level]}`}>
                  {badge.label}
                </span>
                {score.nutriscore.grade && (
                  <span className="rounded-full bg-zinc-100 px-3 py-1">
                    Nutri-Score {score.nutriscore.grade.toUpperCase()}, scored as{" "}
                    {classLabel(score.nutriscore.class)}
                  </span>
                )}
                {product.nova_group && (
                  <span className="rounded-full bg-zinc-100 px-3 py-1">NOVA {product.nova_group}</span>
                )}
                {product.is_organic && <span className="rounded-full bg-zinc-100 px-3 py-1">Organic</span>}
              </div>
              {missing.length > 0 && <p className="text-sm text-zinc-600">Missing: {missing.join(", ")}.</p>}
            </div>
          </section>

          <section aria-labelledby="summary-heading" className="card p-6">
            <h2 id="summary-heading" className="text-base font-semibold">
              In short
            </h2>
            <ul className="mt-3 flex flex-col gap-2">
              {breakdown.explanation.map((sentence) => (
                <li key={sentence} className="flex gap-3 text-zinc-800">
                  <span aria-hidden="true" className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-600" />
                  {sentence}
                </li>
              ))}
            </ul>
          </section>

          <AlternativesStrip data={alternatives} />

          <section aria-labelledby="breakdown-heading" className="card flex flex-col gap-5 p-6">
            <h2 id="breakdown-heading" className="text-base font-semibold">
              Every rule applied
            </h2>
            {groups.map((group) => (
              <div key={group.component}>
                <h3 className="text-sm font-semibold tracking-wide text-zinc-500 uppercase">{group.label}</h3>
                {group.lines.length === 0 ? (
                  <p className="mt-1 text-sm text-zinc-600">{group.emptyText}</p>
                ) : (
                  <ul className="mt-2 divide-y divide-zinc-100">
                    {group.lines.map((line) => (
                      <li key={line.key} className="flex items-start justify-between gap-3 py-3 text-sm">
                        <div>
                          <p className="font-medium">
                            {line.label}
                            {line.estimated && (
                              <span className="ml-2 rounded bg-zinc-100 px-1.5 py-0.5 text-xs">Estimated</span>
                            )}
                          </p>
                          <p className="text-zinc-700">{line.value}</p>
                          {line.note && <p className="text-zinc-600">{line.note}</p>}
                          {line.usStatus && (
                            <p className="text-zinc-700">
                              {line.usStatus.text}
                              {line.usStatus.cfrUrl && (
                                <>
                                  {" "}
                                  (
                                  <a className="underline" href={line.usStatus.cfrUrl}>
                                    {line.usStatus.cfr}
                                  </a>
                                  )
                                </>
                              )}
                            </p>
                          )}
                        </div>
                        <div className="shrink-0 text-right">
                          <p className="font-semibold tabular-nums">
                            {line.points}
                            <span className="sr-only"> {line.pointsHint}</span>
                          </p>
                          <a
                            className="text-xs text-emerald-700 underline"
                            href={line.sourceUrl}
                            aria-label={`Source for ${line.label}`}
                          >
                            Source
                          </a>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </section>

          {product.ingredients_text && (
            <section aria-labelledby="ingredients-heading" className="card p-6">
              <h2 id="ingredients-heading" className="text-base font-semibold">
                Ingredients
              </h2>
              <p className="mt-2 text-sm leading-relaxed text-zinc-700">{product.ingredients_text}</p>
            </section>
          )}
        </div>

        <aside className="flex flex-col gap-6">
          <ComponentBars product={product} />
          <div className="card p-5">
            <VoicePanel data={{ product, breakdown, alternatives }} />
          </div>
          <ProductAccount gtin={product.gtin} label={product} />
          <div className="flex flex-col gap-2">
            <Link href="/scan" className="btn-primary">
              Scan another product
            </Link>
            <Link href="/assistant" className="btn-secondary">
              Ask the assistant about it
            </Link>
          </div>
        </aside>
      </div>
    </article>
  );
}

export function ProductMessage({
  title,
  body,
  action,
}: {
  title: string;
  body: string;
  action?: { href: string; label: string };
}) {
  return (
    <div className="card mx-auto flex max-w-xl flex-col items-start gap-4 p-8">
      <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
      <p className="text-zinc-700">{body}</p>
      <div className="flex flex-wrap gap-3">
        {action && (
          <Link href={action.href} className="btn-primary">
            {action.label}
          </Link>
        )}
        <Link href="/lookup" className="btn-secondary">
          Scan or type another barcode
        </Link>
      </div>
    </div>
  );
}
