# 022: Voice: ask about a product, hear it read aloud

Status: implemented

On a product page, the user can ask a question by voice or by typing, and hear the answer or
the whole summary read aloud. **Answers are built by fixed rules from the data already on the
page.** No AI model is involved, and nothing new is sent to our servers.

Two decisions differ from the original plan (SPEC §6, `kokoro-js`):

- **Speech output uses the browser's built-in `speechSynthesis`.** Kokoro's smallest model is
  86 MB, downloaded from Hugging Face on first use, and its phonemizer bundles eSpeak NG,
  which is GPL-3.0 (hard rule 3).
- **Speech input uses the browser's `SpeechRecognition`.** In Chrome, it sends audio to
  Google's speech service, so it starts only on a tap, after a one-time notice. Typing always
  works instead.

## Answers (pure, `answer(question, product)`)

- **VOICE-1** The question is matched by keywords to one intent, and the first match wins:
  - `allergen`: "contain", "allergen", "gluten", "milk", "nuts", "peanut", "soy", "egg",
    "sesame", "fish", "shellfish", "wheat";
  - `alternatives`: "alternative", "instead", "healthier", "better", "swap";
  - `why`: "why", "lower", "reason", "bad", "good";
  - `additives`: "additive", "e number", "preservative", "color";
  - `score`: "score", "healthy", "rating", "how good";
  - `summary`: "read", "tell me", "about", "summary".
  Anything else gets the help answer.
- **VOICE-2** Answers come only from the product page's data: the score and band, the
  explanation sentences, the additives (with EFSA wording), the alternatives, and the label's
  allergens. A product that isn't scored says so and why.
- **VOICE-3** Allergen answers name what the label lists ("The label lists milk and
  wheat."), or say "The label doesn't list X". Without allergen data, the answer is "Allergen
  information isn't available for this product. Check the label." No answer says a product is
  "safe", "toxic", "dangerous" or "unsafe" (hard rule 4).
- **VOICE-4** The help answer: "You can ask about the score, why it got that score, its
  additives, allergens, or healthier alternatives."

## On the page

- **VOICE-5** A "Read aloud" button speaks the summary (score, band and explanation), and
  becomes "Stop" while speaking. Without `speechSynthesis`, the button isn't shown.
- **VOICE-6** An "Ask about this product" box takes a typed question. The answer is shown as
  text in a polite live region, and spoken if speech is available.
- **VOICE-7** A microphone button starts recognition only when tapped. The first time, a
  notice says the browser may send audio to its speech service (Google, in Chrome), and the
  user must choose "Continue". The choice is remembered on the device. Without
  `SpeechRecognition` (e.g. Firefox), the button isn't shown and typing still works.
- **VOICE-8** Speech and recognition errors never break the page. The typed answer is always
  shown.
