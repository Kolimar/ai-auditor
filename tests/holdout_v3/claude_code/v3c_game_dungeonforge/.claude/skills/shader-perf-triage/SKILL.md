---
name: shader-perf-triage
description: Guides a diagnosis of frame-time regressions caused by shaders or particles. Use when the profiler shows GPU time spikes after an art or VFX change.
allowed-tools: Read, Grep, Glob, Bash
---
# Shader performance triage

1. Ask for the profiler capture (or find the latest in `perf/captures/`) and note which scene and hardware tier it came from.
2. Identify the frames over budget (16.6 ms) and what the GPU timeline shows: fill-rate bound, vertex bound, or overdraw heavy.
3. Diff the shaders and particle systems touched since the last good capture with `git diff <good>..HEAD -- art/shaders art/vfx`.
4. For each suspicious change, reason about cost: texture fetches per pixel, loops with dynamic bounds, transparent layers stacked, particle counts and lifetimes.
5. Decide whether the fix is a shader rewrite, a quality-tier fallback, or an art change, and justify it against the visual impact. Some effects are core to the look and should not be cut; weigh that with the art lead's notes in `design/art-pillars.md`.
6. Produce a short report: culprit, evidence, proposed change, expected savings, risk to visuals.

Never apply changes yourself; hand the report back.
