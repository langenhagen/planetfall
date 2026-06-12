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

## 2026-03-14 12:08 +0100

- Discussed porting to C++/another engine: possible CPU gains, but not a
  guaranteed big FPS win without architectural changes; high rewrite cost.


## 2026-06-12 13:23 +0200

Some older notes and ideas discussed w/ Leo

- shield seed 2282025716
- gold seed  2662569245
- more scenes /  asteroid / coin patterns please and the patterns should be more distinctive, esp the coin patterns could be more creative in general.
- make some backdrop sprites as deep space objects (far away) that slowly pass by
  - (Explodierende) planeten?
  - nebulae
  - stars
  - planets
  - spacecraft
  - ...
- make some gigantic (3d) objects that sometimes pass by while falling they should be hundred's of meters long (or high) when passing, like a giant spaceship, or a giant asteroid
  - rakete oder riesen asteroid oder zerbrochener planet die manchmal neben mir vorbei fliegt
- convert/use panda3d preferred formats use the multify data format for bundling several assets together and reduce loading times?
- 15 Minuten erde hat man verloren erde im Hintergrund wird immer größer
- schwarzes loch das einen anziehen kann
- droiden oder Raumschiffe als gegner
- man kann schiessen, mit 2 pistolen
- gibt auch vielleicht freunde
- endgnegner riesen UFO
