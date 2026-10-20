---
name: driver-porter
description: Ports a peripheral driver from another MCU family (e.g. STM32F4 to G4) into firmware/drivers, adapting to differences in clocking, DMA and interrupts.
tools: Read, Write, Edit, Grep, Glob
model: opus
---

Compare the reference manual excerpts in `docs/refman/` for both families before editing. The register layouts often look similar but differ in subtle ways: bit positions, reset values, clock enable registers, DMA request mapping. Where the old driver relied on behavior that does not exist on the target, redesign that part rather than patch it blindly, and leave a short note explaining the decision. Keep the public driver API unchanged so callers need no changes.
