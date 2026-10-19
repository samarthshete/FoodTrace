# 023: Voice assistant tab

Status: implemented

A separate "Assistant" page where someone taps a big microphone and asks about any product in
their own words, e.g. "Hey, I'm diabetic. Can I eat Pringles?" It finds the product, checks the
nutrients that matter for the person's condition, and answers on screen and out loud.

**An LLM understands the question; it never writes the answer.** When a Groq key is set, a
server route asks a small open-weight model to turn the question into fixed fields (product
words, conditions, nutrients, topics). The product comes from our search, and answers are
templates over its label data, so every number is traceable and the wording rules hold.
Without a key, or when Groq fails, the keyword rules below do the same job.

## Understanding the question (`parseQuestion`)

- **ASSIST-1** Conditions are recognised by keywords: diabetes ("diabetes", "diabetic", "blood
  sugar"), blood pressure ("blood pressure", "hypertension", "sodium"), heart ("heart",
  "cholesterol"), weight ("weight", "calories", "diet"), gluten ("gluten", "celiac",
  "coeliac"), teeth ("teeth", "tooth", "dental", "cavities"), dairy ("lactose", "dairy", "milk allergy"), nuts ("nut allergy", "peanut
  allergy", "nuts", "peanuts"), vegan and vegetarian. A question can name several.
- **ASSIST-2** The product is whatever is left after removing filler, condition and question
  words ("hey assistant", "I'm a", "can I eat", "tell me about", …). With no product words,
  the last product asked about is reused ("what about its salt?"). With neither, the
  assistant asks which product.
- **ASSIST-3** Topics without a condition are recognised too: score, additives, sugar, salt,
  fat, allergens, alternatives. A question with neither gets a short overview (score, band and
  the main reasons).

## Answering (`answerQuestion`)

- **ASSIST-4** The product is the top result of `/api/search` for the product words. Its data
  comes from `GET /products/{gtin}` through a web proxy. It's named in the answer as "{brand}
  {name}" so the user can tell if it picked the wrong one.
- **ASSIST-5** For each condition, the answer gives the relevant nutrients per 100 g (or 100 ml
  for drinks), rated **low / medium / high** with the UK Food Standards Agency front-of-pack
  thresholds:
  - foods: sugars low ≤ 5 g, high > 22.5 g; fat low ≤ 3 g, high > 17.5 g; saturated fat low ≤
    1.5 g, high > 5 g; salt low ≤ 0.3 g, high > 1.5 g;
  - drinks: sugars low ≤ 2.5 g, high > 11.25 g; fat low ≤ 1.5 g, high > 8.75 g; saturated fat
    low ≤ 0.75 g, high > 2.5 g; salt low ≤ 0.3 g, high > 0.75 g.

  Diabetes → sugars (and fibre if listed); teeth → sugars; blood pressure → salt; heart → saturated fat and
  fat; weight → energy in kcal, sugars and fat. A missing nutrient is said to be missing.
- **ASSIST-6** Allergy and diet conditions use the label's allergens, traces and vegan or
  vegetarian status (as in spec 018). Without label data, the answer says so and to check the
  label.
- **ASSIST-7** Every answer adds the score and band, and ends with "This is general label
  information, not medical advice. Your doctor or dietitian can tell you what fits your plan."
  It never says a product is "safe", or that someone "can" or "can't" eat it, and never uses
  "toxic", "dangerous" or "unsafe" (hard rule 4).
- **ASSIST-8** Product not found → "I couldn't find {words}. Try the brand and product name,
  or scan its barcode." Search or network failure → "I can't look that up right now."

## The page

- **ASSIST-9** `/assistant` has a large round microphone button that pulses while listening, a
  chat-style transcript (question, answer, and a link to the product page), and a text box
  that always works. It's linked from the header and the home page.
- **ASSIST-10** Speech: recognition starts only on a tap, after the one-time notice from spec 022
  (VOICE-7). Answers are spoken with `speechSynthesis` when available, with a Stop button.
  Without speech support, the page works by typing.
- **ASSIST-11** The page has no axe-detected WCAG 2.1 AA violations. The transcript is a polite
  live region, and the mic button's state is announced (`aria-pressed`, label).

- **ASSIST-17** Allergen tags are sometimes missing from the data, so allergy answers also read
  the ingredient text: peanuts and tree nuts (almond, cashew, hazelnut, walnut, pecan, pistachio,
  macadamia), gluten (wheat, barley, rye, spelt) and milk (milk, lactose, whey, casein; not
  coconut, almond, oat, soy or rice milk). A match says "The ingredients mention {word}." and is
  never reported as "doesn't list". Nutrient values under 10 g show two decimals, so a value just
  over a threshold never reads as equal to it.

## Understanding with an LLM (Groq free tier)

- **ASSIST-12** `POST /api/assistant/understand` (Next route, server-side) sends only the
  question text (at most 300 characters; longer → 400) to Groq's OpenAI-compatible API with
  `GROQ_API_KEY` and `GROQ_MODEL` (default `openai/gpt-oss-20b`), temperature 0, JSON output,
  6-second timeout. No user ID, history or product data is sent. No key → 404; Groq error,
  timeout or unusable output → 503. At most 20 questions a minute per client address (→ 429).
- **ASSIST-13** The model's output is never trusted: conditions, topics and nutrients are kept
  only if they're in the fixed lists, the product words are trimmed to 80 characters, and a
  concern label is kept only as 1–40 letters, spaces or hyphens and without the hard-rule-4 words.
  Anything else is dropped.
- **ASSIST-14** A health concern outside the fixed conditions (e.g. "dental issues",
  "pregnancy") is answered as "For {label}:" with the nutrients the model linked to it (sugars,
  fat, saturated fat, salt, fibre, energy), or "I don't have specific label guidance for
  {label}." when it linked none.
- **ASSIST-15** The page uses the route first and falls back to `parseQuestion` on any failure,
  so the assistant works without a key, offline from Groq, or rate-limited. A line under the text
  box says questions are sent to Groq to understand them, and answers come from label data.
- **ASSIST-16** When the model marks the product as a broad type ("chocolate", "chips"), the
  assistant asks "Which {words} do you mean? For example: A, B or C." using the top three search
  results, instead of picking one. With fewer than two results it answers as usual.

- **ASSIST-21** Speed and robustness: the keyword parser's product words are searched while the
  model is still answering, and that search is reused when the model names the same product
  (ignoring case). When the model names no product and there's no earlier product to follow up
  on, the keyword parser's product words are used. A request for a recommendation ("which
  chocolate should I eat?") still names the food, as a broad type (ASSIST-16).

## Speech to text with Whisper (Groq free tier)

- **ASSIST-18** `POST /api/assistant/transcribe` (Next route, server-side) takes one recorded
  clip as `multipart/form-data` field `audio` (at most 4 MB, else 413) and sends only that clip
  to Groq's `audio/transcriptions` with `GROQ_API_KEY`, model `GROQ_STT_MODEL` (default
  `whisper-large-v3-turbo`), English, temperature 0, and a short prompt of grocery brand names.
  It returns `{text}`. No key → 404; Groq error, timeout (15 s) or empty text → 503; at most 20
  clips a minute per client address (→ 429). `GET` returns `{enabled}` (whether a key is set).
- **ASSIST-19** On the assistant page, when the route is enabled and the browser can record
  (`MediaRecorder` and `getUserMedia`), the mic records instead of using `SpeechRecognition`:
  tap to start, tap again to stop, and it stops on its own after 12 seconds. The clip is
  transcribed and asked like a typed question. The one-time notice (VOICE-7) says the recording
  is sent to Groq. Audio is never stored.
- **ASSIST-20** Every failure falls back: no key, no `MediaRecorder` or a refused microphone →
  the browser's `SpeechRecognition` path (ASSIST-10) or typing; a failed transcription → "I
  couldn't make that out. Try again, or type your question." The product page's voice panel
  (spec 022) is unchanged.

## Later (production, not built here)

An LLM using tools over the same API (search, product, alternatives) to handle multi-turn
conversations, still writing answers only from the returned data. On-device speech recognition (e.g.
Whisper in the browser) to avoid sending audio to Google. Groq's free tier was chosen for the
demo (no card, rate-limited); production needs a privacy review, since questions can be
health-related.
