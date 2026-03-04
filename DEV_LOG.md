# Dev Log

Short, chronological notes about experiments, changes tried, outcomes, and
decisions. Append newest entries at the end.

## 2026-03-04 12:19 +0100

- Added perf logging hooks and FPS gauge to profile `animate`/`collisions`.
- Reused coin/obstacle batch scratch buffers; minor improvement, still dominated
  by batch work.
- Removed obstacle sphere/icosphere guard (asteroids only).
- Tried auto-yaw coin-road caching; no clear perf improvement. User reverted.
- Tried precomputed coin motion flags (store per-coin booleans at spawn for
  wave/orbit/slalom/bob/pulse so per-frame updates do not recompute masks).
  No clear perf improvement. User reverted.

## 2026-03-04 13:28 +0100

- Asteroid scene-graph instancing (Panda3D `instanceTo`) reduced observed FPS
  dips in Ursina's on-screen counter. Keeping enabled.

## 2026-03-04 15:34 +0100

- Tried coin instancing. No clear perf win in runs and coins rendered white
  (per-entity color not preserved). Reverted.
