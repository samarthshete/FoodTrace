import Link from "next/link";
import { Suspense } from "react";

import {
  ArrowRightIcon,
  BookIcon,
  CheckIcon,
  CompassIcon,
  LeafIcon,
  MicIcon,
  ScanIcon,
  SearchIcon,
  ShieldIcon,
} from "@/components/Icons";
import { ProductCard, ProductCardSkeleton } from "@/components/ProductCard";
import { ScoreRing } from "@/components/ProductView";
import { LookupPanel } from "@/components/ScanHome";
import { PRODUCT_TAGLINE } from "@/lib/brand";
import { loadExplore } from "@/lib/explore";

export default function Home() {
  return (
    <div className="flex flex-col">
      <Hero />
      <QuickLookup />
      <HowItWorks />
      <TopFoods />
      <AssistantBand />
      <Principles />
    </div>
  );
}

function Hero() {
  return (
    <section className="relative overflow-hidden border-b border-zinc-100">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(60rem_30rem_at_80%_-10%,rgba(16,185,129,0.10),transparent),radial-gradient(40rem_20rem_at_0%_10%,rgba(14,165,233,0.06),transparent)]"
      />
      <div className="relative mx-auto grid w-full max-w-7xl items-center gap-12 px-4 py-16 sm:px-6 md:py-24 lg:grid-cols-[1.1fr_1fr]">
        <div className="flex flex-col items-start gap-6">
          <p className="flex items-center gap-2 rounded-full bg-white px-3 py-1 text-xs font-medium text-zinc-700 shadow-sm ring-1 ring-zinc-200">
            <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-emerald-600" />
            {PRODUCT_TAGLINE}
          </p>
          <h1 className="text-4xl font-semibold tracking-tight text-zinc-900 sm:text-6xl sm:leading-[1.05]">
            Know what&apos;s really <span className="text-emerald-700">in your food.</span>
          </h1>
          <p className="max-w-xl text-lg text-zinc-600">
            Scan any grocery barcode and get a 0–100 health score. Every point traces back to a rule and a cited
            source, so you never have to take our word for it.
          </p>
          <div className="flex flex-wrap gap-3">
            <Link href="/scan" className="btn-accent">
              <ScanIcon className="h-4 w-4" />
              Start scanning
            </Link>
            <Link href="/explore" className="btn-secondary">
              Explore top foods
              <ArrowRightIcon className="h-4 w-4" />
            </Link>
          </div>
          <ul className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-zinc-600">
            {["Free, no ads", "No tracking", "Every point cited"].map((t) => (
              <li key={t} className="flex items-center gap-1.5">
                <CheckIcon className="h-4 w-4 text-emerald-700" />
                {t}
              </li>
            ))}
          </ul>
        </div>
        <HeroCard />
      </div>
    </section>
  );
}

const PREVIEW_BARS = [
  { label: "Nutrition", value: 58, of: 60 },
  { label: "Additives", value: 30, of: 30 },
  { label: "Processing", value: 9, of: 10 },
];

/** An illustration of a real result (Barilla red lentil rotini), not live data. */
function HeroCard() {
  return (
    <div aria-hidden="true" className="relative mx-auto w-full max-w-md">
      <div className="absolute -inset-4 -z-10 rotate-3 rounded-[2rem] bg-gradient-to-br from-emerald-100 to-sky-50" />
      <div className="card p-6">
        <div className="flex items-center gap-4">
          <div className="grid h-14 w-14 place-items-center rounded-xl bg-orange-50 text-2xl">🍝</div>
          <div>
            <p className="text-xs font-medium text-emerald-700">Barilla</p>
            <p className="font-semibold">Red Lentil Rotini</p>
          </div>
        </div>
        <div className="mt-6 flex items-center gap-5 border-t border-zinc-100 pt-6">
          <div className="relative">
            <ScoreRing total={97} bandId="excellent" size={96} />
            <p className="absolute inset-0 grid place-items-center text-2xl font-semibold">97</p>
          </div>
          <div className="flex flex-col gap-1.5">
            <span className="w-fit rounded-full bg-emerald-100 px-3 py-1 text-sm font-semibold text-emerald-900">
              Excellent
            </span>
            <span className="text-sm text-zinc-600">Nutri-Score A · NOVA 1</span>
          </div>
        </div>
        <ul className="mt-6 flex flex-col gap-3">
          {PREVIEW_BARS.map((b) => (
            <li key={b.label}>
              <div className="flex justify-between text-sm">
                <span className="font-medium">{b.label}</span>
                <span className="text-zinc-600">
                  {b.value} of {b.of}
                </span>
              </div>
              <div className="mt-1.5 h-2 rounded-full bg-zinc-100">
                <div className="h-full rounded-full bg-emerald-600" style={{ width: `${(b.value / b.of) * 100}%` }} />
              </div>
            </li>
          ))}
        </ul>
        <p className="mt-6 rounded-xl bg-zinc-50 p-3 text-sm text-zinc-700">
          High in fibre and protein, no additives, minimally processed.
        </p>
      </div>
    </div>
  );
}

function QuickLookup() {
  return (
    <section aria-labelledby="lookup-heading" className="mx-auto -mt-px w-full max-w-7xl px-4 py-16 sm:px-6">
      <div className="card grid gap-8 p-6 md:grid-cols-[1fr_1.4fr] md:p-10">
        <div>
          <p className="eyebrow">Quick lookup</p>
          <h2 id="lookup-heading" className="mt-2 text-2xl font-semibold tracking-tight">
            No camera? Look it up.
          </h2>
          <p className="mt-2 text-zinc-600">Search by name or brand, or type the number under the barcode.</p>
        </div>
        <LookupPanel />
      </div>
    </section>
  );
}

const STEPS = [
  {
    Icon: ScanIcon,
    title: "Scan anything",
    body: "Point your camera at a barcode. It's read in your browser, nothing is uploaded.",
    tile: "from-emerald-500 to-emerald-700",
    art: (
      <div className="flex h-16 items-end gap-1">
        {[10, 16, 8, 14, 6, 16, 12, 8, 16, 10, 14, 6].map((h, i) => (
          <span key={i} className="w-1.5 rounded-sm bg-white/90" style={{ height: `${h * 4}px` }} />
        ))}
      </div>
    ),
  },
  {
    Icon: BookIcon,
    title: "See every point",
    body: "Nutrition, additives and processing, each rule shown with its source.",
    tile: "from-zinc-50 to-white ring-1 ring-zinc-200",
    art: (
      <div className="flex w-full flex-col gap-2 px-6">
        {[["w-11/12", "bg-emerald-600"], ["w-2/3", "bg-amber-400"], ["w-5/6", "bg-sky-500"], ["w-1/2", "bg-rose-500"]].map(
          ([w, c], i) => (
            <span key={i} className={`h-2.5 rounded-full ${w} ${c}`} />
          ),
        )}
      </div>
    ),
  },
  {
    Icon: MicIcon,
    title: "Just ask",
    body: "“I'm diabetic. Can I eat Pringles?” Get an answer from the label, out loud.",
    tile: "from-sky-400 to-sky-600",
    art: (
      <div className="flex flex-col gap-2">
        <span className="self-end rounded-2xl rounded-br-md bg-white/95 px-3 py-1.5 text-xs font-medium text-zinc-800">
          Is this ok for me?
        </span>
        <span className="rounded-2xl rounded-bl-md bg-sky-900/30 px-3 py-1.5 text-xs text-white">Sugars: low, 4.8 g</span>
      </div>
    ),
  },
];

function HowItWorks() {
  return (
    <section aria-labelledby="how-heading" className="mx-auto w-full max-w-7xl px-4 py-16 sm:px-6">
      <p className="eyebrow">How it works</p>
      <h2 id="how-heading" className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">
        Three ways in. One honest score.
      </h2>
      <ol className="mt-10 grid gap-8 md:grid-cols-3">
        {STEPS.map(({ Icon, title, body, tile, art }) => (
          <li key={title} className="flex flex-col gap-4">
            <div
              aria-hidden="true"
              className={`grid aspect-[16/10] place-items-center rounded-3xl bg-gradient-to-br shadow-sm ${tile}`}
            >
              {art}
            </div>
            <h3 className="flex items-center gap-2 text-lg font-semibold">
              <Icon className="h-5 w-5 text-emerald-700" />
              {title}
            </h3>
            <p className="-mt-2 text-zinc-600">{body}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}

function TopFoods() {
  return (
    <section aria-labelledby="top-heading" className="border-y border-zinc-100 bg-zinc-50/60">
      <div className="mx-auto w-full max-w-7xl px-4 py-16 sm:px-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="eyebrow">Top foods</p>
            <h2 id="top-heading" className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">
              The best in each aisle
            </h2>
          </div>
          <Link href="/explore" className="btn-secondary">
            <CompassIcon className="h-4 w-4" />
            Explore all categories
          </Link>
        </div>
        <Suspense fallback={<TopSkeleton />}>
          <TopRows />
        </Suspense>
      </div>
    </section>
  );
}

async function TopRows() {
  const categories = await loadExplore(4);
  const shown = (categories ?? []).filter((c) => c.products.length > 0).slice(0, 3);
  if (shown.length === 0) {
    return <p className="mt-8 text-zinc-600">Top foods are unavailable right now.</p>;
  }
  return (
    <div className="mt-10 flex flex-col gap-10">
      {shown.map((c) => (
        <div key={c.id}>
          <div className="flex items-baseline justify-between gap-4">
            <h3 className="text-lg font-semibold">{c.label}</h3>
            <Link href={`/explore/${c.id}`} className="text-sm font-medium text-emerald-700 hover:text-emerald-800">
              See all<span className="sr-only"> {c.label}</span>
            </Link>
          </div>
          <ul className="mt-4 grid grid-cols-2 gap-4 md:grid-cols-4">
            {c.products.map((p, i) => (
              <li key={p.gtin} className="flex">
                <ProductCard item={p} rank={i + 1} />
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

function TopSkeleton() {
  return (
    <div role="status" aria-label="Loading top foods" className="mt-10 grid grid-cols-2 gap-4 md:grid-cols-4">
      {[0, 1, 2, 3].map((i) => (
        <ProductCardSkeleton key={i} />
      ))}
    </div>
  );
}

function AssistantBand() {
  return (
    <section className="mx-auto w-full max-w-7xl px-4 py-16 sm:px-6">
      <Link
        href="/assistant"
        className="group flex flex-col items-start gap-6 rounded-3xl bg-gradient-to-br from-emerald-700 to-emerald-900 p-8 text-white shadow-lg md:flex-row md:items-center md:justify-between md:p-12"
      >
        <span className="flex items-center gap-5">
          <span aria-hidden="true" className="grid h-16 w-16 shrink-0 place-items-center rounded-full bg-white/15 ring-8 ring-white/5">
            <MicIcon className="h-8 w-8" />
          </span>
          <span>
            <span className="block text-2xl font-semibold tracking-tight">Ask the assistant</span>
            <span className="mt-1 block text-emerald-50">
              &ldquo;I&apos;m diabetic. Can I eat Pringles?&rdquo; Ask out loud, hear the answer.
            </span>
          </span>
        </span>
        <span className="flex items-center gap-2 rounded-xl bg-white px-5 py-3 text-sm font-semibold text-emerald-900 transition group-hover:gap-3">
          Try it <ArrowRightIcon className="h-4 w-4" />
        </span>
      </Link>
    </section>
  );
}

const PRINCIPLES = [
  { Icon: BookIcon, title: "Every point cited", body: "Each rule links to the regulation, study or dataset it comes from." },
  { Icon: ShieldIcon, title: "Private by design", body: "No ads, no third-party analytics. Your history is yours to delete." },
  { Icon: LeafIcon, title: "Open data", body: "Built on Open Food Facts, USDA and FDA data, attributed everywhere." },
  { Icon: SearchIcon, title: "Honest about gaps", body: "Missing data lowers our confidence, never the score." },
];

function Principles() {
  return (
    <section aria-labelledby="principles-heading" className="mx-auto w-full max-w-7xl px-4 pb-8 sm:px-6">
      <h2 id="principles-heading" className="sr-only">
        Our principles
      </h2>
      <ul className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
        {PRINCIPLES.map(({ Icon, title, body }) => (
          <li key={title} className="card p-6">
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-emerald-50 text-emerald-700">
              <Icon className="h-5 w-5" />
            </span>
            <h3 className="mt-4 font-semibold">{title}</h3>
            <p className="mt-1 text-sm text-zinc-600">{body}</p>
          </li>
        ))}
      </ul>
      <p className="mt-8 text-center text-sm text-zinc-600">
        <Link href="/methodology" className="font-medium text-emerald-700 underline">
          Read exactly how the score works
        </Link>
      </p>
    </section>
  );
}
