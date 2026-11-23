# Codex Year in Review

Turn your local Codex activity into a private, interactive HTML recap. Explore a year of activity by day, see your longest streak, and get a breakdown of turn starts, tool calls, tokens, cache usage, and models.

## Install the skill

Clone the repository and copy the skill folder into your Codex skills directory.

```sh
git clone https://github.com/twfahey1/codex-year-in-review.git
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
cp -R codex-year-in-review/codex-year-in-review "${CODEX_HOME:-$HOME/.codex}/skills/"
```

In Codex, ask **“Use $codex-year-in-review to make my Codex recap.”** If it doesn't appear in the skill picker, restart Codex.

## Run it directly

Requires Python 3.9+ and IANA timezone data. Install the `zstd` command to include compressed rollouts.

```sh
cd codex-year-in-review
python3 codex-year-in-review/scripts/report.py \
  --timezone America/Chicago --output ~/codex-review.html
```

Open the resulting HTML file in a browser. It's self-contained and works offline. The generator reads the most recent 365 calendar days from active and archived Codex rollout logs. Coverage depends on the local history still available. Cloud-only activity, other devices, and deleted logs may be missing. Token totals describe logged model activity and should not be used to estimate billing.

This is an independent community project. [MIT license](LICENSE).
