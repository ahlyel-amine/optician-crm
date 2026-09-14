# UI-SPEC Review — Phase 3 (Comptes, Permissions & App Shell)

**Reviewed:** 2026-09-14
**Spec:** `03-UI-SPEC.md` (1091 lines, 14 sections)
**Reviewer:** gsd-ui-checker

## Dimension Verdicts

| Dimension | Verdict | Notes |
|---|---|---|
| 1 — Copywriting | PASS | Every CTA is verb+noun (`Se connecter`, `Créer un compte gérant`). Empty/error states have real, specific copy with a next step, never "no data found." Both destructive actions (deactivate account, remove magasin access) have full confirmation copy stating what survives. `Annuler`/`Retour`/`Fermer` disambiguation (§7.10) closes a real French UX trap. Two utility buttons (`Générer`, `Copier`) are single-word without a noun — low severity, object is visually adjacent and unambiguous. |
| 2 — Visuals | PASS | No screen lacks a declared anchor: login has one card/one primary button, the permission checklist is explicitly named "the core of the screen" (§7.4) with row anatomy specified pixel-by-pixel. Icon-only controls (password show/hide, nav icons) all carry an explicit label fallback (`aria-pressed` + text label; `aria-hidden` icon + tooltip + `aria-label` in the collapsed rail). |
| 3 — Color | PASS | Accent `#2563EB` reserved to five named uses, with an explicit "not used for" list — the opposite of "all interactive elements." One accent, one destructive, no third semantic hue (with a stated, sound rationale tied to Phase 9 branding). 60/30/10 split is labelled in the table header. Contrast table verified against real value pairs. |
| 4 — Typography | PASS | Exactly 4 sizes (24/18/14/12), exactly 2 weights (400/600) — at, not over, the ceiling. Line height declared for every role including body (1.50). Sizes are a clear hierarchical scale, not clustered. |
| 5 — Spacing | FLAG | All values are multiples of 4 (no grid-breaking value exists). One token, `sm+` = 12px, falls outside the generic reference set `{4,8,16,24,32,48,64}`. It is deliberately justified (finer increment for a dense counter tool: table cell horizontal padding, switch-row gaps, nav inset) and the doc closes the scale with "no other exception — a value not in this table is a review failure," so it cannot silently grow. Non-blocking: it doesn't break alignment, it's documented, and it's the kind of considered exception the spacing dimension exists to catch when *undocumented*, not when reasoned through. |
| 6 — Registry Safety | PASS | No third-party registry listed; shadcn official blocks only, itemised. `ui_safety_gate: true` in config confirms the dimension is active and it clears cleanly — Safety Gate column correctly says "not required" rather than faking evidence. |

## Deep-Dive Findings (the checks that matter more than the six generic dimensions here)

### 1. The permission screen (§7) — concrete, not aspirational
Every state a plan would need is specified with exact copy and exact mechanics: uniform vs. mixed vs. personalised row states, the tri-state switch (`aria-checked="mixed"`), what "Par magasin" produces, what `Uniformiser` asks before collapsing a disagreeing row, what happens when a magasin is later added to an account with personalised rows (uniform rows extend, personalised ones don't and get an inline note), and what a single-magasin business sees (a static line, no control at all). Default state (`every switch off`, fail-closed) and per-toggle immediate save (no batch Save button) are both stated and reasoned. This is buildable without further design decisions. No finding here — this is the spec's strongest section.

### 2. "Absent, not greyed out" — mechanical where it matters most, one soft spot
For the field-level case this contract exists to solve (a gérant not seeing `prix_achat`), the mechanism is genuinely structural, not developer discipline: the server's `get_fields()` projection means the key is **not present in the JSON payload at all**, and the client's column/field registry (§8.3) filters to `champ in ligne` — a header can only exist if the key exists. A named vitest test (`la colonne absente du payload ne produit aucun en-tête`) mirrors the server's parametrized conformance test. This is testable and would fail loudly if a future developer hardcoded a `<th>`.

**Soft spot:** §7.7's "those rows are absent, not disabled" — for a gérant-manager editing a colleague's permissions — is stated as a rule but not traced to a concrete data mechanism the way §8.3 is. It's plausible the same principle applies (the server-scoped catalogue delivered to that viewer is already intersected before the SPA ever iterates it, the same pattern as nav filtering in §5.3), but the spec doesn't say so explicitly, and this is the one place in the document where "absent" is asserted without a stated wire-level guarantee. Recommend the planner make explicit that `/api/comptes/catalogue/` (or equivalent) returns an already-intersected list for a non-owner editor, not a full list filtered client-side — otherwise this is the one row in the whole document at risk of becoming convention rather than mechanism.

### 3. Navigation holds nine more phases
The 8-entry + 1-reserved nav (§5.3) accounts for every downstream phase: Clients(4), Stock(5), Ventes(6), Caisse(7), Achats(8), Rappels(10), Tableau de bord(10), and Paramètres nesting both Personnalisation(9) and Abonnement(12). Phase 11 (mobile) is correctly out of this nav entirely (separate Expo app). Second-level nav is explicitly *not* a sidebar accordion, avoiding the standard failure mode of an 8-entry sidebar growing a tree. No redesign is implied by any phase 4–12 requirement read against this table.

### 4. French lexicon as a contract
~29 terms across §9.3, each mapped to real domain vocabulary already used in `03-RESEARCH.md`'s own model names (`gérant`, `droits`, `magasin`, `compte`, `caisse`, `encaissé`) rather than invented for the UI. Specified per screen in §9.4. Two developers implementing from this table would produce the same labels — the bar this dimension exists to check.

### 5. Keyboard and accessibility
§5.7 and §10 are both specified as build requirements, not aspirations: focus order, focus restoration on every overlay and route change, landmark structure, `aria-live` scoping (polite vs assertive), 44px hit targets via pseudo-element (not padding), 200% zoom, `prefers-reduced-motion`. This is a genuinely daily-use counter tool and it reads like one was designed.

### 6. The six upstream contradictions (§0)
All six hold up:
- **0.1 (grant model)** correctly enforces CLAUDE.md #13 against the research's flatter model, and correctly declares this a planner-facing reconciliation rather than quietly picking a shape.
- **0.2 (`vente.voir`)** is a real, cheap fix to a real gap (an unrepresentable "may consult but not create" gérant).
- **0.3 (branding on `/connexion`)** correctly identifies that BRAND-01 cannot apply pre-authentication and sets the boundary at first authenticated paint — consistent with CLAUDE.md #11's "one shared login address."
- **0.4 (email identifier)** is right, and is already consistent with `03-RESEARCH.md`'s own `Utilisateur` model (`USERNAME_FIELD = "email"`) — the UI-SPEC's "correction" formalizes a decision the backend design had already made, not a real conflict. Correctly filed as an open question for developer confirmation rather than silently assumed.
- **0.5 (shadcn now, not Phase 4)** is well-argued on concrete component need (focus-trapped dialog, combobox, command palette) plus the CSS-variable theming hook Phase 9 needs. Reversing this later would mean restyling the shell.
- **0.6 (absent-field mechanism)** — see finding #2 above; sound in general, one traced gap.

## Blocking Issues

None.

## Recommendations (non-blocking)

- **Dimension 5:** No action required; the 12px token is justified and grid-safe. Consider a one-line note in §2 acknowledging it's a deliberate extension of the reference scale, purely so a future reviewer doesn't have to re-derive the reasoning.
- **§7.7:** Make explicit that the permission catalogue served to a non-owner `compte.gerer` editor is pre-intersected server-side (same shape as nav filtering, §5.3), so "absent, not disabled" for that row has the same wire-level guarantee as the rest of the document.
- **§7.2 / §7.3A:** `Générer` and `Copier` are single-word CTAs; harmless given adjacency to the password field, but if the planner wants zero ambiguity, `Générer un mot de passe` / `Copier le mot de passe` cost nothing.

## Status: APPROVED

All six dimensions clear (five PASS, one non-blocking FLAG). The deep-dive checks — the permission screen, the absent-field mechanism, the nine-phase nav, the French lexicon, keyboard/accessibility, and the six upstream contradictions — all hold up under scrutiny. This is an unusually rigorous, build-ready contract; the one soft spot (§7.7) is a completeness note for the planner, not a defect that blocks planning.

