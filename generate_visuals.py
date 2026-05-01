#!/usr/bin/env python3
"""
Napkin Visual Generator
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Interactive tool: paste any text → auto-classify intent →
suggest Top 3 diagram layouts → generate via Napkin API →
download & open → pick your favorite or regenerate.

Usage:
    python generate_visuals.py
    python generate_visuals.py --file path/to/rubric-output.json
    python generate_visuals.py --format png
    python generate_visuals.py --lang fr-FR

Requirements:
    NAPKIN_API_TOKEN set in a .env file (or as an environment variable).
"""

import argparse
import http.client
import json
import os
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path


def _load_dotenv(path: str = ".env"):
    """Load key=value pairs from a .env file into os.environ (stdlib only)."""
    env_path = Path(path)
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:  # env var takes precedence
            os.environ[key] = value


_load_dotenv()

# ─── MS Learn brand ─────────────────────────────────────────────────────────

# Official Microsoft Learn style ID — use for all MS Learn / training content
MSLEARN_STYLE_ID = "EGW36S1QC8T38D1DCMR38RSD6GRKCRHD70T34DHD69JKECHN74TPCRSMCCWG"

# ─── Style registry ───────────────────────────────────────────────────────────

STYLE_MAP = {
    "Introduction to Product/Feature":    "CDQPRVVJCSTPRBB6D5P6RSB4",
    "Explanation of a Technical Concept": "CSQQ4VB1DGPP4V31CDNJTVKFBXK6JV3C",
    "Walkthrough of a Process":           "CSQQ4VB1DGPPRTB7D1T0",
    "Architecture and Design Patterns":   "CSQQ4VB1DGPPTVVEDXHPGWKFDNJJTSKCC5T0",
    "Case Study":                         "CDGQ6XB1DGPQ6VV6EG",
    "Troubleshooting Tips":               "CSQQ4VB1DGPQ6TBECXP6ABB3DXP6YWG",
}

# ─── Taxonomy → API visual_query mapping ──────────────────────────────────────

QUERY_MAP = {
    ("Process", "Sequence"):                           "sequence diagram",
    ("Process", "Flowcharts"):                         "flowchart",
    ("Process", "Journey"):                            "user journey",
    ("Timeline", "Timeline"):                          "timeline",
    ("Comparison", "Pros and Cons"):                   "pros and cons",
    ("Comparison", "Versus"):                          "comparison",
    ("Comparison", "Tables"):                          "table",
    ("Comparison", "Decision"):                        "decision matrix",
    ("Comparison", "Relationship"):                    "relationship diagram",
    ("Business Frameworks", "Funnel"):                 "funnel",
    ("Parts of a Whole", "Key Ideas"):                 "key ideas",
    ("Parts of a Whole", "Iceberg"):                   "iceberg",
    ("Parts of a Whole", "Converge"):                  "converge",
    ("Problems and Solutions", "Problem to Solution"): "problem solution",
    ("Problems and Solutions", "Challenges"):          "challenges",
    ("Cause and Effect", "Root Causes"):               "root cause",
    ("Cause and Effect", "Flowcharts"):                "flowchart",
    ("Hierarchy", "Pyramid"):                          "pyramid",
    ("Hierarchy", "Quadrant"):                         "quadrant",
    ("Mindmap", "Horizontal Mindmaps"):                "mindmap",
    ("Visual Metaphors", "Lens"):                      "lens",
    ("Visual Metaphors", "Prism"):                     "prism",
}

# ─── Intent → Top 3 diagram suggestions (from rubric) ─────────────────────────

INTENT_DIAGRAM_MAP = {
    "Walkthrough of a Process": [
        ("Process", "Sequence"),
        ("Process", "Flowcharts"),
        ("Process", "Journey"),
    ],
    "Explanation of a Technical Concept": [
        ("Parts of a Whole", "Key Ideas"),
        ("Mindmap", "Horizontal Mindmaps"),
        ("Parts of a Whole", "Iceberg"),
    ],
    "Architecture and Design Patterns": [
        ("Hierarchy", "Pyramid"),
        ("Comparison", "Relationship"),
        ("Hierarchy", "Quadrant"),
    ],
    "Troubleshooting Tips": [
        ("Cause and Effect", "Root Causes"),
        ("Problems and Solutions", "Problem to Solution"),
        ("Comparison", "Decision"),
    ],
    "Case Study": [
        ("Process", "Journey"),
        ("Timeline", "Timeline"),
        ("Problems and Solutions", "Problem to Solution"),
    ],
    "Introduction to Product/Feature": [
        ("Parts of a Whole", "Key Ideas"),
        ("Comparison", "Pros and Cons"),
        ("Business Frameworks", "Funnel"),
    ],
}

VIDEO_TYPES = list(INTENT_DIAGRAM_MAP.keys())

# ─── Classifier ───────────────────────────────────────────────────────────────

def classify_intent(text: str) -> tuple[str, int]:
    """Return (video_type, confidence_score). Score 0 = default fallback."""
    t = text.lower()
    scores = {vt: 0 for vt in VIDEO_TYPES}

    kw_map = {
        "Walkthrough of a Process": [
            "step", "steps", "how to", "process", "procedure", "workflow",
            "sequence", "first then next", "guide", "walkthrough", "tutorial",
            "follow", "instruction",
        ],
        "Explanation of a Technical Concept": [
            "explain", "concept", "understand", "what is", "why", "how does",
            "definition", "meaning", "works", "function", "mechanism", "principle",
        ],
        "Architecture and Design Patterns": [
            "architecture", "design", "pattern", "component", "layer", "structure",
            "system", "infrastructure", "service", "api", "microservice", "module",
            "diagram", "topology", "blueprint",
        ],
        "Troubleshooting Tips": [
            "error", "fix", "troubleshoot", "issue", "problem", "fail", "debug",
            "resolve", "cause", "symptom", "diagnose", "broken", "not working",
        ],
        "Case Study": [
            "case study", "example", "scenario", "customer", "company", "result",
            "outcome", "impact", "before", "after", "success", "story",
        ],
        "Introduction to Product/Feature": [
            "introduce", "introduction", "what is", "new", "feature", "product",
            "launch", "announce", "present", "benefit", "advantage", "overview",
        ],
    }

    for vt, keywords in kw_map.items():
        for kw in keywords:
            if kw in t:
                scores[vt] += 1

    best = max(scores, key=scores.get)
    top_score = scores[best]

    if top_score == 0:
        return "Explanation of a Technical Concept", 0
    return best, top_score


# ─── API helpers ──────────────────────────────────────────────────────────────

API_HOST = "api.napkin.ai"


def _headers(token: str, content_type: bool = False) -> dict:
    h = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    if content_type:
        h["Content-Type"] = "application/json"
    return h


def create_visual(payload: dict, token: str) -> str:
    conn = http.client.HTTPSConnection(API_HOST)
    conn.request("POST", "/v1/visual", json.dumps(payload), _headers(token, True))
    res = conn.getresponse()
    body = res.read()
    if res.status == 201:
        return json.loads(body)["id"]
    if res.status == 401:
        raise SystemExit("❌ Invalid or expired API token. Check NAPKIN_API_TOKEN.")
    if res.status == 429:
        retry_after = int(res.getheader("Retry-After", "10"))
        raise Exception(f"Rate limited. Retry after {retry_after}s.")
    raise Exception(f"API error {res.status}: {body.decode()}")


def poll_status(request_id: str, token: str) -> dict:
    delays = [3, 6, 12, 24, 48]
    for attempt, delay in enumerate(delays, 1):
        print(f"  ⏳ Attempt {attempt}/5 — waiting {delay}s...    ", end="\r", flush=True)
        time.sleep(delay)
        conn = http.client.HTTPSConnection(API_HOST)
        conn.request("GET", f"/v1/visual/{request_id}/status",
                     headers=_headers(token))
        res = conn.getresponse()
        data = json.loads(res.read())
        status = data.get("status")
        if status == "completed":
            print()
            return data
        if status == "failed":
            err = data.get("error", {})
            code = err.get("code", "unknown")
            if code == "no_credits":
                raise SystemExit("❌ No credits remaining. Top up at https://app.napkin.ai")
            raise Exception(f"Generation failed [{code}]: {err.get('message', '')}")
    raise Exception("Timed out. Visual generation did not complete.")


def _http_get_with_auth(url: str, token: str) -> bytes:
    """GET an authenticated API URL, following a single CDN redirect if needed."""
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
        # Redirect to CDN — fetch the pre-signed URL without auth
        location = res.getheader("Location")
        res.read()  # drain
        req = urllib.request.Request(location)
        with urllib.request.urlopen(req) as r:
            return r.read()
    if res.status == 200:
        return res.read()
    body = res.read()
    raise Exception(f"Download failed {res.status}: {body[:300].decode(errors='replace')}")


def download_files(status_data: dict, output_dir: Path,
                   slug: str, token: str, top3: list) -> list:
    results = []
    for i, file_info in enumerate(status_data.get("generated_files", [])):
        url = file_info["url"]
        fmt = file_info.get("format", "svg")
        rank = i + 1
        filepath = output_dir / f"{slug}_rank{rank}.{fmt}"
        filepath.write_bytes(_http_get_with_auth(url, token))
        cat, sub = top3[i] if i < len(top3) else ("Unknown", "Unknown")
        results.append({
            "rank": rank,
            "file": str(filepath),
            "format": fmt,
            "label": f"{cat} → {sub}",
            "query": QUERY_MAP.get((cat, sub), sub.lower()),
        })
    return results


# ─── UI helpers ───────────────────────────────────────────────────────────────

def hr():
    print("─" * 60)


def read_multiline_input(prompt: str = "") -> str:
    if prompt:
        print(prompt)
    print("(press Enter twice when done)\n")
    lines, blanks = [], 0
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line == "":
            blanks += 1
            if blanks >= 2:
                break
        else:
            blanks = 0
            lines.append(line)
    return "\n".join(lines).strip()


def make_slug(text: str, suffix: str = "") -> str:
    raw = (text[:50] + suffix).replace(" ", "-").lower()
    return "".join(c for c in raw if c.isalnum() or c == "-").strip("-") or "visual"


def print_suggestions(video_type: str, top3: list, confidence: int):
    conf_label = "high" if confidence >= 3 else ("medium" if confidence >= 1 else "low (default)")
    print(f"\n  📋 Intent detected : {video_type}")
    print(f"  🔍 Confidence      : {conf_label}")
    print(f"  🎨 Style           : {video_type}")
    print()
    print("  Suggested layouts:")
    for rank, (cat, sub) in enumerate(top3, 1):
        query = QUERY_MAP.get((cat, sub), sub.lower())
        print(f"    [{rank}] {cat} → {sub}  (query: \"{query}\")")


def choose_intent_manually() -> str:
    print("\n  Choose intent:")
    for i, vt in enumerate(VIDEO_TYPES, 1):
        print(f"    {i}. {vt}")
    raw = input("  Enter number [1-6]: ").strip()
    try:
        return VIDEO_TYPES[int(raw) - 1]
    except (ValueError, IndexError):
        print("  Invalid — keeping auto-detected intent.")
        return None


def open_files_in_browser(files: list):
    for f in files:
        webbrowser.open(Path(f["file"]).resolve().as_uri())
    print(f"  Opened {len(files)} file(s) in your browser.")


def print_files(files: list):
    print()
    for f in files:
        print(f"  [{f['rank']}] {f['label']}")
        print(f"      {f['file']}")


# ─── Build API payload ────────────────────────────────────────────────────────

def build_payload(text: str, video_type: str, top3: list,
                  fmt: str, lang: str,
                  sort_strategy: str = "relevance",
                  custom_style_id: str = None,
                  color_mode: str = "light",
                  width: int = None,
                  height: int = None) -> dict:
    queries = [QUERY_MAP.get((cat, sub), sub.lower()) for cat, sub in top3]
    payload = {
        "format": fmt,
        "content": text,
        "language": lang,
        "style_id": custom_style_id or STYLE_MAP.get(video_type),
        "visual_queries": queries,
        "number_of_visuals": len(queries),
        "orientation": "horizontal",
        "text_extraction_mode": "auto",
        "sort_strategy": sort_strategy,
        "transparent_background": fmt == "png",
        "color_mode": color_mode,
    }
    # width/height only relevant for raster (png); SVG is inherently scalable
    if fmt == "png":
        payload["width"] = width or 1920
        payload["height"] = height or 1080
    return payload


# ─── Generate + download cycle ────────────────────────────────────────────────

def generate_cycle(text: str, video_type: str, top3: list,
                   output_dir: Path, slug: str,
                   token: str, fmt: str, lang: str,
                   sort_strategy: str = "relevance",
                   custom_style_id: str = None,
                   color_mode: str = "light",
                   width: int = None,
                   height: int = None) -> list:
    payload = build_payload(text, video_type, top3, fmt, lang,
                            sort_strategy, custom_style_id,
                            color_mode, width, height)

    print(f"\n  🚀 Submitting to Napkin API...")
    request_id = create_visual(payload, token)
    print(f"  Request ID: {request_id}")

    print("  ⏳ Generating visuals...")
    status_data = poll_status(request_id, token)

    for w in status_data.get("warnings", []):
        print(f"  ⚠  Warning [{w.get('code')}]: layout may have been substituted.")

    print("  📥 Downloading files...")
    files = download_files(status_data, output_dir, slug, token, top3)
    return files


# ─── Main interactive loop ────────────────────────────────────────────────────

def run(args):
    token = os.environ.get("NAPKIN_API_TOKEN", "").strip()
    if not token:
        print("❌ NAPKIN_API_TOKEN is not set.")
        print("   Add it to a .env file:  NAPKIN_API_TOKEN=your-token")
        print("   Or set it inline:       $env:NAPKIN_API_TOKEN = 'your-token'")
        sys.exit(1)

    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    (output_dir / "selected").mkdir(exist_ok=True)

    fmt = args.format
    lang = args.lang
    color_mode = args.color_mode
    width = args.width
    height = args.height
    custom_style_id = MSLEARN_STYLE_ID if args.mslearn else None
    if args.mslearn:
        print("  🎓 Microsoft Learn branding active (use --no-mslearn to disable)")

    print()
    hr()
    print("  Napkin Visual Generator")
    hr()

    while True:
        # ── 1. Get text
        if args.file:
            raw = Path(args.file).read_text(encoding="utf-8")
            # Accept either a plain-text prompt or a rubric JSON
            try:
                rubric = json.loads(raw)
                if not rubric.get("visualizable", True):
                    print("❌ Rubric says visualizable: false. Nothing to generate.")
                    break
                text = "\n".join(
                    item
                    for inp in rubric.get("diagram_generation_inputs", [])
                    if inp.get("rank") == 1
                    for item in inp.get("content", [])
                ) or raw
                video_type = rubric.get("video_type", classify_intent(text)[0])
                top3 = INTENT_DIAGRAM_MAP.get(video_type, INTENT_DIAGRAM_MAP["Explanation of a Technical Concept"])
                confidence = 99  # from file, treat as authoritative
            except json.JSONDecodeError:
                text = raw.strip()
                video_type, confidence = classify_intent(text)
                top3 = INTENT_DIAGRAM_MAP[video_type]
            args.file = None  # only read file once; loop continues interactively
        else:
            hr()
            text = read_multiline_input("📝 Paste your text or describe the topic:")
            if not text:
                print("Nothing entered. Exiting.")
                break
            video_type, confidence = classify_intent(text)
            top3 = INTENT_DIAGRAM_MAP[video_type]

        # ── 2. Show classification
        print_suggestions(video_type, top3, confidence)

        # ── 3. Confirm / override
        print()
        action = input("  Generate these 3 layouts? [Y / change / n]: ").strip().lower()
        if action == "n":
            print("  Skipped.")
        else:
            if action == "change":
                override = choose_intent_manually()
                if override:
                    video_type = override
                    top3 = INTENT_DIAGRAM_MAP[video_type]
                    print_suggestions(video_type, top3, 99)

            slug = make_slug(text)

            # ── 4. Generate
            try:
                files = generate_cycle(
                    text, video_type, top3,
                    output_dir, slug,
                    token, fmt, lang,
                    custom_style_id=custom_style_id,
                    color_mode=color_mode,
                    width=width,
                    height=height,
                )
            except SystemExit as e:
                print(e)
                break
            except Exception as e:
                print(f"\n  ❌ {e}")
                if input("  Try again? [y/N]: ").strip().lower() != "y":
                    break
                continue

            # ── 5. Show results
            hr()
            print(f"  ✅ {len(files)} visual(s) generated:")
            print_files(files)

            open_q = input("\n  Open all in browser? [Y/n]: ").strip().lower()
            if open_q != "n":
                open_files_in_browser(files)

            # ── 6. Pick / regenerate loop
            while True:
                hr()
                pick = input(
                    "  Pick [1/2/3]  |  Regenerate [r]  |  New text [n]  |  Quit [q]: "
                ).strip().lower()

                if pick in ("1", "2", "3"):
                    idx = int(pick) - 1
                    chosen = files[idx]
                    dest = output_dir / "selected" / f"{slug}_selected.{chosen['format']}"
                    Path(chosen["file"]).replace(dest)
                    print(f"\n  ✅ Saved selected visual:")
                    print(f"     {chosen['label']}")
                    print(f"     → {dest}")
                    break

                elif pick == "r":
                    change_text = input("  Change the text? [y/N]: ").strip().lower()
                    if change_text == "y":
                        new_text = read_multiline_input("📝 New text:")
                        if new_text:
                            text = new_text
                            video_type, confidence = classify_intent(text)
                            top3 = INTENT_DIAGRAM_MAP[video_type]
                            print_suggestions(video_type, top3, confidence)

                    regen_slug = make_slug(text, "-regen")
                    try:
                        files = generate_cycle(
                            text, video_type, top3,
                            output_dir, regen_slug,
                            token, fmt, lang,
                            sort_strategy="variation",  # more variety on regenerate
                            custom_style_id=custom_style_id,
                            color_mode=color_mode,
                            width=width,
                            height=height,
                        )
                    except Exception as e:
                        print(f"\n  ❌ {e}")
                        break

                    print(f"\n  ✅ Regenerated {len(files)} visual(s):")
                    print_files(files)
                    open_q = input("\n  Open in browser? [Y/n]: ").strip().lower()
                    if open_q != "n":
                        open_files_in_browser(files)

                elif pick == "n":
                    break  # go back to outer while → new text input

                elif pick == "q":
                    hr()
                    print("  Done. Goodbye.")
                    return

                else:
                    print("  Enter 1, 2, 3, r, n, or q.")

        # ── 7. Another segment?
        again = input("\n  Generate visuals for another segment? [y/N]: ").strip().lower()
        if again != "y":
            break

    hr()
    print("  Done.")


# ─── Headless mode (for Copilot Chat agent) ─────────────────────────────────

def _load_text_from_file(path: str):
    """Return (text, video_type_or_None, confidence) from a plain-text or rubric JSON file."""
    raw = Path(path).read_text(encoding="utf-8")
    try:
        rubric = json.loads(raw)
        if not rubric.get("visualizable", True):
            return None, None, 0  # caller must check
        text = "\n".join(
            item
            for inp in rubric.get("diagram_generation_inputs", [])
            if inp.get("rank") == 1
            for item in inp.get("content", [])
        ) or raw.strip()
        vt = rubric.get("video_type")
        return text, vt, 99
    except json.JSONDecodeError:
        return raw.strip(), None, 0


def run_headless(args):
    """Non-interactive mode: write JSON result to stdout, progress to stderr."""
    token = os.environ.get("NAPKIN_API_TOKEN", "").strip()
    if not token:
        print(json.dumps({"status": "error", "message": "NAPKIN_API_TOKEN not set"}))
        sys.exit(1)

    if not args.file and not getattr(args, "text", None):
        print(json.dumps({"status": "error", "message": "--headless requires --file PATH or --text TEXT"}))
        sys.exit(1)

    # Redirect progress prints to stderr so stdout carries only JSON
    _real_stdout = sys.stdout
    sys.stdout = sys.stderr
    try:
        if getattr(args, "text", None):
            text = args.text.strip()
            rubric_vt, rubric_conf = None, 0
        else:
            text, rubric_vt, rubric_conf = _load_text_from_file(args.file)
        if text is None:
            sys.stdout = _real_stdout
            print(json.dumps({"status": "error", "message": "visualizable: false in rubric"}))
            sys.exit(0)

        # Intent: CLI flag > rubric > classifier
        if args.intent:
            video_type, confidence = args.intent, 99
        elif rubric_vt:
            video_type, confidence = rubric_vt, rubric_conf
        else:
            video_type, confidence = classify_intent(text)

        top3 = INTENT_DIAGRAM_MAP.get(video_type,
               INTENT_DIAGRAM_MAP["Explanation of a Technical Concept"])
        slug = make_slug(text, "-regen" if args.sort == "variation" else "")

        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        (output_dir / "selected").mkdir(exist_ok=True)

        custom_style_id = MSLEARN_STYLE_ID if getattr(args, "mslearn", True) else None
        files = generate_cycle(
            text, video_type, top3, output_dir, slug,
            token, args.format, args.lang, args.sort,
            custom_style_id=custom_style_id,
            color_mode=getattr(args, "color_mode", "light"),
            width=getattr(args, "width", None),
            height=getattr(args, "height", None),
        )
    except SystemExit as e:
        sys.stdout = _real_stdout
        print(json.dumps({"status": "error", "message": str(e)}))
        sys.exit(1)
    except Exception as e:
        sys.stdout = _real_stdout
        print(json.dumps({"status": "error", "message": str(e)}))
        sys.exit(1)
    finally:
        sys.stdout = _real_stdout

    conf_label = "high" if confidence >= 3 else ("medium" if confidence >= 1 else "low")
    result = {
        "status": "ok",
        "intent": video_type,
        "confidence": conf_label,
        "slug": slug,
        "visuals": [
            {
                "rank": f["rank"],
                "label": f["label"],
                "query": f["query"],
                "file": f["file"].replace("\\", "/"),
                "format": f["format"],
            }
            for f in files
        ],
    }
    print(json.dumps(result, indent=2))


def run_select(args):
    """Move a generated file to output/selected/."""
    if not args.slug or not args.rank:
        print(json.dumps({"status": "error", "message": "--select requires --slug and --rank"}))
        sys.exit(1)

    output_dir = Path("output")
    matches = sorted(output_dir.glob(f"{args.slug}_rank{args.rank}.*"))
    if not matches:
        print(json.dumps({"status": "error",
                          "message": f"File not found: output/{args.slug}_rank{args.rank}.*"}))
        sys.exit(1)

    src = matches[0]
    dest = output_dir / "selected" / f"{args.slug}_selected{src.suffix}"
    (output_dir / "selected").mkdir(exist_ok=True)
    src.replace(dest)
    print(json.dumps({"status": "ok", "selected": str(dest).replace("\\", "/")}))


# ─── Document scan mode ([NAPKIN-IMAGE] markers) ────────────────────────────

NAPKIN_MARKER_PREFIX = "[NAPKIN-IMAGE"


def extract_napkin_blocks(path: str) -> list:
    """Extract [NAPKIN-IMAGE] or [NAPKIN-IMAGE: slug-hint] blocks from a markdown doc.

    Each block starts on a line that begins with '[NAPKIN-IMAGE' and ends just
    before the next such marker or the end of the file.
    """
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    blocks, block_num, i = [], 0, 0
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith(NAPKIN_MARKER_PREFIX):
            slug_hint = None
            if ":" in stripped:
                slug_hint = stripped.split(":", 1)[1].rstrip("]").strip() or None
            i += 1
            content_lines = []
            while i < len(lines):
                if lines[i].strip().startswith(NAPKIN_MARKER_PREFIX):
                    break
                content_lines.append(lines[i])
                i += 1
            content = "\n".join(content_lines).strip()
            if content:
                block_num += 1
                blocks.append({"block": block_num, "slug_hint": slug_hint, "text": content})
        else:
            i += 1
    return blocks


def run_scan(args):
    """Scan a markdown document for [NAPKIN-IMAGE] blocks and generate visuals for each."""
    token = os.environ.get("NAPKIN_API_TOKEN", "").strip()
    if not token:
        print(json.dumps({"status": "error", "message": "NAPKIN_API_TOKEN not set"}))
        sys.exit(1)
    if not args.file:
        print(json.dumps({"status": "error", "message": "--scan requires --file PATH"}))
        sys.exit(1)

    blocks = extract_napkin_blocks(args.file)
    if not blocks:
        print(json.dumps({"status": "ok", "blocks_found": 0, "results": []}))
        return

    print(f"  Found {len(blocks)} [NAPKIN-IMAGE] block(s) in {args.file}", file=sys.stderr)

    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    (output_dir / "selected").mkdir(exist_ok=True)

    custom_style_id = MSLEARN_STYLE_ID if getattr(args, "mslearn", True) else None
    results = []

    for block in blocks:
        text = block["text"]
        print(f"\n  Block {block['block']}: {text[:70]}...", file=sys.stderr)
        video_type, confidence = classify_intent(text)
        top3 = INTENT_DIAGRAM_MAP.get(video_type,
               INTENT_DIAGRAM_MAP["Explanation of a Technical Concept"])
        slug = block["slug_hint"] or make_slug(text)
        try:
            files = generate_cycle(
                text, video_type, top3, output_dir, slug,
                token, args.format, args.lang,
                custom_style_id=custom_style_id,
                color_mode=getattr(args, "color_mode", "light"),
                width=getattr(args, "width", None),
                height=getattr(args, "height", None),
            )
            conf_label = "high" if confidence >= 3 else ("medium" if confidence >= 1 else "low")
            results.append({
                "block": block["block"],
                "status": "ok",
                "intent": video_type,
                "confidence": conf_label,
                "slug": slug,
                "visuals": [
                    {
                        "rank": f["rank"],
                        "label": f["label"],
                        "query": f["query"],
                        "file": f["file"].replace("\\", "/"),
                        "format": f["format"],
                    }
                    for f in files
                ],
            })
        except SystemExit as e:
            print(json.dumps({"status": "error", "message": str(e)}))
            sys.exit(1)
        except Exception as e:
            results.append({
                "block": block["block"],
                "status": "error",
                "message": str(e),
                "text_preview": text[:100],
            })

    print(json.dumps({"status": "ok", "blocks_found": len(blocks), "results": results}, indent=2))


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate Napkin AI visuals interactively from text."
    )
    parser.add_argument(
        "--file", "-f",
        metavar="PATH",
        help="Path to a rubric JSON file or plain-text file.",
    )
    parser.add_argument(
        "--format",
        choices=["svg", "png"],
        default="svg",
        help="Output format (default: svg).",
    )
    parser.add_argument(
        "--lang",
        default="en-US",
        help="BCP 47 language tag (default: en-US).",
    )
    # Headless / chat-agent mode
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Non-interactive: read --file or --text, output JSON to stdout.",
    )
    parser.add_argument(
        "--text",
        metavar="TEXT",
        default=None,
        help="Inline text to visualize (headless mode, alternative to --file).",
    )
    parser.add_argument(
        "--intent",
        choices=VIDEO_TYPES,
        metavar="VIDEO_TYPE",
        help="Override intent classification (headless mode).",
    )
    parser.add_argument(
        "--sort",
        choices=["relevance", "variation"],
        default="relevance",
        help="Sort strategy: relevance (default) or variation (regenerate).",
    )
    # Select mode
    parser.add_argument(
        "--select",
        action="store_true",
        help="Move a generated file to output/selected/.",
    )
    parser.add_argument("--slug", help="Slug for --select mode.")
    parser.add_argument("--rank", type=int, choices=[1, 2, 3], help="Rank to select.")
    # Document scan mode
    parser.add_argument(
        "--scan",
        action="store_true",
        help="Scan --file for [NAPKIN-IMAGE] markers and generate visuals for each block.",
    )
    # Branding / graphical constraints
    parser.add_argument(
        "--mslearn",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Apply the official Microsoft Learn style (default: on). Use --no-mslearn to disable.",
    )
    parser.add_argument(
        "--color-mode",
        dest="color_mode",
        choices=["light", "dark", "both"],
        default="light",
        help="Color mode (default: light).",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=None,
        help="Output width in px for png (default: 1920).",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=None,
        help="Output height in px for png (default: 1080).",
    )

    args = parser.parse_args()

    if args.headless:
        run_headless(args)
    elif args.select:
        run_select(args)
    elif args.scan:
        run_scan(args)
    else:
        run(args)


if __name__ == "__main__":
    main()
