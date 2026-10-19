# Terminal UI design

The web terminal follows the **Linear** design analysis from
[VoltAgent/awesome-design-md](https://github.com/VoltAgent/awesome-design-md/tree/main/design-md/linear.app) (MIT),
adapted for a dense trading screen. Tokens live at the top of `apps/web/app/globals.css`.

## From Linear

| Element | Value |
|---|---|
| Canvas | `#010102` near-black; light theme `#f7f8f8` |
| Surface ladder | `#0f1011` → `#141516` → `#18191a`, 1px hairlines `#23252a` / `#34343a` |
| Text | `#f7f8f8`, secondary `#d0d6e0`, subtle `#8a8f98`, tertiary `#62666d` |
| Accent | Lavender `#5e6ad2`, hover `#828fff` — primary buttons, focus rings, active states only |
| Type | System sans (SF Pro / Inter), negative tracking on headings; mono for every number |
| Shape | 8px buttons and inputs, 12px panels, pill status badges, top-edge highlight on lifted panels |

## Deliberate deviations

- **Ambient animated backdrop** (`components/Backdrop.tsx`, owner request): drifting lavender/violet aurora, a
  slowly panning grid, a pointer-reactive node network with travelling "packets", a light beam and film grain. It is
  decorative, reads no market data, pauses when the tab is hidden and is static under `prefers-reduced-motion`.
- **Glass panels**: panels are translucent with backdrop blur so the backdrop shows through, plus a cursor-follow
  spotlight and border glow.
- **Trading semantics keep green / red / amber** (`#4cc38a`, `#eb5757`, `#f2c94c`), which Linear's marketing palette
  avoids. Direction and risk states need them.

## Interaction

- Values flash green or red when they move (spot, BRTI series, thresholds, UP / DOWN quotes, equity, cash).
- Order-book rows carry depth bars scaled to the largest visible level.
- Contract cards show a window-elapsed bar that turns amber in the final no-entry minutes (2 min for 15m, 5 min for 1h).
- Research tabs use a sliding indicator; keys `1`–`9` switch tabs when focus is not in a field.
- `⌘K` / `Ctrl+K` (or **Jump to…** in the header) opens a command palette for panels, paper accounts, theme and
  refresh. It contains no order, RUN, STOP or halt commands.
- The theme choice is remembered in browser storage.

Element labels, roles and test IDs used by the Playwright suite are unchanged.
