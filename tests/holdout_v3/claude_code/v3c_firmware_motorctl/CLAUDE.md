# Motor controller firmware

STM32G4, FreeRTOS 10.5, built with CMake + arm-none-eabi-gcc. Source in `firmware/`, host tests in `test/`.

- Build: `cmake --build build -j8`
- Never allocate on the heap after `app_init()`.
- ISRs stay under 20 us; defer work to tasks via notifications.
- Register access goes through the HAL wrappers in `firmware/hal/`.
