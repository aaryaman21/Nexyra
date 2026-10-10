# Phase 5B.5 — Final PIB Full-Text Integration

Date: 2026-10-09 (Asia/Kolkata)

## Result

All four distinct PIB articles are available through Model B's recent-events API and Semantic Intelligence panel. The saved article text supports **four full-body articles**: PRID 1684194 is extracted from the existing saved HTML capture; PRIDs 1972618, 2042765, and 2114060 use separate `manual_txt` representations. The dashboard displays four cards, one per PRID, despite five existing HTML capture rows and multiple text representations. Eleven evidence-backed event classifications are available across the four articles.

The two requested TXT files were attached to their existing captures. No article capture or capture run was created by either import. Existing source checksums, publication metadata, first-seen timestamps, and the PRID 1972618 representation remain intact. The import commands were rerun after the extraction update; both returned `duplicate` and reused their existing representation IDs.

## Article coverage and extracted events

| PRID | Headline | Verified publication date | Issuing ministry | Best text representation | Event classifications |
|---|---|---|---|---|---|
| 1684194 | Prohibition removed from Onion Export | 2020-12-28 | Ministry of Commerce & Industry | Existing saved HTML; full text extracted | `export_restriction_removal` |
| 1972618 | Government notifies Minimum Export Price (MEP) of USD 800 per Metric Ton on onion export to maintain domestic availability | 2023-10-28 | Ministry of Consumer Affairs, Food & Public Distribution | `manual_txt` | `mep_introduction`, `government_procurement` |
| 2042765 | 2.60 lakh tons of onion exported in 2024-25, till 31st July, 2024 | 2024-08-07 | Ministry of Consumer Affairs, Food & Public Distribution | `manual_txt` | `reported_export_volume`, `government_procurement`, `market_price_report` |
| 2114060 | Centre withdraws 20% duty on Onion Export effective from April 1st, 2025 | 2025-03-22 | Ministry of Consumer Affairs, Food & Public Distribution | `manual_txt` | `export_duty_reduction`, `reported_export_volume`, `market_arrivals`, `production_estimate`, `market_price_report` |

The article dates above retain the verified date precision; no timezone or unverified publication time was added. For PRID 2114060, the announcement/publication date is 22 March 2025 and the stated duty withdrawal takes effect 1 April 2025. The dashboard shows these separately.

### Evidence-grounded facts

- **1684194:** The saved full HTML supports removal of the onion-export prohibition, with effect from 01.01.2021. This is classified as removal, not introduction, of a restriction.
- **1972618:** The full text supports the USD 800/MT MEP for 29 October–31 December 2023 and separately supports additional procurement of 2 lakh tons for the buffer. Publication date and policy dates remain distinct.
- **2042765:** The saved TXT includes the article body and annexures. It reports **2.60 lakh tons exported in FY 2024-25 through 31 July 2024** and **4.68 lakh tons procured for the price-stabilisation buffer**. The procurement passage does not state a more precise period. It also reports Maharashtra mandi modal prices of Rs.1,230–2,578 per quintal for April–July 2024, compared with Rs.693–1,205 for the corresponding 2023 period, and buffer procurement prices of Rs.2,833 versus Rs.1,724 per quintal (64% higher). The reported export quantity is classified as historical volume, not a newly introduced ban, duty reduction, or export incentive. The release also mentions an earlier prohibition lift; that historical reference was not emitted as a new policy event.
- **2114060:** The full text supports withdrawal of a **20% export duty**, effective **1 April 2025**. It also reports 17.17 LMT exports in FY 2023-24; 11.65 LMT in FY 2024-25 through “18th March” (the passage does not repeat the year); monthly exports rising from 0.72 LMT in September 2024 to 1.85 LMT in January 2025; increased arrivals at the named benchmark markets; a 227 LMT versus 192 LMT rabi production estimate; a 39% decline in all-India weighted average modal prices (comparison period not stated); a 10% all-India retail-price decline over the past month; and dated benchmark modal prices of Rs.1330/qtl and Rs.1325/qtl on 21 March 2025. The release spells the market names “Lasalgoan”, “Lasalgaon”, “Pimpalgaon”, and “Pimpalgoan” in different passages. They remain source text only; no market alias mapping was created. The exact supporting passages and periods are persisted with the event/fact data and rendered in the dashboard.

The code records all rules as experimental and leaves price effects unvalidated. It does not infer a guaranteed price increase or decrease. The PRID 2114060 TXT has two visibly mis-encoded apostrophes (`â€™`) in the copied body. Its source bytes and checksums were preserved; the imported text was not silently rewritten. The extracted event passages are unaffected.

## Capture and representation lineage

The original capture rows and their raw HTML hashes are unchanged:

| PRID | Existing capture ID | Existing HTML SHA-256 | Existing first-seen UTC |
|---|---|---|---|
| 1684194 | `b21d5968-db18-464a-bdb2-33ae2232d206` | `a7f0b3b97efc200c589c16f81be9b85fdd28eed6ba2647673ce65cd4951787dd` | `2026-10-09T10:35:00.892187+00:00` |
| 1684194 | `f5b185d0-34ea-4553-9551-17ea769f3416` | `fecf6b62d312990a7529778734ea5942617d5c4fb9aa1c5f16e85d1060e05ab8` | `2026-10-09T10:35:00.892187+00:00` |
| 1972618 | `a72daf8b-7b7d-4a3c-9def-e8d2d96a6132` | `d676952902a7808a412261fc68aa2225177cbf23ed6d76c67dc86b31e1f633c9` | `2026-10-09T10:35:00.910957+00:00` |
| 2042765 | `a4aba132-443a-40e6-8e50-e5da8c8e203c` | `69ed15b57be13c4fddeb8f3de3da32e0657acadaf2249deb56ddbccce5b1520f` | `2026-10-09T10:35:00.923925+00:00` |
| 2114060 | `b120024d-7bee-4f43-8582-e2c8ff7fbde1` | `3b5b2b91be180708df1a826b7ffc3436f3b03100bacb736feb960acab4e8234d` | `2026-10-09T09:33:43.453917+00:00` |

The two new TXT files were stored as follows. `content_sha256` covers the normalized article body after the `Posted On` metadata line is removed; `raw_sha256` covers the original local file bytes.

| PRID | Representation ID | Imported UTC | Raw TXT SHA-256 | Body SHA-256 |
|---|---|---|---|---|
| 2042765 | `4bce4c98-be96-40c8-a6a3-21da775f9f7c` | `2026-10-09T13:05:12.836445+00:00` | `d517b32f89f5899591b0ec028ca973c5520cae3bf678b5ce1e67e948fac2c29a` | `8a80378f844df19b334751145fd731d1a1bf1ef1038a9c73de73dbf0af7e6dee` |
| 2114060 | `aa87ac87-ab76-49cb-97c8-a5727f5aa505` | `2026-10-09T13:05:15.649052+00:00` | `4c70bd76c390d838fddb865e815b1c501345eb4abb0461a0b62ccaacc0f8b84f` | `4c71775f6a971fc70a811801e32b1ae02fc3750cd6a0846636e3e78d970b6117` |

The PRID 1972618 `manual_txt` representation was also preserved: ID `0996048d-9ad4-47e5-a5e8-67a4854df50c`, raw SHA-256 `ee29c1ed7de7a7f328474f61743335fdc00b0a2e86a3adfecb2b3318fc91bbce`, body SHA-256 `0baae72fb8c6db41e6d1ed4eeb632c13d1f07ddb5268b1a129657982eb379924`, imported at `2026-10-09T12:35:57.845084+00:00`.

The capture/representation table counts are **5 captures / 3 manual TXT representations**. Price-table counts remain **291 canonical (`agri_daily_prices`) / 21,864 historical (`agri_historical_price_observations`)**. The importer writes only to the event representation table; it does not modify either price table.

## API and dashboard verification

- `GET /api/agri/events/recent?limit=50` returned HTTP 200, `ready`, and four unique article cards.
- Each card carries the original title, verified publication date/ministry, full article text, source representation, and classification evidence. The three TXT cards expose their actual import timestamps and representation checksums.
- Each article appears once, including PRID 1684194 which has two HTML capture rows.
- The Semantic Intelligence panel displays the categories, exact evidence, available quantities/reporting periods, effective date, source text, and unvalidated-impact limitation.
- A Microsoft Edge Playwright smoke test against the production Next.js build and live API passed. It checked each PRID appears exactly once, checked event labels and dates, expanded full source text for PRIDs 2042765 and 2114060, and observed no page exceptions.
- Existing visual styling, layout, fonts, themes, animation, and navigation were not redesigned. Reported facts use the panel's existing text and evidence styling.

## Validation results

- Backend suite: **92 passed**, with two upstream Starlette/AnyIO deprecation warnings.
- Focused event/full-text tests: **16 passed**. Tests cover actual saved source files, PRID/date/ministry anchoring, exact event evidence, preservation of capture IDs/checksums/first-seen/publication data, and idempotency by both raw and normalized-content checksum.
- API smoke: **passed** against the configured SQLite database; asserted all four PRIDs, four full-body texts, current representation counts, exact effective/announcement dates, and unchanged price counts.
- Frontend TypeScript (`tsc --noEmit`): **passed**.
- Production build (`npm.cmd run build`): **passed**.
- Real browser smoke: **passed** against production Next.js and Microsoft Edge.

## Remaining Model B limitations and next steps

These rule-supported labels have not been reviewed by human annotators and are not accuracy measurements. There is no validated event-to-price effect estimate, and the reported market changes do not establish causality. The text uses market spellings such as “Lasalgoan”; no market alias or grade mappings were added. The TXT import proves file integrity and capture association, not a cryptographic signature from PIB. The visible mojibake in PRID 2114060 should be corrected only from a separately preserved, verified source representation.

For dataset expansion, collect more genuine PIB full texts and other authorized primary sources while retaining first-seen/revision lineage. For classification evaluation, prepare a human-reviewed set that separately labels event type, exact supporting passage, quantity/unit/period, policy announcement versus effective date, geography, and uncertainty of price impact. Have reviewers resolve disagreements before reporting precision/recall or any price-effect findings. Keep future price-outcome evaluation temporally separated from the article/classification decisions.
