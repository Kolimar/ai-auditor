---
name: flash-and-verify
description: Flash the current build to the bench board and verify it boots. Use when the user asks to flash, program or smoke test the board.
allowed-tools: Bash
---

# Flash and verify

1. `cmake --build build -j8`
2. `openocd -f board/openocd.cfg -c "program build/motorctl.elf verify reset exit"`
3. `python3 tools/read_boot_log.py --port /dev/ttyACM0 --timeout 10`
4. `python3 tools/check_boot_log.py boot.log`

Report the output of step 4.
