# CortexStratum — Gap Closure Roadmap (v2.0)

| Gap | Phase | Effort | Impact | Risk |
|-----|-------|--------|--------|------|
| No observability (metrics, latency, errors) | **P1 — Observability Layer** | LOW ~150 loc | HIGH | None — builds on `mid.py` hooks |
| Single-threaded dispatch | **P2 — Async/Concurrency** | MED ~200 loc | HIGH | Thread safety (addressable with locks) |
| No plug-in system, no hot-reload | **P3 — Plugin Engine** | MED ~300 loc | HIGH | FS dependency |
| No OAuth for external APIs | **P4 — OAuth2 Client** | MED ~200 loc | MED | Stdlib only |
| No auth/encryption | **P5 — Auth + Encryption** | MED ~300 loc | MED | Design surface |
| No operational connectors | **P6 — Connector Framework** | LOW ~200 loc | MED | Depends on P4 |
| No lineage tracking / quality scoring | **P7 — Data Lineage** | MED ~250 loc | MED | Depends on MLM |
| No SIEM/SOAR / compliance automation | **P8 — Security/Compliance** | HIGH ~400 loc | MED | Depends on P5,P6 |

## Recommendation: P1 → P3 → P2 → P4 → P6 → P5 → P7 → P8

**Start now: P1 — Observability Layer**
- Lowest effort, zero risk, highest immediate value
- Uses existing `mid.py` hooks → zero-touch integration into every tool call
- 7,500 tokens of `tools/list` + wait times become measurable
- Ships in one session, fully testable
