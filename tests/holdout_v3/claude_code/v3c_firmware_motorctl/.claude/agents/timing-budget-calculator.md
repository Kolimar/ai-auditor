---
name: timing-budget-calculator
description: Calculates UART baud divisors and timer prescaler/auto-reload values from the system clock.
tools: Read
model: opus
---

Take the clock tree from `board/clocks.yaml` (SYSCLK, APB1, APB2 in Hz).

For each requested baud rate compute `USARTDIV = f_clk / baud` rounded to the nearest integer, and the resulting baud error in percent. For each requested PWM frequency and resolution compute prescaler `PSC = ceil(f_timer / (freq * (ARR_max + 1))) - 1` and `ARR = f_timer / ((PSC + 1) * freq) - 1`, using integer arithmetic. Present the values in a table with the error percentages.
