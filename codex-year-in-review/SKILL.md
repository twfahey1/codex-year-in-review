---
name: codex-year-in-review
description: Generate a private, interactive year-in-review HTML report from local Codex session logs. Use for requests about historical Codex activity, personal Codex stats, or a Codex recap. Current plan limits and billing use separate data sources.
---

# Codex year in review

Run [the report generator](scripts/report.py) using Python 3.9 or later. Pass the user's IANA timezone when known and choose a new HTML path outside a source-controlled directory. The default period is 365 calendar days ending today in the selected timezone. Use `--end YYYY-MM-DD` for a specific ending date.

```sh
python3 /path/to/skill/scripts/report.py --timezone America/Chicago --output /path/to/private/codex-review.html
```

The script reads active and archived rollouts under `CODEX_HOME` (default `~/.codex`). Use `--codex-home` to select another local Codex directory if requested. Compressed rollouts require `zstd` on PATH. The report identifies skipped compressed files and read errors. Call out incomplete coverage when summarizing the report.

Present the HTML as a local file link. If Codex can display a localhost preview, serve only the report directory on loopback and open it in the side panel. Keep the report, raw logs, and usage figures local unless the user separately requests sharing. The output includes aggregate activity and model labels. It contains no conversation text, tool arguments, thread IDs, or workspace paths.
