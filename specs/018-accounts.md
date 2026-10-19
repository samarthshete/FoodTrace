# 018: Accounts

Status: implemented

Optional sign-in with Google, so people can keep a scan history, save favorites, and get
warnings for their allergens and diets. **Everything else keeps working signed out.** Scan
history is health-adjacent data (hard rule 6): we collect the minimum, every user can delete
everything in one action, and Postgres row-level security keeps each user's rows private even
if the API has a bug.

## Sign-in

- **ACC-1** Sign-in uses Better Auth in the web app, with Google or an email and password
  (ACC-19). The session lives in an httpOnly, Secure, SameSite=Lax cookie. A password is never
  stored in plain text: Better Auth keeps only a salted scrypt hash.
- **ACC-2** We keep only what Better Auth needs: an internal user id, the Google account's
  email, name and avatar URL, and the session. No Google tokens are stored after sign-in.
- **ACC-3** The web app gets a short-lived (15-minute) signed JWT for the user from Better
  Auth and sends it to the API as `Authorization: Bearer`. The API verifies it against
  Better Auth's JWKS (`/api/auth/jwks`), checking the signature, `exp`, `iss` and `aud`. A
  missing or invalid token on a `/me` route → `401` problem+json.
- **ACC-4** The header shows "Sign in" when signed out, and the avatar plus an account menu
  when signed in. Signing out ends the session server-side.

## Profile and preferences

- **ACC-5** `GET /me` returns the user's name, email, avatar and preferences.
  `PUT /me/preferences` sets:
  - `allergens`: any of the US major nine (milk, eggs, fish, crustacean shellfish, tree
    nuts, peanuts, wheat, soybeans, sesame);
  - `diets`: any of vegan, vegetarian, gluten-free;
  - `save_history`: whether scans are saved. **On by default**, with a "Pause history"
    switch on the account page.

  Unknown values → `422`.

## Allergen and diet warnings

- **ACC-6** Products store the allergens (`allergens`), possible traces (`traces`) and
  ingredient analysis (`ingredients_analysis`: vegan / vegetarian status) that Open Food
  Facts provides, live and in the bulk import. USDA and contributed products have none, so
  their status is unknown. Re-importing fills existing rows.
- **ACC-7** For a signed-in user, the product page shows a warning above the score when the
  product contains one of their allergens. It shows "may contain" for traces, and a diet
  note when the product isn't vegan, vegetarian or gluten-free as they asked. Unknown data
  says "Allergen information isn't available for this product. Check the label." It never
  says a product is "safe" for them.
- **ACC-8** The warnings come only from the label data, and the page links to the
  ingredients. The footer's "not medical advice" line still applies.

## Scan history

- **ACC-9** When a signed-in user with `save_history` on opens a product page, one history
  row is saved: user, GTIN, time, and the score and band at that moment. Repeat views of the
  same product within 10 minutes don't add rows.
- **ACC-10** `GET /me/history?cursor=` returns the user's scans, newest first, 50 per page,
  with each product's name, brand, image and the score saved then. The account page lists
  them grouped by day.
- **ACC-17** History keeps the newest 1,000 scans per user; older rows are deleted as new
  ones arrive. Nothing else expires it.
- **ACC-11** `DELETE /me/history/{id}` removes one scan. `DELETE /me/history` removes all
  of them in one call (hard rule 6).

## Favorites

- **ACC-12** `PUT /me/favorites/{gtin}` saves a product (idempotent).
  `DELETE /me/favorites/{gtin}` removes it. `GET /me/favorites` lists them with their
  current score. The product page has a "Save" toggle when signed in.

## Deleting the account

- **ACC-13** `DELETE /me` deletes the user, their sessions, preferences, history and
  favorites in one transaction. Their contributions stay but lose the link to them
  (`user_id = null`).
- **ACC-18** A contribution made while signed in is linked to the user (`contributions.user_id`)
  and listed on their account page. The account page asks for confirmation first.

## Privacy and isolation

- **ACC-14** `scan_history`, `favorites` and user preferences have row-level security. The
  API connects as a role without `BYPASSRLS`, and sets `app.user_id` per transaction
  (`SET LOCAL`) from the verified token. Policies allow only rows where `user_id =
  current_setting('app.user_id')`. Tests prove user A can't read, change or delete user
  B's rows, even when the API asks for them by id.
- **ACC-15** No third-party analytics or tracking scripts. The only third party involved is
  Google, during sign-in.
- **ACC-16** The privacy page (M6) lists exactly what is stored, why, and how to delete it.

## Email and password (added 2026-10-13)

- **ACC-19** `/sign-in` has two modes: "Sign in" (email, password) and "Create account" (name,
  email, password of at least 8 characters). Wrong details say "That email and password don't
  match." without saying which one was wrong. Success returns to the page in `?next=` (only a
  path on this site, else `/account`). "Continue with Google" is offered as well.
- **ACC-20** The header's "Sign in" links to `/sign-in?next={current path}`, and the account
  page's signed-out view shows the same form.

## Decisions (approved 2026-10-12)

1. History is on by default, with a "Pause history" switch (ACC-5).
2. History keeps the newest 1,000 scans until the user deletes them (ACC-17).
3. ~~Google is the only sign-in provider for now (ACC-1).~~ Email and password added for the
   demo on 2026-10-13 (ACC-19, ACC-20).
4. Contributions made while signed in are linked to the user, and unlinked on account
   deletion (ACC-13, ACC-18).
