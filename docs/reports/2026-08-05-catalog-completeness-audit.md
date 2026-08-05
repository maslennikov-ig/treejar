# Catalog attribute completeness

Task: `tj-feet.1`. Measured 2026-08-05 against the canonical runtime database.

Authority: the owner authorized this exact read on 2026-08-05 — SSH to the Noor
host, `docker compose exec` into the database container, aggregates only. The
session ran with `default_transaction_read_only = on` and every statement is a
`SELECT`. This report publishes counters and attribute **key names**; no product
row content, no identifiers and no free text appear anywhere in it.

## Reproducing

```sh
ssh noor-server 'cd /opt/noor && docker compose exec -T db sh -c \
  "exec psql -X -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -v ON_ERROR_STOP=1 -f -"' \
  < audit.sql
```

`audit.sql` begins with `SET default_transaction_read_only = on;` and contains
only the queries reproduced in [Queries](#queries).

## Population

| | count |
|---|---|
| rows in `products` | 920 |
| active | 344 |
| inactive | 576 |

Everything below is over the 344 **active** SKUs. Distinct categories: 11.
Distinct subcategories: 22.

## Completeness by language

| field | non-empty | share |
|---|---|---|
| `name_en` | 344 | 100.0% |
| `description_en` | 343 | 99.7% |
| `category` | 344 | 100.0% |
| `subcategory` | 281 | 81.7% |
| `attributes` (non-empty JSON object) | 344 | 100.0% |
| `name_ar` | 0 | **0.0%** |
| `description_ar` | 0 | **0.0%** |

`description_en` length, in characters:

| bucket | SKUs |
|---|---|
| empty | 1 |
| 1–40 | 0 |
| 41–200 | 81 |
| over 200 | 262 |

There is no Russian catalog column; RU is a conversation language served from the
same English rows.

## The `attributes` JSON

Every active SKU carries exactly the same 13 top-level keys — the sync writes a
fixed shape, so key presence proves nothing about content:

`availability`, `brand`, `features`, `images`, `manufacturer`, `raw_source`,
`source`, `specifications`, `treejar_category_slug`, `treejar_parent_category`,
`treejar_parent_category_slug`, `treejar_slug`, `treejar_url`.

Two of them carry the product attributes a sales claim would rely on.

| carrier | shape | non-empty | share |
|---|---|---|---|
| `attributes.features` | array on 344/344 | 263 | 76.5% |
| `attributes.specifications` | object on 344/344 | 203 | 59.0% |
| `attributes.brand` | scalar | 344 | 100.0% |
| `attributes.availability` | scalar | 344 | 100.0% |

`features` entries per SKU: 0 → 81 SKUs, 1 → 2, **2 → 192**, 3–5 → 14, 6–11 → 55.
More than half the catalog carries exactly two feature strings.

`specifications` keys per SKU: 0 → 141 SKUs (41.0%), 1 → 39 (11.3%),
7 or more → 164 (47.7%).

### The specification key namespace

67 distinct keys exist across the 203 SKUs that have any. Coverage of the widest
ones, as a share of all 344 active SKUs:

| key | SKUs | share |
|---|---|---|
| `Warranty` | 158 | 45.9% |
| `Line` | 112 | 32.6% |
| `Assembly Required` | 109 | 31.7% |
| `Table Color` | 102 | 29.7% |
| `Materials` | 98 | 28.5% |
| `Height` / `Length` / `Width` | 90 each | 26.2% |
| `Item Code` / `Weight kg` | 78 each | 22.7% |
| `Country` | 68 | 19.8% |
| `Recommended load` | 60 | 17.4% |
| `Castors` / `Gaslift` / `Mechanism` / `Upholstery` | 58 each | 16.9% |
| `Armrests` / `Base` / `Box Volume` / `Manufacturer's Warranty` / `Net Weight` | 57 each | 16.6% |
| `Seat Depth` / `Seat Height` | 53 each | 15.4% |
| `Dimensions Per Person` | 9 | 2.6% |
| `Control panel` / `Motor` / `Noise` / `USB ports` / `Wireless charge` | 3 each | 0.9% |

The namespace is not canonical. `Recommended load` (60) and `Recommended Load`
(56) are separate keys. So are `Warranty` (158) and `Manufacturer's Warranty`
(57), and `Top Color` and `Top Color Text`. Keys such as `Reclining Back2` and
`LEGSIZEtext` carry sync artefacts in the name itself. A claim contract that
verifies a field **path** has to normalize before it compares, or it will report
a supported claim as unsupported.

## Seating capacity

This is the question `tj-2pkk` (GH #54) has been blocked on since 2026-06-16.

| measurement | count | share of active |
|---|---|---|
| SKUs with a top-level capacity attribute key | **0** | 0.0% |
| specification keys that name a seating capacity | **0** | — |
| SKUs whose `features` mention a capacity word | 2 | 0.6% |
| SKUs whose `description_en` states an explicit `N`-seater/person/pax token | 28 | 8.1% |
| …of those, SKUs stating **two different numbers** | **25** | 89.3% of 28 |
| …of those, SKUs stating exactly one number | 3 | 10.7% of 28 |

Four specification keys match a `capacity|seat|person|people|pax` name pattern —
`Seat Depth` (53), `Seat Height` (53), `Dimensions Per Person` (9) and
`Dimensions Per Person Text` (9). All four are dimensions in millimetres or
metres. None is a seat count.

**Seating capacity is not a catalog field.** `_catalog_product_capacity`
(`src/llm/engine.py:1590`) derives it with a regular expression over the product
text, falling back to `1` when the text names a single-unit product term. That
derived integer then feeds unit-coverage arithmetic (`quantity * capacity`,
`src/llm/engine.py:1336`, `:2977`) and is presented to the model as an
authoritative line — `Catalog price basis: full N-seat SKU unit`
(`src/llm/engine.py:12744`).

So the value the model is told to trust is parsed from text that, wherever it
mentions a number at all, states two different ones in 25 of 28 cases.

## What this means for the stage

**`tj-feet.3` is not blocked by emptiness.** The stop condition asked whether the
catalog is sparse enough that a claim contract would mostly answer *not
specified*. For English it is not: 99.7% of active SKUs carry a real description,
76.5% carry at least one feature and 59.0% carry at least one specification. A
volunteered attribute usually has somewhere to be checked against.

Three findings do change how `tj-feet.3` must be built.

1. **Coverage is per-attribute, not per-SKU.** The specific attributes a sales
   reply volunteers are much thinner than the headline: `Mechanism` and
   `Upholstery` reach 16.9% of the catalog, `Materials` 28.5%. The `unknown`
   branch is therefore the common case for exactly the attributes that were
   fabricated in the sealed round, which makes the *useful partial answer* the
   main path rather than an edge case.

2. **The capacity requirement in the `tj-feet.3` design does not hold.** That
   design assumes a capacity value "already exists as a modelled field … so the
   claim contract can require it rather than let the model infer it". Against the
   production catalog there is no such field. A contract that requires a
   `capacity` field path would reject every capacity claim, including correct
   ones, and would break the existing coverage arithmetic. This needs an owner
   decision and is raised separately.

3. **Arabic has no catalog text at all.** 0 of 344 active SKUs carry `name_ar` or
   `description_ar`. Every Arabic reply is already grounded in English rows. A
   claim contract that requires the field path in the customer's language would
   fail 100% of Arabic attribute claims; it has to verify against the English row
   and treat the Arabic surface form as translation, not as a separate source.
   This also fixes the denominator for the Arabic metrics of `tj-feet.5`: Arabic
   grounding cannot be measured against Arabic catalog text, because none exists.

## Queries

```sql
SET default_transaction_read_only = on;

-- completeness by language
SELECT count(*) AS active_skus,
       count(*) FILTER (WHERE nullif(btrim(coalesce(name_en, '')), '') IS NOT NULL)        AS name_en,
       count(*) FILTER (WHERE nullif(btrim(coalesce(name_ar, '')), '') IS NOT NULL)        AS name_ar,
       count(*) FILTER (WHERE nullif(btrim(coalesce(description_en, '')), '') IS NOT NULL) AS desc_en,
       count(*) FILTER (WHERE nullif(btrim(coalesce(description_ar, '')), '') IS NOT NULL) AS desc_ar,
       count(*) FILTER (WHERE nullif(btrim(coalesce(category, '')), '') IS NOT NULL)       AS category,
       count(*) FILTER (WHERE nullif(btrim(coalesce(subcategory, '')), '') IS NOT NULL)    AS subcategory,
       count(*) FILTER (WHERE attributes IS NOT NULL
                          AND jsonb_typeof(attributes::jsonb) = 'object'
                          AND attributes::jsonb <> '{}'::jsonb)                            AS attributes_object
FROM products WHERE is_active;

-- attributes key distribution
SELECT k.key, count(*) FROM products p
CROSS JOIN LATERAL jsonb_object_keys(p.attributes::jsonb) AS k(key)
WHERE p.is_active AND jsonb_typeof(p.attributes::jsonb) = 'object'
GROUP BY k.key ORDER BY count(*) DESC, k.key;

-- specification key namespace
SELECT k.key, count(DISTINCT p.id) FROM products p
CROSS JOIN LATERAL jsonb_object_keys(p.attributes::jsonb -> 'specifications') AS k(key)
WHERE p.is_active AND jsonb_typeof(p.attributes::jsonb -> 'specifications') = 'object'
GROUP BY k.key ORDER BY count(DISTINCT p.id) DESC, k.key;

-- seating capacity in free text, and its internal consistency
WITH tokens AS (
  SELECT p.id, m[1] AS seats
  FROM products p,
       LATERAL regexp_matches(coalesce(p.description_en, ''),
         '([0-9]{1,2})\s*-?\s*(?:seater|seaters|person|persons|people|pax)\y', 'gi') AS m
  WHERE p.is_active
)
SELECT distinct_numbers, count(*) AS skus
FROM (SELECT id, count(DISTINCT seats) AS distinct_numbers FROM tokens GROUP BY id) t
GROUP BY distinct_numbers ORDER BY distinct_numbers;
```

The full script also buckets `description_en` length, counts `features` entries
and `specifications` keys per SKU, and checks the shape and emptiness of each
carrier. Every statement is an aggregate over `products`.
