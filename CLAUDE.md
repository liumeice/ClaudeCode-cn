# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A 3-step pipeline that scrapes the [Claude Code Docs (zh-CN)](https://code.claude.com/docs/zh-CN/) website and produces a single merged PDF with full bookmark/TOC structure.

## Pipeline

```
step1_scrape_sidebar.py  →  sidebar.json + sidebar.md
step2_generate_pdfs.py   →  temp/pdfs/*.pdf (one per doc page) + cover PDF
step2_generate_pdfs_mt.py →  temp/pdfs/*.pdf (multi-threaded, faster) + cover PDF
step3_merge_pdfs.py      →  Output/ClaudeCodeDocs.pdf
```

| Step | Script | What it does |
|------|--------|--------------|
| 1 | [step1_scrape_sidebar.py](step1_scrape_sidebar.py) | Uses Playwright to visit each top-level nav tab on the docs site, extracts sidebar groups/pages via JS evaluation, outputs `sidebar.json` (hierarchical tree) and `sidebar.md` (markdown TOC) |
| 2 | [step2_generate_pdfs.py](step2_generate_pdfs.py) | Reads `sidebar.json`, visits each page sequentially with Playwright, injects `DOM_MANIPULATE_JS` to strip nav/sidebar/TOC/feedback widgets, exports each page as an individual A4 PDF. Also generates a styled cover PDF |
| 2 (MT) | [step2_generate_pdfs_mt.py](step2_generate_pdfs_mt.py) | Multi-threaded version using `asyncio` + semaphore-limited concurrency. Auto-detects CPU threads as default worker count. Supports `--workers`, `--timeout`, `--retries` CLI args |
| 3 | [step3_merge_pdfs.py](step3_merge_pdfs.py) | Uses PyMuPDF (`fitz`) to merge all individual PDFs into `Output/ClaudeCodeDocs.pdf` with precise page-level bookmarks matching the sidebar hierarchy |

## Commands

```bash
# Activate the virtual environment first
source .venv/Scripts/activate

# Run the full pipeline (single-threaded step2)
run.bat

# Or run individual steps
run.bat step1   # Scrape sidebar structure
run.bat step2   # Generate individual PDFs (single-threaded)
run.bat step3   # Merge into final PDF
```

Alternatively, run Python scripts directly:

```bash
python step1_scrape_sidebar.py

# Single-threaded
python step2_generate_pdfs.py

# Multi-threaded (recommended, auto-detects CPU threads)
python step2_generate_pdfs_mt.py
python step2_generate_pdfs_mt.py --workers 8       # specify worker count
python step2_generate_pdfs_mt.py --workers 2 --retries 5 --timeout 90

python step3_merge_pdfs.py
```

## Dependencies

- **Playwright** (sync API for step2, async API for step2_mt, Chromium) — browser automation for scraping and PDF export
- **PyMuPDF (fitz)** — PDF merging and bookmark/TOC generation
- Python virtual environment is pre-configured in `.venv/`

## Key Architecture Details

- **Step 1** iterates 8 nav tabs (快速开始, 使用 Claude Code 代理, 管理, 设置, 参考, Agent SDK, 新闻动态, 资源), each mapped to a starting URL
- **Step 2** uses an extensive `DOM_MANIPULATE_JS` script (~300 lines) injected into each page to: hide sidebars/TOC/footers/feedback, fix tab components (expand all panels inline), normalize image/SVG sizing, set cream backgrounds to white, apply print-friendly CSS, and handle page break behavior
- **Step 2** skips already-generated PDFs (idempotent — safe to re-run)
- **zh-CN → en fallback**: if a Chinese page returns 404, step2 scripts automatically try the English URL (`/zh-CN/` → `/en/`). The English PDF is saved as `_docs_en_*.pdf`.
- **Step 3** tracks page offsets to build accurate bookmarks where category nodes point to their first child's starting page. It also supports the English fallback — when `_docs_zh-CN_*.pdf` is missing, it looks for `_docs_en_*.pdf`.

## Output Files

| File | Description |
|------|-------------|
| `sidebar.json` | Full documentation tree structure from Step 1 |
| `sidebar.md` | Human-readable markdown TOC from Step 1 |
| `temp/pdfs/*.pdf` | Individual page PDFs from Step 2 (zh-CN or en fallback) |
| `Output/temp/Cover_Claude_Code.pdf` | Cover page PDF from Step 2 |
| `Output/ClaudeCodeDocs.pdf` | Final merged document from Step 3 |

## No Cursor/Copilot Rules

No `.cursorrules`, `.cursor/rules/`, or `.github/copilot-instructions.md` files exist in this project.
