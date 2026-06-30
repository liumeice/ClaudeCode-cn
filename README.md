# Claude Code Docs PDF Generator

A 3-step pipeline that scrapes the [Claude Code Docs (zh-CN)](https://code.claude.com/docs/zh-CN/) website and produces a single merged PDF with full bookmark / table-of-contents structure.

## Output

| File | Description |
|------|-------------|
| `sidebar.json` | Full documentation tree structure (JSON) |
| `sidebar.md` | Human-readable markdown table of contents |
| `Output/ClaudeCodeDocs.pdf` | Final merged PDF with bookmarks |
| `Output/temp/Cover_Claude_Code.pdf` | Styled cover page |
| `temp/pdfs/*.pdf` | Individual per-page PDFs (intermediate) |

## Quick Start

```bash
# Activate the virtual environment
source .venv/Scripts/activate        # Linux / macOS
.venv\Scripts\activate.bat           # Windows (cmd)

# Run the entire pipeline
run.bat

# Or run individual steps
run.bat step1   # Scrape sidebar structure → sidebar.json + sidebar.md
run.bat step2   # Generate individual page PDFs → temp/pdfs/*.pdf + cover
run.bat step3   # Merge into final PDF → Output/ClaudeCodeDocs.pdf
```

## Pipeline Overview

```
step1_scrape_sidebar.py  →  sidebar.json  +  sidebar.md
step2_generate_pdfs.py   →  temp/pdfs/*.pdf  +  cover PDF
step3_merge_pdfs.py      →  Output/ClaudeCodeDocs.pdf
```

### Step 1 — Scrape Sidebar

Uses Playwright (sync API, Chromium) to visit each top-level navigation tab on the docs site, extracts sidebar groups and page links via JavaScript evaluation, and outputs:

- **`sidebar.json`** — hierarchical tree of all documentation pages
- **`sidebar.md`** — plain-text markdown table of contents

Scraped nav tabs (8 total):

| Tab | Starting URL |
|-----|-------------|
| 快速开始 | `/docs/zh-CN/quickstart/` |
| 使用 Claude Code 代理 | `/docs/zh-CN/using/` |
| 管理 | `/docs/zh-CN/managing/` |
| 设置 | `/docs/zh-CN/configs/` |
| 参考 | `/docs/zh-CN/reference/` |
| Agent SDK | `/docs/zh-CN/agent-sdk/` |
| 新闻动态 | `/docs/zh-CN/news/` |
| 资源 | `/docs/zh-CN/resources/` |

### Step 2 — Generate Individual PDFs

Reads `sidebar.json`, visits each page with Playwright, and:

1. Injects **`DOM_MANIPULATE_JS`** (~300 lines) into each page to:
   - Hide navigation sidebars, in-page TOC, footers, and feedback widgets
   - Expand collapsed tab/accordion components (all panels visible inline)
   - Normalize image and SVG sizing for print layout
   - Set cream/gray backgrounds to white for clean printing
   - Apply print-friendly CSS with proper page-break behavior
2. Exports each page as an individual **A4-sized PDF** to `temp/pdfs/`
3. Generates a styled **cover page PDF** (`Output/temp/Cover_Claude_Code.pdf`)

> **Idempotent** — already-generated PDFs are skipped. Safe to re-run after modifying `DOM_MANIPULATE_JS`.

### Step 3 — Merge PDFs

Uses **PyMuPDF** (`fitz`) to merge all individual PDFs into `Output/ClaudeCodeDocs.pdf` with:

- Precise page-level **bookmarks** matching the sidebar hierarchy
- Category nodes pointing to their first child's starting page
- Full **TOC** (table of contents) embedded in the PDF

## Dependencies

- **Python 3.x** with virtual environment (`.venv/`)
- **Playwright** (sync API, Chromium) — browser automation for scraping and PDF export
- **PyMuPDF** (`fitz`) — PDF merging and bookmark/TOC generation

Install dependencies (if rebuilding the venv):

```bash
pip install playwright pymupdf
playwright install chromium
```

## Project Structure

```
├── CLAUDE.md                  # Project instructions for Claude Code
├── run.bat                    # Windows batch runner for the pipeline
├── step1_scrape_sidebar.py    # Step 1: scrape sidebar structure
├── step2_generate_pdfs.py     # Step 2: generate individual page PDFs + cover
├── step3_merge_pdfs.py        # Step 3: merge PDFs with bookmarks
├── sidebar.json               # Generated: documentation tree (Step 1)
├── sidebar.md                 # Generated: markdown TOC (Step 1)
├── temp/
│   ├── pdfs/                  # Generated: individual page PDFs (Step 2)
│   ├── hooks_ancestors.json   # Hook configuration data
│   ├── hooks_dom.json         # Hook DOM snapshot data
│   └── ...
└── Output/
    ├── ClaudeCodeDocs.pdf     # Final merged PDF (Step 3)
    └── temp/
        └── Cover_Claude_Code.pdf  # Cover page (Step 2)
```
