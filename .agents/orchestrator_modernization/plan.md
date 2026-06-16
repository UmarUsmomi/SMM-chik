# Project Modernization Plan

## Milestones and Status

| Milestone | Name | Objective / Scope | Status |
|-----------|------|-------------------|--------|
| M1 | Exploration & Setup | Spawn explorer to inspect the current codebase, find HUD graphics drawing, background generators, image url check logic, watermark logic, font downloading, scheduler db settings, and warnings. Check baseline tests. | DONE |
| M2 | Graphics Layout & Fonts | Clean up HUD graphics (R1), remove watermark (R4), configure Russo One Google Font download, and create Cyberpunk HUD card with neon vertical indicator (R5). | DONE |
| M3 | BG Generators & Bypass | Remove LoremFlickr, Unsplash, AI Horde. Update fallback to HuggingFace -> Pollinations.ai -> Cloudflare Workers AI -> procedural gradient. Implement original image bypass (R2, R3). | DONE |
| M4 | Quotes & Scheduler | Add blockquote selectively (50-70% of posts) only for long articles (R6). Fix bot app.py scheduler using `last_pipeline_run` db settings (R7). | DONE |
| M5 | Final verification | Ensure all 51+ tests pass, remove warnings (sqlite3 datetime adapter, google.genai conversion if appropriate) (R8), and generate demo covers. | DONE |

## Execution Protocol per Milestone
For each milestone, we will use the iteration loop:
1. **Explorer**: Analyzes target files, suggests implementation strategy and files to modify.
2. **Worker**: Implements the changes, runs local unit tests, verifies code compiles.
3. **Reviewer & Challenger**: Review logic, run full tests, verify functionality.
4. **Auditor**: Audits integrity and verifies no warning/errors.
