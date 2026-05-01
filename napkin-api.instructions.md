---
applyTo: "**"
---

# Napkin AI API – Integration Instructions

These instructions govern all interactions with the Napkin AI API (`https://api.napkin.ai`)
within the video creation pipeline. They must be followed by any agent or skill that calls the API.

---

## 1. Authentication

All requests require a Bearer token:

```
Authorization: Bearer <NAPKIN_API_TOKEN>
```

- Store the token in the environment variable `NAPKIN_API_TOKEN`.
- Never log or expose the token in output, files, or error messages.
- A `401` response means the token is missing, expired, or invalid – surface this clearly to the user.

---

## 2. Async Workflow (3-Step, Always)

The API is **asynchronous**. Follow this sequence every time:

```
1. POST /v1/visual          → receive request ID
2. GET  /v1/visual/{id}/status  → poll until status = "completed" or "failed"
3. GET  <file_url>          → download each file immediately (URLs expire in 30 minutes)
```

**Polling rules:**
- Start polling after 3 seconds.
- Use exponential backoff: 3s → 6s → 12s → 24s → 48s → stop after 5 attempts.
- If `status = "failed"` and `error.code = "no_credits"`: inform user, stop.
- If `status = "failed"` and `error.code = "no_visuals"`: simplify content, retry once.
- A `429` response includes a `Retry-After` header – respect it before retrying.

---

## 3. Parameter Mapping (Rubric JSON → API Body)

The diagram recommendation rubric produces a `diagram_generation_inputs` array.
Map each entry to an API call as follows:

| Rubric Field | API Parameter | Notes |
|---|---|---|
| `visual_query` | `visual_query` | Used for single-visual calls |
| `visual_query` (array) | `visual_queries` | Use with `number_of_visuals ≥ 2` |
| `content[]` (array) | `content` | Join array items with `\n` separator |
| `context_notes` | `context` | Nullable; omit if empty |
| *(video language)* | `language` | BCP 47 tag, e.g. `"en-US"`. Always specify. |
| *(brand preference)* | `style_id` | See style registry below |
| *(video format)* | `orientation` | Default `"horizontal"` for video |
| *(export need)* | `format` | `"svg"` default; `"png"` for video overlay; `"ppt"` for slide decks |
| *(overlay use)* | `transparent_background` | `true` when exporting PNG for video overlay |
| `rank` (1,2,3) | *(controls call order)* | Process rank 1 first; store results by rank |

**Generating all 3 Top options in one call** (preferred for efficiency):
```json
{
  "format": "svg",
  "content": "<assembled content>",
  "context": "<context_notes>",
  "language": "en-US",
  "visual_queries": ["<rank1 query>", "<rank2 query>", "<rank3 query>"],
  "number_of_visuals": 3,
  "orientation": "horizontal",
  "sort_strategy": "relevance",
  "text_extraction_mode": "preserve"
}
```
Use `text_extraction_mode: "preserve"` because the rubric agent has already curated the content precisely.

**Single-visual call** (for regeneration or fallback):
```json
{
  "format": "svg",
  "content": "<assembled content>",
  "context": "<context_notes>",
  "language": "en-US",
  "visual_query": "<specific query>",
  "number_of_visuals": 1,
  "orientation": "horizontal",
  "text_extraction_mode": "preserve"
}
```

---

## 4. Rubric Taxonomy → `visual_query` Mapping

Use this exact mapping table when converting rubric category/subcategory to API `visual_query` values:

| Rubric Category | Rubric Subcategory | API `visual_query` |
|---|---|---|
| Process | Sequence | `"sequence diagram"` |
| Process | Flowcharts | `"flowchart"` |
| Process | Journey | `"user journey"` |
| Timeline | Timeline | `"timeline"` |
| Comparison | Pros and Cons | `"pros and cons"` |
| Comparison | Versus | `"comparison"` |
| Comparison | Tables | `"table"` |
| Comparison | Decision | `"decision matrix"` |
| Comparison | Relationship | `"relationship diagram"` |
| Business Frameworks | Funnel | `"funnel"` |
| Parts of a Whole | Key Ideas | `"key ideas"` |
| Parts of a Whole | Iceberg | `"iceberg"` |
| Parts of a Whole | Converge | `"converge"` |
| Problems and Solutions | Problem to Solution | `"problem solution"` |
| Problems and Solutions | Challenges | `"challenges"` |
| Cause and Effect | Root Causes | `"root cause"` |
| Cause and Effect | Flowcharts | `"flowchart"` |
| Hierarchy | Pyramid | `"pyramid"` |
| Hierarchy | Quadrant | `"quadrant"` |
| Mindmap | Horizontal Mindmaps | `"mindmap"` |
| Visual Metaphors | Lens | `"lens"` |
| Visual Metaphors | Prism | `"prism"` |

> **Note:** `visual_query` is a best-effort hint. If the API cannot satisfy the query with the
> given content, it will fall back to the best-fitting layout. Check `warnings` in the status
> response for `missing_visual_ids` or fallback indicators.

---

## 5. Style Selection (Video Production Context)

Choose style based on video type from the rubric:

| Video Type | Recommended Style | `style_id` |
|---|---|---|
| Introduction to Product/Feature | Radiant Blocks (colorful, bold) | `CDQPRVVJCSTPRBB6D5P6RSB4` |
| Explanation of Technical Concept | Elegant Outline (formal, clear) | `CSQQ4VB1DGPP4V31CDNJTVKFBXK6JV3C` |
| Walkthrough of a Process | Subtle Accent (professional, readable) | `CSQQ4VB1DGPPRTB7D1T0` |
| Architecture and Design Patterns | Corporate Clean (flat, business) | `CSQQ4VB1DGPPTVVEDXHPGWKFDNJJTSKCC5T0` |
| Case Study | Carefree Mist (casual, approachable) | `CDGQ6XB1DGPQ6VV6EG` |
| Troubleshooting Tips | Monochrome Pro (focused, minimal) | `CSQQ4VB1DGPQ6TBECXP6ABB3DXP6YWG` |

Use a custom `style_id` if the team has defined a brand style in the Napkin app.

---

## 6. Output and File Handling

- Download files **immediately** after status = `"completed"` (30-minute expiry).
- Save files locally using the naming convention: `<video_slug>_rank<N>_<visual_query>.<ext>`
  - Example: `azure-functions-intro_rank1_keyideas.svg`
- Store the downloaded file path and the request `id` for traceability.
- For PNG exports used in video overlays, set `transparent_background: true` and specify
  `width: 1920` (or `height: 1080`) to match standard video resolution.

---

## 7. Error and Warning Handling

| Code / Warning | Action |
|---|---|
| `401` | Stop, tell user token is invalid |
| `429` | Wait `Retry-After` seconds, retry |
| `no_credits` | Stop, tell user to recharge credits |
| `no_visuals` | Shorten `content`, retry once; if still fails, skip this rank |
| `missing_visual_ids` | Expected; API chose best fit. Log warning, proceed |
| `invalid_style_id` | Log warning, API used default style, proceed |
| `not_enough_visuals` | Some visuals failed; return what was generated |
| `some_visuals_failed_orientation_control` | Some visuals returned without requested orientation; proceed |

---

## 8. Constraints (from Rubric)

- Never pass diagram types outside the Approved Napkin Taxonomy.
- Never pass numeric chart types unless `content_cues` include quantitative data.
- `text_extraction_mode` must be `"preserve"` — the rubric agent already structures content.
- Content passed to API must be the assembled `content[]` array from rubric output, not raw video script.
- Do not call the API if `visualizable: false` in the rubric output.
- Content byte limit: 100,000 bytes. The rubric's structured content is always well below this.
