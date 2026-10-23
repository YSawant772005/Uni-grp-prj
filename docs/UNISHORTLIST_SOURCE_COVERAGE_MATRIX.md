# UniShortlist — source, rights and country coverage

Checkpoint: **2026-10-22, 08:20 UTC / 13:50 IST**. No external sources were crawled for this documentation. Availability refers to previously captured official responses/logs or a recorded access limitation. Development/recovery counts were independently queried read-only.

Read [interrupted recovery](UNISHORTLIST_INTERRUPTED_WORK_RECOVERY.md) for exact manifests, exclusions, backup and unapproved import plan. Registration, implementation, permission, successful import and current academic applicability are distinct claims.

## 1. Complete registry inventory

`backend/app/ingestion/registry.py` has **12 specifications: seven enabled and five disabled**. Eight concrete adapters include the disabled IPEDS completions parser. The generic webpage adapter is configurable separately. No new national connector was introduced in the interrupted task: existing Dutch/French adapters were extended and wrapped in exact-plan tooling.

| Source key | Geography / entity kind | Registry and adapter | Rights / policy | Actual active development coverage | Additional isolated coverage |
| --- | --- | --- | --- | --- | --- |
| `ror` | Global institution identity | Enabled; REST adapter and bulk directory tools | CC0 identities; GeoNames attribution | 30,328 references, one canonical UAL identity match; **zero programmes supplied by ROR** | Original directory preserved |
| `ual_masters` | One Spanish university; named Master's plans | Enabled; implemented | Dataset CC BY; separate webpage access rules | One institution / **five programmes** | Original five preserved |
| `fr_monmaster` | France; historical 2025 pathways/M1 offerings | Enabled, explicit limit; implemented | Licence Ouverte v2.0 | **Zero active** French institutions/programmes; historical jobs retained | **108 institutions / 7,843 offerings** |
| `duo_rio_masters` | Netherlands; registry Master's offerings | Enabled, bounded/manual; implemented | CC BY 4.0 | **Zero** Dutch institutions/programmes | **41 providers / 1,501 offerings** |
| `ipeds_hd` | US institutional directory and graduate flags | Enabled, explicit limit; implemented | NCES public domain | No active US institutions/programmes; old source/jobs retained | None |
| `ipeds_ic` | US historical institution charges | Enabled, historical/manual; implemented | NCES public domain | No active US institutions/programmes | None |
| `nces_cip` | Discipline taxonomy | Enabled; implemented HTML parser | NCES public domain | No programme records supplied | None |
| `ipeds_completions` | US award/CIP statistical rows | **Disabled**; parser blocked without official mapping | Public domain; dictionary requirement unresolved | No active programme imports | None |
| `whed` | Global institution recognition reference | **Disabled**; no runnable adapter | Automated fetch prohibited without permission | None | None |
| `erasmus_mundus` | Joint Master's catalogue | **Disabled**; no adapter | Access/reuse assessment required | None | None |
| `licensed_provider` | Contract-specific placeholder | **Disabled**; no contracted integration | Licence/credentials missing | None | None |
| `kaggle_community` | Per-dataset community placeholder | **Disabled**; no approved dataset | Provenance/reuse review required | None | None |

Counts are source-linked active records, not all historical discovery attempts. The ROR match and UAL institution overlap and must not be added as two universities. Distinct source offering IDs are not necessarily distinct qualification families.

## 2. Implemented sources: metadata, actual use and next action

### ROR — `ror`

- **Publisher / URLs:** Research Organization Registry. REST: <https://api.ror.org/v2/organizations>. Official bulk concept: <https://doi.org/10.5281/zenodo.6347574>. Selected release: <https://zenodo.org/records/23500708>.
- **Format / access:** bounded REST JSON for identity checks; official ZIP/v2 JSON for the global directory. `ror_dump.py` streams/validates a keyed local artifact; `ror_directory.py` performs checkpointed transactional imports and replay. No whole-registry REST pagination was used.
- **Rights:** CC0-1.0 identity data; GeoNames CC BY 4.0 attribution retained. No programme, tuition or admissions data is supplied by ROR.
- **Version / availability:** v2.15 published 2026-10-20, retrieved 2026-10-22T05:07:28Z. Dataset version is not an academic year. ZIP SHA256 `7a7bf58d5ac18436ed98daf5da906913761d54869edf86d405e51966609dd133`.
- **Dry run / isolated / development:** release validation completed; 500-row checkpoint then full recovery import; repeat zero creates / 30,328 unchanged; exact development migration/import/API deployment authorized and completed.
- **Actual coverage:** 146,716 organizations examined, 30,328 active education references across 223 codes, 116,388 excluded, 913 missing websites, zero duplicate/conflicting source IDs, five archive reconciliation flags and one existing canonical UAL match.
- **Next:** directory work is complete. Do not rebuild it. Canonical promotion/archive reconciliation requires separate evidence and authorization. ROR alone cannot make an institution Master's-review-ready.

Current UAL institutional evidence is an ROR query document: the website fact is
verified; official name, aliases, location and reported relationships remain
candidate facts. Accepted ROR identity and approved institution/source associations
are separate records. Name evidence is present without a claim that every name
fact was individually verified.

### University of Almería — `ual_masters`

- **Publisher / URLs:** Universidad de Almería. Feed: <https://campus.ual.es/ual/api/estudios/planes/titulaciones/MOF/es>. Dataset rights: <https://datos.gob.es/es/catalogo/u04800001-titulos-universitarios>. Individual example: <https://www.ual.es/estudios/masteres/presentacion/7101>.
- **Format / access:** official MOF JSON, then at most one official catalogue and five HTML programme pages per run. Robots checks, allowed redirects, literal title and plan binding are required. Course URLs must come from source catalogue evidence, not invented patterns.
- **Rights:** dataset CC BY with university attribution and changes identified. This is not blanket reuse permission for HTML prose. Descriptions use short reference excerpts and independently authored reviewer summaries.
- **Availability / period:** saved HTTP 200 feed has 64 raw plan rows, 35 eligible after joint/double-master holds. Pilot academic year is unknown. Thirty additional eligible plans were not imported or page-crawled in this task.
- **Identity:** `ual:master:plan:{cod_plan}`. Publisher `ual_dataset_publisher:u04800001` is not an authoritative university identifier; genuine ROR `003d3xx08` is separately accepted and reviewed.
- **Actual imports / tests:** bounded pilot and repeat/page tests completed. Development has one approved UAL institution, five accepted programme identities, five verified official pages, one publication with reviewed description and four candidates. Existing five remain unchanged in recovery.
- **Next:** preserve pilot. Any remaining-plan import needs a separate bounded approval. Templates must not become duration, ECTS, admissions or price facts.

### Netherlands DUO/RIO — `duo_rio_masters`

- **Publisher / URLs:** Dienst Uitvoering Onderwijs. Dataset: <https://onderwijsdata.duo.nl/datasets/ho_opleidingsoverzicht>. CKAN API: <https://onderwijsdata.duo.nl/api/3/action/datastore_search>. Official rights corroboration: <https://data.overheid.nl/dataset/ho_opleidingsoverzicht>.
- **Version:** package `7c0686f4-b5c2-418e-8e44-7be0057d8084`, resource `ffffa7ad-e6a2-4ba7-9fc2-a09df4128555`, modified 2026-10-21T02:35:16.559393.
- **Format / access / rights:** CKAN Datastore JSON, CC BY 4.0, attribute DUO/dataset and normalization. Existing fetcher uses 0.5 requests/second, one worker, timeout/retry. Snapshot bound is 5,000 offerings / 10,000 scanned rows; ordinary runs above 100 require the planned workflow.
- **Availability / source filtering:** metadata and samples returned HTTP 200; 28 frozen responses. Of 2,752 MASTER rows, 466 lack provider/UUID/title, 91 have unsupported partner relationships and one duplicates an offering, leaving 2,194 adapter candidates.
- **Identity / holds:** stable `duo:offering:{UUID}` and reporting-unit `rio_provider_id`. Further preflight holds 693 offerings across 23 shared-board/subunit providers. No parent-university merge is guessed from names or a governing board.
- **Selected data / applicability:** 1,501 offerings / 41 providers. Registry validity reports 1,484 unexpired and 17 future; academic year is unknown. Registry validity does not establish open admissions. WEBSITE is an institution-site candidate, never a verified individual programme URL.
- **Dry run / tests:** earlier five-offering pilot; corrected 100-record multi-page dry run; deterministic 100/500-record fixtures, ambiguity/cache/policy/rollback/replay tests. **Final queue assertions and full suite rerun complete on 2026-10-22: 470 passed / 7 skipped** (current source mounted, isolated stack). Sources and captures unchanged since the frozen manifests; both manifests and all 110 captured bodies re-hashed with 0 mismatches.
- **Isolated import:** **1,501 offerings / 41 pending providers** persisted and replayed with zero additions. First job is `partial` because of known frozen holdout warnings; all selected records were created without validation errors, conflicts or automatic approval/publication.
- **Development:** zero records imported from this source; no active DUO source row. New wrapper is not deployed.
- **Next:** finish final regressions and plan/backup checks, obtain exact development approval. Reconcile held providers later with authentic organisational evidence. New institutions still require authoritative identity/name/website/package review.

### France Mon Master — `fr_monmaster`

- **Publisher / URLs:** French Ministry of Higher Education, Research and Space. Dataset: <https://data.enseignementsup-recherche.gouv.fr/explore/dataset/fr-esr-mon_master/>. API: <https://data.enseignementsup-recherche.gouv.fr/api/explore/v2.1/catalog/datasets/fr-esr-mon_master/records>.
- **Format / access / rights:** Explore v2.1 JSON; explicit limit, 0.5 requests/second, one worker, 100-page bound. Licence Ouverte v2.0; attribute ministry and 2025 snapshot. Selected fields exclude applicant/outcome statistics.
- **Version / availability:** modified 2025-12-04T08:00:00+00:00, **historical campaign 2025**. Metadata/samples returned HTTP 200; 82 frozen responses, 8,167 source rows. Nine joint/double-award paths held, leaving 8,158 candidates.
- **Identity / holds:** UAI reporting-unit identity; programme `fr-monmaster:ifc:{ifc}`. Mention/pathway and M1 semantics retained. Two archived institution identities hold 312 offerings; three titles exceed the 250-character limit. No archive revival or title truncation.
- **Dry run / isolated:** 100-record dry run passed. **7,843 offerings / 108 pending institutions** persisted; replay added zero. Known joint warnings produce a `partial` job with no missing selected records. No automatic review or publication.
- **Development:** historical source and two jobs remain, but **zero active French institutions/programmes**. Archived historical catalogue records are not current active coverage.
- **Next:** final tests and exact approved frozen import. Archive reconciliation is separate. Assess a current campaign before making current-offer claims. No individually verified university course page is provided by this source.

### US IPEDS HD — `ipeds_hd`

- **Publisher / URL:** NCES, US Department of Education. Configurable release, default <https://nces.ed.gov/ipeds/datacenter/data/HD2024.zip>; official dictionary validation in `adapters/ipeds.py`.
- **Format / access / rights:** zipped CSV, one bounded download with ETag cache; explicit manual limit, no approved refresh schedule. US federal public-domain data; attribute NCES/IPEDS.
- **Data:** institution UNITID, name, address, classification, website and graduate flags. **No individual named Master's programmes**, course descriptions or admissions deadlines.
- **Availability / tests:** previous official dictionary/live checks and HD/IC cross-source ownership regressions are recorded. No new download occurred in programme work or this checkpoint.
- **Imports / period:** current development retains an **HD2023** source label and two historical jobs; no active US institutions/programmes after the old approved reset. Configuration default HD2024 does not rewrite past source applicability.
- **Next:** use for institution identity only when a genuine programme source needs it. Do not ingest directory volume as a substitute for programmes.

### US IPEDS IC — `ipeds_ic`

- **Publisher / URL:** NCES, <https://nces.ed.gov/ipeds/datacenter/data/IC2023.zip>.
- **Format / rights / registration:** zipped CSV, public domain, explicit manual limit; `historical_snapshot_manual_only`.
- **Period / data:** 2023–24 institution-reported room/board charges and graduate application fee. IC2024 lacks the mapped fields; these are not current programme tuition.
- **Tests / imports:** historical dictionary/format and identity corroboration tests recorded; no new live check. No IC source row in the current five-source development baseline, no active US programme import and no interrupted-task import.
- **Next:** retain historical applicability; this is not a programme-volume priority.

### NCES CIP — `nces_cip`

- **Publisher / URL / rights:** NCES, <https://nces.ed.gov/ipeds/cipcode/>, public-domain taxonomy.
- **Format / implementation:** enabled concrete adapter parses HTML select options into two-digit CIP `CandidateField` series. Taxonomy is not an individual programme or proof of an institution's offer.
- **Tests / availability / imports:** deterministic adapter infrastructure exists; no new live check or programme import here. No source row in the current five-source development baseline; zero programme records supplied.
- **Next:** maintain classification only when required. Configured interval is not an active schedule while the global scheduler is off.

## 3. Disabled, restricted and proposed integrations

| Source | Authority / URL / format | Rights and availability | Implementation / actual imports | Exact next action |
| --- | --- | --- | --- | --- |
| `ipeds_completions` | NCES, <https://nces.ed.gov/ipeds/datacenter/data/C2023_A.zip>, CSV | Public domain; official AWLEVEL dictionary unresolved | Parser exists but disabled; no active programme imports | Obtain official labels, then assess whether award/CIP statistical rows can represent genuine identified programmes; never guess level |
| `whed` | IAU/WHED; registry labels UNESCO/IAU; <https://whed.net/> | `prohibited_automated_fetch`; <https://whed.net/using-whed.html> requires consent for substantial copying | Disabled specification, no runnable adapter, no imports | Written permission before automation; not a programme-volume workaround |
| `erasmus_mundus` | European Commission, <https://erasmus-plus.ec.europa.eu/> | `review_required`; earlier connection failure; page-specific rights/robots unresolved | Disabled, no adapter, no imports | Assess actual official data access and joint/consortium ownership before tests |
| `licensed_provider` | No contracted publisher; `example.invalid` is a placeholder | Licence and credentials missing | Disabled, no adapter/download/data | Agree rights and payload first; do not invent/contact endpoints |
| `kaggle_community` | Per-contributor datasets, <https://www.kaggle.com/datasets> | Per-dataset origin, rights, date and reuse review required | Disabled placeholder, no approved dataset/import | Trace official provenance before treating any value as authoritative |
| Generic `WebPageAdapter` | Explicit official HTML/PDF/JSON/CSV URL | Per-source permission/robots/access; not universal crawl permission | Implemented field rules and configured named-programme extraction; no extra active volume here | Configure real publisher, stable identity, permitted URL and rules; deterministic fixtures and bounded check |
| Finland Studyinfo/Konfo | Proposed official registry family | Actual endpoint/rights/current period not established in this task | Not registered/implemented; zero imports | Source assessment before code; do not invent access claims |
| Australia CRICOS | Proposed official register/licensed dataset route | Actual reusable bulk distribution not established | Not registered/implemented; zero imports | Confirm licence, distribution and provider/qualification identifiers |
| Spain RUCT/QEDU | Proposed official registries beyond UAL | Machine-readable access/reuse not established | Not registered/implemented; zero imports | Assess official format, permission and award relationships |
| Other national registries | No additional source confirmed | Unknown | Not started | Select country priority and verify an official programme-level source first |

No new licence was granted and no disabled source was enabled during this checkpoint. A reachable file does not waive terms or prove academic applicability.

## 4. Geographic strategy and gaps

| Country / region | Existing evidence | Actual programme gap | Priority |
| --- | --- | --- | --- |
| Netherlands | DUO IDs, 1,501 selected/rehearsed | Zero development programmes, no new verified course pages | Approve validated candidates first; reconcile provider holds and page evidence later |
| France | 7,843 selected/rehearsed historical 2025 offerings | Zero active French programmes; current campaign not established | Selected historical import with explicit labels, then current-source assessment |
| Spain | UAL five active, five verified pages, one published | Only one institution; national connector absent | Preserve pilot; optional separate UAL expansion; later RUCT/QEDU assessment |
| United States | IPEDS identity, historical charges and taxonomy | No identified current programme connector | Do not relabel graduate flags or statistical awards as named programmes |
| Finland / Australia | ROR references; proposed Studyinfo / CRICOS | No validated programme import | Confirm official rights and formats |
| EU joint programmes | Erasmus disabled placeholder | Access/rights/consortium model unresolved | Assessment after existing NL/FR delivery |
| UK, Canada, Germany, Italy, India, China and other codes below | ROR identities where present | No additional confirmed permitted programme connector | Country-specific official-source assessment; no assumed global feed |

The 223 codes are country/territory reference coverage, not 223 countries with Master's evidence. Missing ROR coverage is not proof that an institution or programme does not exist.

## 5. Source acceptance gate

1. Authentic publisher, actual access/reuse rights, attribution and academic period.
2. Stable offering ID and correct offering/awarding provider; strong IDs first, no name-only merges.
3. Bounded source capture, document hash, retrieval/source dates and exact evidence; ignore templates/unknowns.
4. Native-format fixtures, representative inspection, isolated persistent import/replay and reported conflicts/holds.
5. Fresh exact development plan, verified backup/rehearsal, impact/visibility report and current tests.
6. Explicit development write approval; separate human institution/fact/programme decisions afterwards.

## 6. Complete current reference-country inventory

Generated from the running read-only directory stats endpoint during this checkpoint. Counts are references, not university approvals or programme evidence. Recovery additions are separate. “No confirmed programme connector” means none is confirmed in this repository; it does not assert no official source exists.

| Country/territory code | ROR reference records | Development Master's programmes | Extra isolated offerings | Programme source status |
| --- | ---: | ---: | ---: | --- |
| AD | 2 | 0 | 0 | No confirmed programme connector |
| AE | 69 | 0 | 0 | No confirmed programme connector |
| AF | 59 | 0 | 0 | No confirmed programme connector |
| AG | 3 | 0 | 0 | No confirmed programme connector |
| AI | 1 | 0 | 0 | No confirmed programme connector |
| AL | 35 | 0 | 0 | No confirmed programme connector |
| AM | 22 | 0 | 0 | No confirmed programme connector |
| AO | 34 | 0 | 0 | No confirmed programme connector |
| AR | 172 | 0 | 0 | No confirmed programme connector |
| AS | 2 | 0 | 0 | No confirmed programme connector |
| AT | 104 | 0 | 0 | No confirmed programme connector |
| AU | 144 | 0 | 0 | CRICOS proposed; no validated connector |
| AW | 1 | 0 | 0 | No confirmed programme connector |
| AX | 1 | 0 | 0 | No confirmed programme connector |
| AZ | 54 | 0 | 0 | No confirmed programme connector |
| BA | 27 | 0 | 0 | No confirmed programme connector |
| BB | 6 | 0 | 0 | No confirmed programme connector |
| BD | 218 | 0 | 0 | No confirmed programme connector |
| BE | 92 | 0 | 0 | No confirmed programme connector |
| BF | 18 | 0 | 0 | No confirmed programme connector |
| BG | 58 | 0 | 0 | No confirmed programme connector |
| BH | 14 | 0 | 0 | No confirmed programme connector |
| BI | 15 | 0 | 0 | No confirmed programme connector |
| BJ | 23 | 0 | 0 | No confirmed programme connector |
| BM | 1 | 0 | 0 | No confirmed programme connector |
| BN | 14 | 0 | 0 | No confirmed programme connector |
| BO | 53 | 0 | 0 | No confirmed programme connector |
| BQ | 2 | 0 | 0 | No confirmed programme connector |
| BR | 612 | 0 | 0 | No confirmed programme connector |
| BS | 4 | 0 | 0 | No confirmed programme connector |
| BT | 5 | 0 | 0 | No confirmed programme connector |
| BW | 13 | 0 | 0 | No confirmed programme connector |
| BY | 54 | 0 | 0 | No confirmed programme connector |
| BZ | 3 | 0 | 0 | No confirmed programme connector |
| CA | 410 | 0 | 0 | No confirmed programme connector |
| CD | 69 | 0 | 0 | No confirmed programme connector |
| CF | 3 | 0 | 0 | No confirmed programme connector |
| CG | 4 | 0 | 0 | No confirmed programme connector |
| CH | 166 | 0 | 0 | No confirmed programme connector |
| CI | 18 | 0 | 0 | No confirmed programme connector |
| CL | 98 | 0 | 0 | No confirmed programme connector |
| CM | 52 | 0 | 0 | No confirmed programme connector |
| CN | 3,252 | 0 | 0 | No confirmed programme connector |
| CO | 225 | 0 | 0 | No confirmed programme connector |
| CR | 56 | 0 | 0 | No confirmed programme connector |
| CU | 39 | 0 | 0 | No confirmed programme connector |
| CV | 5 | 0 | 0 | No confirmed programme connector |
| CW | 4 | 0 | 0 | No confirmed programme connector |
| CY | 50 | 0 | 0 | No confirmed programme connector |
| CZ | 108 | 0 | 0 | No confirmed programme connector |
| DE | 618 | 0 | 0 | No confirmed programme connector |
| DJ | 1 | 0 | 0 | No confirmed programme connector |
| DK | 57 | 0 | 0 | No confirmed programme connector |
| DM | 5 | 0 | 0 | No confirmed programme connector |
| DO | 38 | 0 | 0 | No confirmed programme connector |
| DZ | 125 | 0 | 0 | No confirmed programme connector |
| EC | 111 | 0 | 0 | No confirmed programme connector |
| EE | 27 | 0 | 0 | No confirmed programme connector |
| EG | 125 | 0 | 0 | No confirmed programme connector |
| EH | 1 | 0 | 0 | No confirmed programme connector |
| ER | 1 | 0 | 0 | No confirmed programme connector |
| ES | 223 | 5 | 0 | UAL only; national registry unconfirmed |
| ET | 68 | 0 | 0 | No confirmed programme connector |
| FI | 50 | 0 | 0 | Studyinfo proposed; no validated connector |
| FJ | 4 | 0 | 0 | No confirmed programme connector |
| FM | 2 | 0 | 0 | No confirmed programme connector |
| FO | 1 | 0 | 0 | No confirmed programme connector |
| FR | 503 | 0 | 7,843 | Mon Master historical 2025; development import pending |
| GA | 4 | 0 | 0 | No confirmed programme connector |
| GB | 599 | 0 | 0 | No confirmed programme connector |
| GD | 1 | 0 | 0 | No confirmed programme connector |
| GE | 67 | 0 | 0 | No confirmed programme connector |
| GF | 1 | 0 | 0 | No confirmed programme connector |
| GH | 127 | 0 | 0 | No confirmed programme connector |
| GI | 1 | 0 | 0 | No confirmed programme connector |
| GL | 2 | 0 | 0 | No confirmed programme connector |
| GM | 7 | 0 | 0 | No confirmed programme connector |
| GN | 12 | 0 | 0 | No confirmed programme connector |
| GP | 3 | 0 | 0 | No confirmed programme connector |
| GQ | 2 | 0 | 0 | No confirmed programme connector |
| GR | 64 | 0 | 0 | No confirmed programme connector |
| GT | 14 | 0 | 0 | No confirmed programme connector |
| GU | 3 | 0 | 0 | No confirmed programme connector |
| GW | 2 | 0 | 0 | No confirmed programme connector |
| GY | 4 | 0 | 0 | No confirmed programme connector |
| HK | 28 | 0 | 0 | No confirmed programme connector |
| HN | 13 | 0 | 0 | No confirmed programme connector |
| HR | 62 | 0 | 0 | No confirmed programme connector |
| HT | 17 | 0 | 0 | No confirmed programme connector |
| HU | 74 | 0 | 0 | No confirmed programme connector |
| ID | 2,224 | 0 | 0 | No confirmed programme connector |
| IE | 43 | 0 | 0 | No confirmed programme connector |
| IL | 67 | 0 | 0 | No confirmed programme connector |
| IN | 2,283 | 0 | 0 | No confirmed programme connector |
| IQ | 130 | 0 | 0 | No confirmed programme connector |
| IR | 370 | 0 | 0 | No confirmed programme connector |
| IS | 10 | 0 | 0 | No confirmed programme connector |
| IT | 261 | 0 | 0 | No confirmed programme connector |
| JM | 9 | 0 | 0 | No confirmed programme connector |
| JO | 31 | 0 | 0 | No confirmed programme connector |
| JP | 1,681 | 0 | 0 | No confirmed programme connector |
| KE | 91 | 0 | 0 | No confirmed programme connector |
| KG | 38 | 0 | 0 | No confirmed programme connector |
| KH | 59 | 0 | 0 | No confirmed programme connector |
| KM | 1 | 0 | 0 | No confirmed programme connector |
| KN | 4 | 0 | 0 | No confirmed programme connector |
| KP | 12 | 0 | 0 | No confirmed programme connector |
| KR | 376 | 0 | 0 | No confirmed programme connector |
| KW | 16 | 0 | 0 | No confirmed programme connector |
| KY | 3 | 0 | 0 | No confirmed programme connector |
| KZ | 97 | 0 | 0 | No confirmed programme connector |
| LA | 10 | 0 | 0 | No confirmed programme connector |
| LB | 38 | 0 | 0 | No confirmed programme connector |
| LC | 5 | 0 | 0 | No confirmed programme connector |
| LI | 3 | 0 | 0 | No confirmed programme connector |
| LK | 41 | 0 | 0 | No confirmed programme connector |
| LR | 7 | 0 | 0 | No confirmed programme connector |
| LS | 1 | 0 | 0 | No confirmed programme connector |
| LT | 40 | 0 | 0 | No confirmed programme connector |
| LU | 10 | 0 | 0 | No confirmed programme connector |
| LV | 45 | 0 | 0 | No confirmed programme connector |
| LY | 59 | 0 | 0 | No confirmed programme connector |
| MA | 107 | 0 | 0 | No confirmed programme connector |
| MC | 1 | 0 | 0 | No confirmed programme connector |
| MD | 22 | 0 | 0 | No confirmed programme connector |
| ME | 7 | 0 | 0 | No confirmed programme connector |
| MG | 17 | 0 | 0 | No confirmed programme connector |
| MK | 22 | 0 | 0 | No confirmed programme connector |
| ML | 11 | 0 | 0 | No confirmed programme connector |
| MM | 128 | 0 | 0 | No confirmed programme connector |
| MN | 28 | 0 | 0 | No confirmed programme connector |
| MO | 8 | 0 | 0 | No confirmed programme connector |
| MP | 3 | 0 | 0 | No confirmed programme connector |
| MQ | 1 | 0 | 0 | No confirmed programme connector |
| MR | 5 | 0 | 0 | No confirmed programme connector |
| MS | 1 | 0 | 0 | No confirmed programme connector |
| MT | 11 | 0 | 0 | No confirmed programme connector |
| MU | 6 | 0 | 0 | No confirmed programme connector |
| MV | 6 | 0 | 0 | No confirmed programme connector |
| MW | 15 | 0 | 0 | No confirmed programme connector |
| MX | 711 | 0 | 0 | No confirmed programme connector |
| MY | 665 | 0 | 0 | No confirmed programme connector |
| MZ | 28 | 0 | 0 | No confirmed programme connector |
| NA | 5 | 0 | 0 | No confirmed programme connector |
| NC | 3 | 0 | 0 | No confirmed programme connector |
| NE | 10 | 0 | 0 | No confirmed programme connector |
| NG | 342 | 0 | 0 | No confirmed programme connector |
| NI | 43 | 0 | 0 | No confirmed programme connector |
| NL | 132 | 0 | 1,501 | DUO/RIO validated; development import pending |
| NO | 69 | 0 | 0 | No confirmed programme connector |
| NP | 76 | 0 | 0 | No confirmed programme connector |
| NU | 1 | 0 | 0 | No confirmed programme connector |
| NZ | 42 | 0 | 0 | No confirmed programme connector |
| OM | 37 | 0 | 0 | No confirmed programme connector |
| PA | 33 | 0 | 0 | No confirmed programme connector |
| PE | 137 | 0 | 0 | No confirmed programme connector |
| PF | 1 | 0 | 0 | No confirmed programme connector |
| PG | 8 | 0 | 0 | No confirmed programme connector |
| PH | 880 | 0 | 0 | No confirmed programme connector |
| PK | 273 | 0 | 0 | No confirmed programme connector |
| PL | 325 | 0 | 0 | No confirmed programme connector |
| PR | 41 | 0 | 0 | No confirmed programme connector |
| PS | 25 | 0 | 0 | No confirmed programme connector |
| PT | 415 | 0 | 0 | No confirmed programme connector |
| PW | 1 | 0 | 0 | No confirmed programme connector |
| PY | 41 | 0 | 0 | No confirmed programme connector |
| QA | 33 | 0 | 0 | No confirmed programme connector |
| RE | 3 | 0 | 0 | No confirmed programme connector |
| RO | 109 | 0 | 0 | No confirmed programme connector |
| RS | 48 | 0 | 0 | No confirmed programme connector |
| RU | 834 | 0 | 0 | No confirmed programme connector |
| RW | 23 | 0 | 0 | No confirmed programme connector |
| SA | 69 | 0 | 0 | No confirmed programme connector |
| SB | 2 | 0 | 0 | No confirmed programme connector |
| SC | 1 | 0 | 0 | No confirmed programme connector |
| SD | 59 | 0 | 0 | No confirmed programme connector |
| SE | 67 | 0 | 0 | No confirmed programme connector |
| SG | 120 | 0 | 0 | No confirmed programme connector |
| SI | 67 | 0 | 0 | No confirmed programme connector |
| SJ | 1 | 0 | 0 | No confirmed programme connector |
| SK | 48 | 0 | 0 | No confirmed programme connector |
| SL | 6 | 0 | 0 | No confirmed programme connector |
| SM | 1 | 0 | 0 | No confirmed programme connector |
| SN | 28 | 0 | 0 | No confirmed programme connector |
| SO | 48 | 0 | 0 | No confirmed programme connector |
| SR | 2 | 0 | 0 | No confirmed programme connector |
| SS | 10 | 0 | 0 | No confirmed programme connector |
| ST | 1 | 0 | 0 | No confirmed programme connector |
| SV | 28 | 0 | 0 | No confirmed programme connector |
| SX | 2 | 0 | 0 | No confirmed programme connector |
| SY | 38 | 0 | 0 | No confirmed programme connector |
| SZ | 2 | 0 | 0 | No confirmed programme connector |
| TC | 1 | 0 | 0 | No confirmed programme connector |
| TD | 9 | 0 | 0 | No confirmed programme connector |
| TG | 7 | 0 | 0 | No confirmed programme connector |
| TH | 228 | 0 | 0 | No confirmed programme connector |
| TJ | 23 | 0 | 0 | No confirmed programme connector |
| TL | 12 | 0 | 0 | No confirmed programme connector |
| TM | 12 | 0 | 0 | No confirmed programme connector |
| TN | 71 | 0 | 0 | No confirmed programme connector |
| TO | 1 | 0 | 0 | No confirmed programme connector |
| TR | 241 | 0 | 0 | No confirmed programme connector |
| TT | 6 | 0 | 0 | No confirmed programme connector |
| TW | 151 | 0 | 0 | No confirmed programme connector |
| TZ | 61 | 0 | 0 | No confirmed programme connector |
| UA | 307 | 0 | 0 | No confirmed programme connector |
| UG | 60 | 0 | 0 | No confirmed programme connector |
| US | 4,433 | 0 | 0 | IPEDS institution/statistics only |
| UY | 18 | 0 | 0 | No confirmed programme connector |
| UZ | 133 | 0 | 0 | No confirmed programme connector |
| VC | 2 | 0 | 0 | No confirmed programme connector |
| VE | 60 | 0 | 0 | No confirmed programme connector |
| VG | 1 | 0 | 0 | No confirmed programme connector |
| VI | 1 | 0 | 0 | No confirmed programme connector |
| VN | 267 | 0 | 0 | No confirmed programme connector |
| VU | 1 | 0 | 0 | No confirmed programme connector |
| WS | 3 | 0 | 0 | No confirmed programme connector |
| XK | 12 | 0 | 0 | No confirmed programme connector |
| YE | 60 | 0 | 0 | No confirmed programme connector |
| YT | 1 | 0 | 0 | No confirmed programme connector |
| ZA | 71 | 0 | 0 | No confirmed programme connector |
| ZM | 30 | 0 | 0 | No confirmed programme connector |
| ZW | 26 | 0 | 0 | No confirmed programme connector |

Total: **30,328 reference records across 223 codes**, **five active development programmes**, and **9,344 additional offerings in isolated recovery only**.

---

## POST-IMPORT VERIFICATION — 2026-10-22

Both sources are now **imported into development and deployed**, from the frozen snapshots only
(no live crawl at apply time). Full record: [interrupted recovery §11](UNISHORTLIST_INTERRUPTED_WORK_RECOVERY.md).

| Source | Licence | Version | Imported | Candidates | Status |
| --- | --- | --- | --- | --- | --- |
| `duo_rio_masters` (NL, DUO/RIO) | CC BY 4.0 | `2026-10-21T02:35:16.559393` | **1,501** programmes, 41 institutions | all `candidate` | deployed, 23 providers held |
| `fr_monmaster` (FR, Mon Master) | Licence Ouverte v2.0 | `2025-12-04T08:00:00+00:00` | **7,843** programmes, 108 institutions | all `candidate`, **historical 2025** | deployed, 2 archived UAI held |
| ROR directory | CC0 | v2.15 | 30,328 references, 223 countries | n/a (reference only) | deployed earlier |
| UAL official catalogue | official university source | 2026-10-21 | 5 programmes, 1 published | — | unchanged |

Verified: 9,349 total programmes; 1 published / 9,348 candidates; 150 institutions (149 pending);
81,599 evidence rows / 119 source documents; **0 duplicate `(source_key, external_key)`**;
all 7,843 FR offerings carry `academic_campaign = {"session":"2025"}`; all 1,501 NL offerings
carry official `offering_validity_period`; fees/requirements/intakes remain 0/0/0.
Idempotent replay of the identical command added **0** rows.
