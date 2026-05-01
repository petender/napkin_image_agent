# Napkin Image Generation Skill

**Domain:** Automated visual generation via Napkin AI API for video production pipelines.

**Use when:**
- Converting a rubric agent's `diagram_generation_inputs` JSON into actual image files
- Generating diagram visuals from structured content for video slides or overlays
- Regenerating a specific visual with updated content (same layout, new text)
- Bulk-generating all Top 3 diagram options in a single API call

**Do NOT use when:**
- The rubric output has `"visualizable": false`
- You need freeform image generation (Napkin generates diagrams and infographics, not photos)
- You need interactive or animated diagrams (Napkin exports static files only)

---

## Core Concept

This skill translates the structured output of the **Diagram Recommendation Agent**
(defined by the rubric in `draft rubric.md`) into live Napkin API calls, retrieves
the generated SVG/PNG/PPT files, and returns them ready for use in video production.

The rubric agent outputs → this skill consumes:
```json
{
  "video_type": "Explanation of a Technical Concept",
  "visualizable": true,
  "diagram_generation_inputs": [
    {
      "rank": 1,
      "category": "Parts of a Whole",
      "subcategory": "Key Ideas",
      "visual_query": "Show 4 key ideas for understanding Azure Functions",
      "content": ["Trigger", "Binding", "Execution Context", "Scaling"],
      "context_notes": "Azure Functions serverless intro video"
    }
  ]
}
```

---

## Step-by-Step Workflow

### Step 1: Validate Input

Before calling the API:

1. Check `visualizable: true` in rubric output. If false, stop and return `"No diagram generated"`.
2. Confirm `NAPKIN_API_TOKEN` environment variable is set.
3. Extract `video_type`, `language` (from context), and `diagram_generation_inputs`.

### Step 2: Assemble API Payload

For all 3 ranks in one call (preferred):

```python
def build_payload(inputs, video_type, language="en-US", format="svg"):
    style_map = {
        "Introduction to Product/Feature": "CDQPRVVJCSTPRBB6D5P6RSB4",
        "Explanation of a Technical Concept": "CSQQ4VB1DGPP4V31CDNJTVKFBXK6JV3C",
        "Walkthrough of a Process": "CSQQ4VB1DGPPRTB7D1T0",
        "Architecture and Design Patterns": "CSQQ4VB1DGPPTVVEDXHPGWKFDNJJTSKCC5T0",
        "Case Study": "CDGQ6XB1DGPQ6VV6EG",
        "Troubleshooting Tips": "CSQQ4VB1DGPQ6TBECXP6ABB3DXP6YWG",
    }
    query_map = {
        ("Process", "Sequence"): "sequence diagram",
        ("Process", "Flowcharts"): "flowchart",
        ("Process", "Journey"): "user journey",
        ("Timeline", "Timeline"): "timeline",
        ("Comparison", "Pros and Cons"): "pros and cons",
        ("Comparison", "Versus"): "comparison",
        ("Comparison", "Tables"): "table",
        ("Comparison", "Decision"): "decision matrix",
        ("Comparison", "Relationship"): "relationship diagram",
        ("Business Frameworks", "Funnel"): "funnel",
        ("Parts of a Whole", "Key Ideas"): "key ideas",
        ("Parts of a Whole", "Iceberg"): "iceberg",
        ("Parts of a Whole", "Converge"): "converge",
        ("Problems and Solutions", "Problem to Solution"): "problem solution",
        ("Problems and Solutions", "Challenges"): "challenges",
        ("Cause and Effect", "Root Causes"): "root cause",
        ("Cause and Effect", "Flowcharts"): "flowchart",
        ("Hierarchy", "Pyramid"): "pyramid",
        ("Hierarchy", "Quadrant"): "quadrant",
        ("Mindmap", "Horizontal Mindmaps"): "mindmap",
        ("Visual Metaphors", "Lens"): "lens",
        ("Visual Metaphors", "Prism"): "prism",
    }

    # Sort inputs by rank
    sorted_inputs = sorted(inputs, key=lambda x: x["rank"])

    # Use the content from rank 1 as the main content (all ranks share same source content)
    primary = sorted_inputs[0]
    content = "\n".join(primary["content"])
    context = primary.get("context_notes") or None

    # Build visual_queries list from all 3 ranks
    queries = []
    for inp in sorted_inputs:
        key = (inp["category"], inp["subcategory"])
        queries.append(query_map.get(key, inp["visual_query"]))

    return {
        "format": format,
        "content": content,
        "context": context,
        "language": language,
        "style_id": style_map.get(video_type),
        "visual_queries": queries,
        "number_of_visuals": len(queries),
        "orientation": "horizontal",
        "text_extraction_mode": "preserve",
        "sort_strategy": "relevance",
        "transparent_background": format == "png",
    }
```

### Step 3: Submit the Request

```python
import http.client, json, os, time

def create_visual(payload):
    token = os.environ["NAPKIN_API_TOKEN"]
    conn = http.client.HTTPSConnection("api.napkin.ai")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
    }
    conn.request("POST", "/v1/visual", json.dumps(payload), headers)
    res = conn.getresponse()
    if res.status == 201:
        return json.loads(res.read())["id"]
    elif res.status == 429:
        retry_after = int(res.getheader("Retry-After", "10"))
        raise RateLimitError(f"Rate limited. Retry after {retry_after}s.")
    else:
        raise APIError(f"HTTP {res.status}: {res.read().decode()}")
```

### Step 4: Poll for Status (Exponential Backoff)

```python
def poll_status(request_id, max_attempts=5):
    token = os.environ["NAPKIN_API_TOKEN"]
    delays = [3, 6, 12, 24, 48]
    conn = http.client.HTTPSConnection("api.napkin.ai")
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
    }
    for attempt, delay in enumerate(delays[:max_attempts]):
        time.sleep(delay)
        conn.request("GET", f"/v1/visual/{request_id}/status", headers=headers)
        res = conn.getresponse()
        data = json.loads(res.read())
        status = data.get("status")
        if status == "completed":
            return data
        elif status == "failed":
            error = data.get("error", {})
            raise VisualGenerationError(error.get("code"), error.get("message"))
    raise TimeoutError("Visual generation did not complete within expected time.")
```

### Step 5: Download Files Immediately

```python
import urllib.request

def _download_file(url, token):
    """The URL is an authenticated API endpoint that redirects to a CDN.
    Use http.client to send the Bearer token on the first hop, then follow
    the redirect to the CDN without auth (CDN URL is already pre-signed)."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    conn = http.client.HTTPSConnection(parsed.netloc)
    path = parsed.path + ("?" + parsed.query if parsed.query else "")
    conn.request("GET", path, headers={
        "Accept": "*/*",
        "Authorization": f"Bearer {token}",
    })
    res = conn.getresponse()
    if res.status in (301, 302, 307, 308):
        location = res.getheader("Location")
        res.read()  # drain
        with urllib.request.urlopen(location) as r:
            return r.read()
    if res.status == 200:
        return res.read()
    raise Exception(f"Download failed {res.status}: {res.read()[:200].decode(errors='replace')}")


def download_files(status_data, output_dir, video_slug):
    token = os.environ["NAPKIN_API_TOKEN"]
    generated = status_data.get("generated_files", [])
    downloaded = []
    for i, file_info in enumerate(generated):
        file_url = file_info["url"]
        ext = file_info.get("format", "svg")
        rank = i + 1
        filename = f"{video_slug}_rank{rank}.{ext}"
        filepath = os.path.join(output_dir, filename)
        with open(filepath, "wb") as f:
            f.write(_download_file(file_url, token))
        downloaded.append({"rank": rank, "file": filepath, "format": ext})
    return downloaded
```

### Step 6: Handle Warnings

After polling completes, inspect `warnings` in the status response:

```python
def process_warnings(status_data):
    warnings = status_data.get("warnings", [])
    for w in warnings:
        code = w.get("code")
        if code == "missing_visual_ids":
            print("⚠ API substituted a fallback layout for one or more visuals.")
        elif code == "invalid_style_id":
            print("⚠ Style ID not found; API used default style.")
        elif code == "not_enough_visuals":
            print("⚠ Fewer visuals generated than requested.")
        elif code == "some_visuals_failed_orientation_control":
            print("⚠ Some visuals don't match requested orientation.")
```

---

## Output Format

This skill returns a structured result that feeds back into the video production pipeline:

```json
{
  "request_id": "123e4567-e89b-12d3-a456-426614174000",
  "video_slug": "azure-functions-intro",
  "status": "completed",
  "files": [
    { "rank": 1, "file": "output/azure-functions-intro_rank1.svg", "format": "svg" },
    { "rank": 2, "file": "output/azure-functions-intro_rank2.svg", "format": "svg" },
    { "rank": 3, "file": "output/azure-functions-intro_rank3.svg", "format": "svg" }
  ],
  "warnings": [],
  "notes": "Rank 2 query was substituted by API fallback. Review layout before use."
}
```

---

## Constraints and Guardrails

- **NEVER** call the API if `visualizable: false` in the rubric output.
- **NEVER** modify the rubric's `content[]` values before passing to API (preserve mode).
- **ALWAYS** download files within the 30-minute expiry window.
- **ALWAYS** use `text_extraction_mode: "preserve"` to respect rubric-curated content.
- **LIMIT** to `number_of_visuals: 3` (Top 3 from rubric). Never request more than 4.
- **RESPECT** rate limits: never retry without reading `Retry-After`.
- **LOG** all request IDs and warning codes for traceability.

---

## Invocation Pattern (for agents calling this skill)

Read this SKILL.md when you need to:
- Generate images from a rubric agent's JSON output
- Understand which API parameters to use
- Handle API errors or warnings appropriately
- Map rubric taxonomy entries to `visual_query` strings
- Select the right style for a given video type

**Inputs needed from caller:**
1. The full rubric JSON output (or just `diagram_generation_inputs` + `video_type`)
2. A `video_slug` string (used for output file naming)
3. Output directory path
4. Target format: `"svg"` (default), `"png"` (video overlay), or `"ppt"` (slide deck)
5. Language BCP 47 tag (e.g. `"en-US"`)

**Optional inputs:**
- Custom `style_id` (overrides the video-type default)
- `width` / `height` for PNG exports (default: 1920 width for video resolution)
