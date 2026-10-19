// Browser port of api/app/services/gtin.py (spec 001). The server stays authoritative;
// this exists so the scanner can drop misreads without a network round trip (SCAN-4).

export class InvalidGTIN extends Error {}

export function checkDigitOk(digits: string): boolean {
  const body = digits.slice(0, -1);
  const check = Number(digits.at(-1));
  let total = 0;
  [...body].reverse().forEach((d, i) => {
    total += Number(d) * (i % 2 === 0 ? 3 : 1);
  });
  return (10 - (total % 10)) % 10 === check;
}

export function normalize(raw: string): string {
  const digits = raw.replace(/[\s-]+/g, "");
  if (!/^\d+$/.test(digits)) {
    throw new InvalidGTIN("A barcode may only contain digits.");
  }
  if (![8, 12, 13, 14].includes(digits.length)) {
    throw new InvalidGTIN(`A barcode has 8, 12, 13 or 14 digits, not ${digits.length}.`);
  }
  if (digits.length === 14 && digits[0] !== "0") {
    throw new InvalidGTIN("This is a case or pallet code, not a product barcode.");
  }
  if (!checkDigitOk(digits)) {
    throw new InvalidGTIN("The check digit doesn't match. Check the number and try again.");
  }
  return digits.slice(-13).padStart(13, "0");
}

export function tryNormalize(raw: string): string | null {
  try {
    return normalize(raw);
  } catch {
    return null;
  }
}

/** Accept a code only after the same valid code is read twice in a row (SCAN-5). */
export function createReadFilter(): (raw: string) => string | null {
  let last: string | null = null;
  return (raw) => {
    const gtin = tryNormalize(raw);
    if (gtin === null) return null; // misread: ignore, keep the previous candidate
    if (gtin === last) return gtin;
    last = gtin;
    return null;
  };
}
