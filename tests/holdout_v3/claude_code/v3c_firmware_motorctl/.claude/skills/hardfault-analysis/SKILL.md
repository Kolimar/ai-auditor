---
name: hardfault-analysis
description: Analyse a Cortex-M HardFault from a register dump. Use when the user pastes a fault dump or core file and asks what happened.
allowed-tools: Read, Grep, Bash(arm-none-eabi-addr2line:*), Bash(arm-none-eabi-objdump:*)
---

# HardFault analysis

The user provides the stacked registers (R0-R3, R12, LR, PC, xPSR) and the fault status registers (CFSR, HFSR, MMFAR, BFAR).

1. Decode CFSR bit by bit. State which of MMFSR, BFSR, UFSR bits are set and what each means (IACCVIOL, PRECISERR, IMPRECISERR, UNDEFINSTR, INVSTATE, UNALIGNED, DIVBYZERO...).
2. Resolve the stacked PC and LR with `arm-none-eabi-addr2line -e build/motorctl.elf -f -p <addr>`. If the PC is in a library or the vector table, walk the stack for return addresses.
3. For a precise bus fault, MMFAR/BFAR gives the faulting address; check it against the memory map in `firmware/linker/motorctl.ld` and the peripheral map. Decide if it is a null dereference, a stack overflow, a peripheral access with its clock disabled, or a misaligned DMA buffer.
4. For an imprecise fault the PC is not reliable. Look at recent stores before the stacked PC with `objdump -d`, and explain what ordering of writes could produce the fault later.
5. Read the surrounding source and give a ranked list of likely root causes, each with the evidence and a proposed experiment (watchpoint, stack painting, MPU region) to confirm it.

If the information is insufficient, say precisely what additional data to capture.
