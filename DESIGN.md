# Design (terminal UI, Phase 2c)

Direction: dense, quiet, precise. Bloomberg-level information density with modern minimalism.

- **Hierarchy by data importance.** Official reference, countdown and executable Up/Down prices dominate. Model
  outputs are visually secondary to observed market data.
- **Provenance is always visible.** Every value shows its source (official / derived / external) and age. Stale
  values grey out and are labelled, never silently kept.
- **Action colours are reserved.** BUY UP, BUY DOWN, EXIT, HOLD and NO TRADE each get a distinct token. Green and
  red are never used for decoration.
- **Mode banner.** PAPER is permanently visible in the header. There is no UI control that implies live trading.
- **Themes.** Dark and light, built from semantic tokens. Tabular numerals for every price.
