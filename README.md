# Napkin Image Agent

Generate professional diagram visuals from plain text or structured content using [Napkin AI](https://napkin.ai) — directly from VS Code Copilot Chat.

There are two ways to use this workspace: a **chat-driven agent** for interactive use, and an **image generation agent** for automated bulk generation.

---

## Prerequisites

- A Napkin AI API token stored as `NAPKIN_API_TOKEN` in a `.env` file at the root of this workspace.
- VS Code with GitHub Copilot Chat.

```
NAPKIN_API_TOKEN=your_token_here
```

---

## Agent 1 — `napkin-chat`

**Best for:** Interactive, conversational visual generation. Paste any text, get 3 diagram options back.

### How it works

1. Open Copilot Chat and switch to the `napkin-chat` agent.
2. Paste your content — a paragraph, bullet list, slide notes, or script excerpt.
3. The agent classifies the content intent (e.g. "Explanation of a Technical Concept"), recommends the top 3 diagram types from the approved Napkin taxonomy, and generates all 3 visuals.
4. Review the 3 SVG files saved to the `output/` folder. Pick your favorite, or ask for a regeneration with adjusted content.

### Sample scenario

**Your prompt:**
> Azure Functions has four trigger types: HTTP Trigger for web requests, Timer Trigger for scheduled jobs, Blob Trigger for file events, and Queue Trigger for message processing.

**What happens:**
- Agent classifies this as *"Explanation of a Technical Concept / Parts of a Whole"*
- Recommends: (1) Key Ideas, (2) Horizontal Mindmap, (3) Iceberg
- Calls the Napkin API and downloads three SVG files:
  - `output/azure-functions-triggers_rank1.svg`
  - `output/azure-functions-triggers_rank2.svg`
  - `output/azure-functions-triggers_rank3.svg`

**Follow-up prompts you can use:**
> "Regenerate rank 1 but replace 'Queue Trigger' with 'Event Grid Trigger'"

> "Generate rank 2 again as PNG with transparent background"

> "Move rank 1 to the selected folder"

---

## Agent 2 — `napkin-image-agent`

**Best for:** Automated or bulk generation from a structured rubric JSON. Used when you already have a `diagram_generation_inputs` payload (e.g. output from a rubric agent or a saved `.json` file).

### How it works

1. Open Copilot Chat and switch to the `napkin-image-agent`.
2. Provide either:
   - A rubric JSON object directly in chat, or
   - A path to a saved rubric output file (e.g. `sample-rubric-output.json`)
3. The agent validates the input, maps each entry to Napkin API parameters, calls the API for all ranks, and downloads the files.
4. Files land in `output/` named by content slug and rank.

### Sample scenario

**Your prompt:**
> Generate visuals from `sample-rubric-output.json`

**What happens:**
- Agent reads the file, finds `"visualizable": true`
- Processes all 3 `diagram_generation_inputs` entries
- Outputs:
  - `output/<slug>_rank1.svg`
  - `output/<slug>_rank2.svg`
  - `output/<slug>_rank3.svg`

**Or paste the JSON directly:**
> Generate visuals from this rubric output:
> ```json
> { "video_type": "Walkthrough of a Process", "visualizable": true, "diagram_generation_inputs": [...] }
> ```

**Follow-up prompts:**
> "Regenerate rank 3 with updated content: add 'Retry Policy' as a fifth step"

> "Export all three as PNG with transparent background for video overlay"

---

## Output Structure

```
output/
  <content-slug>_rank1.svg    ← top recommendation
  <content-slug>_rank2.svg    ← second option
  <content-slug>_rank3.svg    ← third option
  selected/                   ← move your final picks here
```

---

## Choosing the Right Agent

| Situation | Use |
|---|---|
| You have raw text or a script excerpt | `napkin-chat` |
| You want to explore diagram options interactively | `napkin-chat` |
| You have a saved rubric JSON file | `napkin-image-agent` |
| You're running a batch pipeline | `napkin-image-agent` |
| You want to regenerate one specific visual | Either — both support regeneration prompts |

---

## Notes

- Napkin generates **diagrams and infographics only** — not photos or freeform illustrations.
- All exports are static files (SVG, PNG, or PPT). Animated or interactive diagrams are not supported.
- Downloaded file URLs from the Napkin API expire after 30 minutes — files are saved locally immediately after generation.
- If you see a `no_credits` error, your Napkin API plan has been exhausted.
