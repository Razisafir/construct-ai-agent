# Task: Redesign AgentPanel.tsx and premium components

## Summary
Redesigned 5 components to match the Construct v2 design system, removing all inline style objects and replacing them with Tailwind classes using the new design tokens (bg-onyx, panel-bg, border-subtle, text-primary, text-secondary, accent-cyan, accent-cyan-dim, accent-gold, accent-gold-dim, status-running, status-running-bg, diff-add, diff-add-bg, diff-remove, diff-remove-bg, tertiary, tertiary-dim).

## Files Modified

### 1. AgentPanel.tsx
- Removed ALL inline `style={{}}` objects — replaced with Tailwind classes
- Agent header: `smart_toy` Material Symbol, status pill with dynamic classes per status (`bg-status-running-bg border-status-running/30 text-status-running` for working, etc.)
- Memory recall banner: `bg-bg-onyx border border-diff-add/30 text-diff-add`, memory icon, progress bar with `bg-accent-cyan` + `bg-diff-add` segments
- Timeline items: icon boxes `w-8 h-8 rounded-md bg-bg-onyx border border-border-subtle`, vertical connector line `bg-border-subtle`
- Active timeline item: `border-accent-cyan/50 shadow-[0_0_10px_rgba(0,245,255,0.2)]`
- Diff snippets: `bg-bg-onyx rounded-md border border-border-subtle font-mono text-xs`, `text-diff-add` / `text-diff-remove`
- Action buttons: Apply (`bg-status-running-bg border-status-running/30 text-status-running`), Skip (`bg-bg-onyx border-border-subtle text-text-secondary`), Stop (`bg-bg-onyx border-border-subtle text-diff-remove`)
- Goal input: `bg-bg-onyx rounded-lg border border-border-subtle focus-within:border-accent-cyan/50 focus-within:shadow-[0_0_10px_rgba(0,245,255,0.1)]`
- Panel wrapper: `bg-panel-bg font-mono glass-panel`
- All business logic (Tauri invoke/listen, state management, streaming, diff store) PRESERVED exactly

### 2. GlassCard.tsx
- Replaced `glass-panel` class with explicit Tailwind: `bg-[rgba(20,22,25,0.6)] backdrop-blur-[12px] -webkit-backdrop-blur-[12px] border border-border-subtle rounded`

### 3. GlowButton.tsx
- Primary: `bg-accent-cyan text-bg-onyx border-accent-cyan hover:bg-accent-cyan/80`
- Secondary: `bg-transparent text-text-primary border-transparent hover:bg-accent-cyan-dim luminous-border`
- Danger: `bg-diff-remove/10 text-diff-remove border-diff-remove/30 hover:bg-diff-remove/20`
- Ghost: `bg-transparent text-text-secondary border-transparent hover:text-text-primary hover:border-border-subtle`

### 4. StatusBadge.tsx
- idle: `text-text-secondary` / `bg-text-secondary`
- working: `text-accent-cyan` / `bg-accent-cyan animate-pulse`
- success: `text-status-running` / `bg-status-running`
- warning: `text-accent-gold` / `bg-accent-gold`
- error: `text-tertiary` / `bg-tertiary animate-pulse`
- Removed inline style objects, using Tailwind classes only

### 5. ProgressRing.tsx
- Progress fill: `text-accent-cyan`
- Percentage text: `text-text-primary`
- Removed inline style objects

## Build Verification
- `npm run build` — SUCCESS (no TypeScript or build errors)
- `npm run lint` (tsc --noEmit) — Type check passed

## Design Token Verification
All tokens used are confirmed in tailwind.config.js: bg-onyx, panel-bg, border-subtle, text-primary, text-secondary, accent-cyan, accent-cyan-dim, accent-gold, accent-gold-dim, status-running, status-running-bg, diff-add, diff-add-bg, diff-remove, diff-remove-bg, tertiary, tertiary-dim
