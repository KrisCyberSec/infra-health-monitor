# Sample Daily Health Report

**Date:** 2026-10-31  
**Host:** lab-server-01  
**Overall status:** Degraded

## Summary
- 3 checks performed
- 1 anomaly detected (high disk)
- No service failures
- Failed logins: within normal range

## Metrics Trend
| Check | CPU | Memory | Disk | Notes |
|-------|-----|--------|------|-------|
| Morning | 22% | 48% | 61% | Normal |
| Afternoon | 31% | 55% | 94% | Disk anomaly |
| Evening | 18% | 41% | 93% | Disk still high |

**Recommendation:** Address disk usage before it reaches 100%.
