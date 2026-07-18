# Future Development Ideas

**This directory holds specs, blueprints, and research for future features.**  
Build nothing here. Spec only. When a feature is ready to implement, it moves to the main codebase.

## Structure

```
future/
  README.md              ← This file
  agent-skills/          ← New agent capabilities (coder modules, sensory tools, etc.)
  simulation/            ← Engineering simulation engines (FEA, CFD, math)
  cognitive/             ← Cognitive pipeline enhancements
  infrastructure/        ← Auth, migration, monitoring
```

## Rules

1. **Spec, don't build.** Each file is a markdown document describing what, why, and how — not executable code.
2. **Route off-task ideas here.** When scope creep is detected mid-session, the Focus module suggests saving the idea here instead of building it immediately.
3. **Build when the endpoint is real.** Don't build a simulation engine until you have actual simulation data. Don't build an auth layer until you have untrusted users.
4. **Review quarterly.** Every 3 months, scan the `future/` directory. Promote ready specs to implementation. Archive stale ones.

## Active Specs

| Spec | Category | Status |
|------|----------|--------|
| Audio Processing Suite (EQ, room analysis, sound design) | agent-skills | Foundation built, expansion planned |
| Music Personality Engine (personality analyzer, album intel, Spotify sync) | agent-skills | Spec only — needs API credentials |
| Externalize sensory/coder/gamedev/devops as separate MCPs | infrastructure | Plan exists in docs/externalization-plan.md |
