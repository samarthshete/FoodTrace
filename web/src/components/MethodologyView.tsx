import type { Methodology } from "@/lib/api";

// How the score works, with every number from GET /methodology (spec 019, METH-3..5).
export function MethodologyView({ m }: { m: Methodology | null }) {
  if (!m) {
    return (
      <p role="status">
        The scoring details aren&apos;t available right now, so we won&apos;t show possibly outdated
        numbers. Try again in a moment.
      </p>
    );
  }
  const w = m.weights;
  const bands = [...m.bands].sort((a, b) => b.min - a.min);
  const pct = (v: number) => `${Math.round(v * 100)}%`;
  return (
    <div className="flex flex-col gap-6 text-sm leading-6">
      <p>
        Every product gets a score from 0 to 100, built from three parts. The total is{" "}
        <strong>
          {w.nutrition}·N + {w.additives}·A + {w.processing}·P
        </strong>
        , where each part is between 0 and 1. Scoring version {m.engine_version}.
      </p>
      <table className="w-full text-left">
        <caption className="sr-only">Score bands</caption>
        <thead>
          <tr><th scope="col">Score</th><th scope="col">Band</th></tr>
        </thead>
        <tbody>
          {bands.map((b, i) => (
            <tr key={b.id}>
              <td>{i === 0 ? `${b.min}–100` : `${b.min}–${bands[i - 1].min - 1}`}</td>
              <td>{b.label}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <section id="nutrition" aria-labelledby="nutrition-heading">
        <h2 id="nutrition-heading" className="text-lg font-semibold">Nutrition ({w.nutrition} points)</h2>
        <p>
          We compute the 2023 Nutri-Score. Energy, sugars, saturated fat and salt count against a
          product; fibre, protein and fruit, vegetables and legumes count for it. Drinks, cheeses, and
          fats, oils, nuts and seeds have their own rules. The Nutri-Score result is scaled to 0–1 within
          its class. Sources:{" "}
          <a className="underline" href={m.sources.nutriscore_foods}>foods</a>,{" "}
          <a className="underline" href={m.sources.nutriscore_beverages}>drinks</a>.
        </p>
        <p>
          We check our grades against Open Food Facts&apos; own: on 41,750 US products they match 99.27%
          of the time, and every change must keep that above 99%.
        </p>
      </section>

      <section id="additives" aria-labelledby="additives-heading">
        <h2 id="additives-heading" className="text-lg font-semibold">Additives ({w.additives} points)</h2>
        <p>
          Each additive with an EFSA overexposure rating takes points off, depending on the rating
          (none {pct(m.additives.risk_penalty["0"])}, low {pct(m.additives.risk_penalty["1"])},
          moderate {pct(m.additives.risk_penalty["2"])}, high {pct(m.additives.risk_penalty["3"])} of
          this part) and how strong the evidence is (×{m.additives.evidence_weight.A} for full
          evaluations, ×{m.additives.evidence_weight.B} and ×{m.additives.evidence_weight.C} for weaker
          evidence). An additive with a high rating caps the whole score at {m.additives.cap_total}.{" "}
          <a className="underline" href={m.sources.efsa}>EFSA re-evaluations</a>.
        </p>
      </section>

      <section id="processing" aria-labelledby="processing-heading">
        <h2 id="processing-heading" className="text-lg font-semibold">Processing ({w.processing} points)</h2>
        <p>
          The NOVA group: unprocessed {pct(m.nova_values["1"])}, culinary ingredients{" "}
          {pct(m.nova_values["2"])}, processed {pct(m.nova_values["3"])}, ultra-processed{" "}
          {pct(m.nova_values["4"])} of this part.{" "}
          <a className="underline" href={m.sources.nova}>About NOVA</a>.
        </p>
      </section>

      <section aria-labelledby="missing-heading">
        <h2 id="missing-heading" className="text-lg font-semibold">Missing data</h2>
        <p>
          We never guess a nutrient. If a part is unknown, the total is worked out from the parts we
          have, and the data badge says so. Without energy, sugars, saturated fat and salt, a product is
          &ldquo;not scored&rdquo;. When the label data lacks the fruit and vegetable share or the
          processing level, we estimate it from the ingredient list, using only what the label states,
          and mark it &ldquo;Estimated&rdquo;. Estimates never raise the data badge.
        </p>
      </section>

      <section aria-labelledby="changelog-heading">
        <h2 id="changelog-heading" className="text-lg font-semibold">Changes to the scoring</h2>
        <ul className="mt-2 flex flex-col gap-2">
          {[...m.changelog].reverse().map((e) => (
            <li key={e.version}>
              <strong>{e.version}</strong>: {e.change.replaceAll("`", "")}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
