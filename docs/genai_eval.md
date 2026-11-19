# GenAI check: 5 sellers

`explain_seller(seller_id, 2018-01-01, 2018-08-31)` on five sellers whose rating changed the most in 2018 and who
have at least 10 written 1–2 star reviews. The answers were checked by reading the metrics and every review
text (Portuguese) and counting the complaint themes by hand.

Model: `qwen2.5:7b` via local Ollama (RTX 3050 4 GB, temperature 0.1, max 400 tokens). Prompt:
[`genai/prompts/seller_insight.txt`](../genai/prompts/seller_insight.txt).

| Seller | Rating first → last month | Numbers traceable | Themes match the reviews | Useful (1–5) | Notes |
| --- | --- | --- | --- | --- | --- |
| `6973a06f…` (computers_accessories) | 3.63 → 1.0 | yes | partly | 3 | Non-delivery found; misses "only one of two cartridges arrived" (~5 reviews); counts too low (4 vs ~10). Correctly reads the null July late_pct as "nothing delivered". |
| `8444e55c…` (cool_stuff) | 2.0 → 1.0 | **no** | yes | 3 | Wrong/fake product and non-delivery are the right themes, but cites "avg_rating = 1.0 in January" (1.0 is July). |
| `6fd52c52…` (bed_bath_table) | 2.6 → 4.17 | yes | partly | 3 | Poor quality / not as pictured is right (~9 reviews, says 12); non-delivery under-counted (says 1, ~4). Does not link the recovery to late_pct falling from 40–75% to 0. |
| `213b25e6…` (home_construction) | 3.0 → 3.6 | yes | partly | 3 | Delivery and damaged products found; the biggest theme, incomplete multi-item orders (~10), is folded into "delivery issues". |
| `7ad32824…` (bed_bath_table) | 2.0 → 4.0 | yes | yes | 3 | Themes and counts close (non-delivery 12, missing pieces 5, wrong size 3+2); says late_pct is "decreasing" from 0.0 to 3.7 (it rose). |

**Result:** 4 of 5 answers have fully traceable numbers. In all five the headline numbers (first/last month rating and
late %) are correct, and the main complaint themes are found, but theme counts are approximate.

## What the guardrail does and does not catch

- Every number in the answer must equal a metric value (or its rounding), a part of a month/period date, 1–5,
  or a count no larger than the number of reviews. Otherwise the metrics are shown with a warning instead.
  In testing it rejected `qwen2.5:3b` answers that invented "100%" and an unexplained "31" (the latter was a
  period date, now allowed).
- It cannot catch a real number attached to the wrong month or a wrong direction word ("decreasing"), as in
  rows 2 and 5. The app therefore always shows the metrics table next to the answer.

## Prompt and model choices (measured on the same 5 sellers)

| Change | Effect |
| --- | --- |
| Plan's prompt, metrics as one JSON list, `qwen2.5:3b` | rambling month-by-month text, 3 of 5 cut off at 400 tokens, category numbers presented as the seller's |
| Question stated, fixed output format, ≤150 words | short answers, 0 cut off |
| Seller monthly vs. one category average for the period; first/last month repeated | first/last month numbers attributed correctly in 5 of 5 |
| Note that negative delay = early, null = nothing delivered | no more "more negative delay = worse service" |
| `qwen2.5:3b` → `qwen2.5:7b` | 3b adds false readings ("40% = 4 of 5 late") and invented a number; 7b follows the format and is more accurate. 7b takes 20–40 s per answer (does not fit fully in 4 GB VRAM) vs. ~5 s |

## Next improvements

- Count themes deterministically: classify each review into a fixed theme list (one short structured call per
  review, or keyword rules) and give the model the counts instead of asking it to count.
- With a larger hosted model (`LLM_PROVIDER=bedrock` once the account has Bedrock quota) the same prompt and
  guardrail apply unchanged.
