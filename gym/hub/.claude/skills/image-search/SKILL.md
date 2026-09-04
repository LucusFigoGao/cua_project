---
name: image-search
description: Search and download UI screenshots from the web using image search. Use when you need reference screenshots of real websites/apps (e.g., Gmail, Slack, Notion) for building mock applications. Downloads high-resolution images to a local directory.
argument-hint: "<search query>" <output_dir> [--max N]
allowed-tools: Bash(python3 *)
---

# Image Search — Download UI Reference Screenshots

Search Google/Bing Images and download results to a local directory. Ideal for collecting UI reference screenshots of real applications when building mocks.

## Usage

```bash
python3 .claude/skills/image-search/scripts/image_search.py "<query>" <output_dir> [options]
```

### Examples

```bash
# Download Gmail UI screenshots
python3 .claude/skills/image-search/scripts/image_search.py "gmail inbox UI screenshot" gmail_mock/assets/screenshots --max 8

# Download multiple views of an app
python3 .claude/skills/image-search/scripts/image_search.py "slack channels sidebar desktop" slack_mock/assets/screenshots --max 5
python3 .claude/skills/image-search/scripts/image_search.py "slack thread panel reply" slack_mock/assets/screenshots --max 5

# Download with JSON output for programmatic use
python3 .claude/skills/image-search/scripts/image_search.py "notion page editor" notion_mock/assets/screenshots --max 5 --json
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--max N` | 8 | Maximum number of images to download |
| `--engine` | bing | Search engine: `bing` (recommended) or `google` |
| `--min-width` | 400 | Minimum image width in pixels |
| `--min-height` | 300 | Minimum image height in pixels |
| `--json` | off | Output results as JSON |

### Recommended search queries for mock app research

For best results, use specific queries combining the app name with UI-specific terms:

- `"<app> inbox UI screenshot"` — main view
- `"<app> settings page interface"` — settings
- `"<app> compose new message dialog"` — modals/dialogs
- `"<app> sidebar navigation desktop"` — navigation
- `"<app> dark mode interface"` — dark theme variant
- `"<app> mobile vs desktop UI comparison"` — responsive design

### Notes

- **Bing is the default engine** (Google blocks automated crawling)
- Downloads large, high-resolution photos by default
- If Bing fails, the script automatically falls back to Google
- Images are saved as numbered JPGs: `000001.jpg`, `000002.jpg`, etc.
- Requires `icrawler` Python package (`pip3 install icrawler`)
