# Driver notes (firmware/drivers)

Read this before editing anything in this directory.

## ADC1

The ADC1 driver is initialised from `board_init()` in a fixed order; see `drivers/adc1.c`. Clock gating for ADC1 must be enabled before any register write, otherwise the write is silently ignored on this silicon revision (errata ES0430 section 2.4). Interrupt priority for ADC1 is set in `irq_priorities.h` and must stay numerically above the FreeRTOS max syscall priority when the handler calls `FromISR` APIs.
DMA channels used by ADC1 are assigned in `dma_map.h`; do not reuse them for other peripherals without updating the request multiplexer settings.

## ADC2

The ADC2 driver is initialised from `board_init()` in a fixed order; see `drivers/adc2.c`. Clock gating for ADC2 must be enabled before any register write, otherwise the write is silently ignored on this silicon revision (errata ES0430 section 2.4). Interrupt priority for ADC2 is set in `irq_priorities.h` and must stay numerically above the FreeRTOS max syscall priority when the handler calls `FromISR` APIs.
DMA channels used by ADC2 are assigned in `dma_map.h`; do not reuse them for other peripherals without updating the request multiplexer settings.

## DAC1

The DAC1 driver is initialised from `board_init()` in a fixed order; see `drivers/dac1.c`. Clock gating for DAC1 must be enabled before any register write, otherwise the write is silently ignored on this silicon revision (errata ES0430 section 2.4). Interrupt priority for DAC1 is set in `irq_priorities.h` and must stay numerically above the FreeRTOS max syscall priority when the handler calls `FromISR` APIs.
DMA channels used by DAC1 are assigned in `dma_map.h`; do not reuse them for other peripherals without updating the request multiplexer settings.

## TIM1

The TIM1 driver is initialised from `board_init()` in a fixed order; see `drivers/tim1.c`. Clock gating for TIM1 must be enabled before any register write, otherwise the write is silently ignored on this silicon revision (errata ES0430 section 2.4). Interrupt priority for TIM1 is set in `irq_priorities.h` and must stay numerically above the FreeRTOS max syscall priority when the handler calls `FromISR` APIs.
DMA channels used by TIM1 are assigned in `dma_map.h`; do not reuse them for other peripherals without updating the request multiplexer settings.

## TIM2

The TIM2 driver is initialised from `board_init()` in a fixed order; see `drivers/tim2.c`. Clock gating for TIM2 must be enabled before any register write, otherwise the write is silently ignored on this silicon revision (errata ES0430 section 2.4). Interrupt priority for TIM2 is set in `irq_priorities.h` and must stay numerically above the FreeRTOS max syscall priority when the handler calls `FromISR` APIs.
DMA channels used by TIM2 are assigned in `dma_map.h`; do not reuse them for other peripherals without updating the request multiplexer settings.

## TIM3

The TIM3 driver is initialised from `board_init()` in a fixed order; see `drivers/tim3.c`. Clock gating for TIM3 must be enabled before any register write, otherwise the write is silently ignored on this silicon revision (errata ES0430 section 2.4). Interrupt priority for TIM3 is set in `irq_priorities.h` and must stay numerically above the FreeRTOS max syscall priority when the handler calls `FromISR` APIs.
DMA channels used by TIM3 are assigned in `dma_map.h`; do not reuse them for other peripherals without updating the request multiplexer settings.

## TIM8

The TIM8 driver is initialised from `board_init()` in a fixed order; see `drivers/tim8.c`. Clock gating for TIM8 must be enabled before any register write, otherwise the write is silently ignored on this silicon revision (errata ES0430 section 2.4). Interrupt priority for TIM8 is set in `irq_priorities.h` and must stay numerically above the FreeRTOS max syscall priority when the handler calls `FromISR` APIs.
DMA channels used by TIM8 are assigned in `dma_map.h`; do not reuse them for other peripherals without updating the request multiplexer settings.

## TIM15

The TIM15 driver is initialised from `board_init()` in a fixed order; see `drivers/tim15.c`. Clock gating for TIM15 must be enabled before any register write, otherwise the write is silently ignored on this silicon revision (errata ES0430 section 2.5). Interrupt priority for TIM15 is set in `irq_priorities.h` and must stay numerically above the FreeRTOS max syscall priority when the handler calls `FromISR` APIs.
DMA channels used by TIM15 are assigned in `dma_map.h`; do not reuse them for other peripherals without updating the request multiplexer settings.

## USART1

The USART1 driver is initialised from `board_init()` in a fixed order; see `drivers/usart1.c`. Clock gating for USART1 must be enabled before any register write, otherwise the write is silently ignored on this silicon revision (errata ES0430 section 2.6). Interrupt priority for USART1 is set in `irq_priorities.h` and must stay numerically above the FreeRTOS max syscall priority when the handler calls `FromISR` APIs.
DMA channels used by USART1 are assigned in `dma_map.h`; do not reuse them for other peripherals without updating the request multiplexer settings.

## USART2

The USART2 driver is initialised from `board_init()` in a fixed order; see `drivers/usart2.c`. Clock gating for USART2 must be enabled before any register write, otherwise the write is silently ignored on this silicon revision (errata ES0430 section 2.6). Interrupt priority for USART2 is set in `irq_priorities.h` and must stay numerically above the FreeRTOS max syscall priority when the handler calls `FromISR` APIs.
DMA channels used by USART2 are assigned in `dma_map.h`; do not reuse them for other peripherals without updating the request multiplexer settings.

## LPUART1

The LPUART1 driver is initialised from `board_init()` in a fixed order; see `drivers/lpuart1.c`. Clock gating for LPUART1 must be enabled before any register write, otherwise the write is silently ignored on this silicon revision (errata ES0430 section 2.7). Interrupt priority for LPUART1 is set in `irq_priorities.h` and must stay numerically above the FreeRTOS max syscall priority when the handler calls `FromISR` APIs.
DMA channels used by LPUART1 are assigned in `dma_map.h`; do not reuse them for other peripherals without updating the request multiplexer settings.

## SPI1

The SPI1 driver is initialised from `board_init()` in a fixed order; see `drivers/spi1.c`. Clock gating for SPI1 must be enabled before any register write, otherwise the write is silently ignored on this silicon revision (errata ES0430 section 2.4). Interrupt priority for SPI1 is set in `irq_priorities.h` and must stay numerically above the FreeRTOS max syscall priority when the handler calls `FromISR` APIs.
DMA channels used by SPI1 are assigned in `dma_map.h`; do not reuse them for other peripherals without updating the request multiplexer settings.

## SPI2

The SPI2 driver is initialised from `board_init()` in a fixed order; see `drivers/spi2.c`. Clock gating for SPI2 must be enabled before any register write, otherwise the write is silently ignored on this silicon revision (errata ES0430 section 2.4). Interrupt priority for SPI2 is set in `irq_priorities.h` and must stay numerically above the FreeRTOS max syscall priority when the handler calls `FromISR` APIs.
DMA channels used by SPI2 are assigned in `dma_map.h`; do not reuse them for other peripherals without updating the request multiplexer settings.

## I2C1

The I2C1 driver is initialised from `board_init()` in a fixed order; see `drivers/i2c1.c`. Clock gating for I2C1 must be enabled before any register write, otherwise the write is silently ignored on this silicon revision (errata ES0430 section 2.4). Interrupt priority for I2C1 is set in `irq_priorities.h` and must stay numerically above the FreeRTOS max syscall priority when the handler calls `FromISR` APIs.
DMA channels used by I2C1 are assigned in `dma_map.h`; do not reuse them for other peripherals without updating the request multiplexer settings.

## I2C2

The I2C2 driver is initialised from `board_init()` in a fixed order; see `drivers/i2c2.c`. Clock gating for I2C2 must be enabled before any register write, otherwise the write is silently ignored on this silicon revision (errata ES0430 section 2.4). Interrupt priority for I2C2 is set in `irq_priorities.h` and must stay numerically above the FreeRTOS max syscall priority when the handler calls `FromISR` APIs.
DMA channels used by I2C2 are assigned in `dma_map.h`; do not reuse them for other peripherals without updating the request multiplexer settings.

## FDCAN1

The FDCAN1 driver is initialised from `board_init()` in a fixed order; see `drivers/fdcan1.c`. Clock gating for FDCAN1 must be enabled before any register write, otherwise the write is silently ignored on this silicon revision (errata ES0430 section 2.6). Interrupt priority for FDCAN1 is set in `irq_priorities.h` and must stay numerically above the FreeRTOS max syscall priority when the handler calls `FromISR` APIs.
DMA channels used by FDCAN1 are assigned in `dma_map.h`; do not reuse them for other peripherals without updating the request multiplexer settings.

## DMA1

The DMA1 driver is initialised from `board_init()` in a fixed order; see `drivers/dma1.c`. Clock gating for DMA1 must be enabled before any register write, otherwise the write is silently ignored on this silicon revision (errata ES0430 section 2.4). Interrupt priority for DMA1 is set in `irq_priorities.h` and must stay numerically above the FreeRTOS max syscall priority when the handler calls `FromISR` APIs.
DMA channels used by DMA1 are assigned in `dma_map.h`; do not reuse them for other peripherals without updating the request multiplexer settings.

## DMA2

The DMA2 driver is initialised from `board_init()` in a fixed order; see `drivers/dma2.c`. Clock gating for DMA2 must be enabled before any register write, otherwise the write is silently ignored on this silicon revision (errata ES0430 section 2.4). Interrupt priority for DMA2 is set in `irq_priorities.h` and must stay numerically above the FreeRTOS max syscall priority when the handler calls `FromISR` APIs.
DMA channels used by DMA2 are assigned in `dma_map.h`; do not reuse them for other peripherals without updating the request multiplexer settings.

## CRC

The CRC driver is initialised from `board_init()` in a fixed order; see `drivers/crc.c`. Clock gating for CRC must be enabled before any register write, otherwise the write is silently ignored on this silicon revision (errata ES0430 section 2.3). Interrupt priority for CRC is set in `irq_priorities.h` and must stay numerically above the FreeRTOS max syscall priority when the handler calls `FromISR` APIs.
DMA channels used by CRC are assigned in `dma_map.h`; do not reuse them for other peripherals without updating the request multiplexer settings.

## RNG

The RNG driver is initialised from `board_init()` in a fixed order; see `drivers/rng.c`. Clock gating for RNG must be enabled before any register write, otherwise the write is silently ignored on this silicon revision (errata ES0430 section 2.3). Interrupt priority for RNG is set in `irq_priorities.h` and must stay numerically above the FreeRTOS max syscall priority when the handler calls `FromISR` APIs.
DMA channels used by RNG are assigned in `dma_map.h`; do not reuse them for other peripherals without updating the request multiplexer settings.

## COMP1

The COMP1 driver is initialised from `board_init()` in a fixed order; see `drivers/comp1.c`. Clock gating for COMP1 must be enabled before any register write, otherwise the write is silently ignored on this silicon revision (errata ES0430 section 2.5). Interrupt priority for COMP1 is set in `irq_priorities.h` and must stay numerically above the FreeRTOS max syscall priority when the handler calls `FromISR` APIs.
DMA channels used by COMP1 are assigned in `dma_map.h`; do not reuse them for other peripherals without updating the request multiplexer settings.

## OPAMP1

The OPAMP1 driver is initialised from `board_init()` in a fixed order; see `drivers/opamp1.c`. Clock gating for OPAMP1 must be enabled before any register write, otherwise the write is silently ignored on this silicon revision (errata ES0430 section 2.6). Interrupt priority for OPAMP1 is set in `irq_priorities.h` and must stay numerically above the FreeRTOS max syscall priority when the handler calls `FromISR` APIs.
DMA channels used by OPAMP1 are assigned in `dma_map.h`; do not reuse them for other peripherals without updating the request multiplexer settings.

## CORDIC

The CORDIC driver is initialised from `board_init()` in a fixed order; see `drivers/cordic.c`. Clock gating for CORDIC must be enabled before any register write, otherwise the write is silently ignored on this silicon revision (errata ES0430 section 2.6). Interrupt priority for CORDIC is set in `irq_priorities.h` and must stay numerically above the FreeRTOS max syscall priority when the handler calls `FromISR` APIs.
DMA channels used by CORDIC are assigned in `dma_map.h`; do not reuse them for other peripherals without updating the request multiplexer settings.

## FMAC

The FMAC driver is initialised from `board_init()` in a fixed order; see `drivers/fmac.c`. Clock gating for FMAC must be enabled before any register write, otherwise the write is silently ignored on this silicon revision (errata ES0430 section 2.4). Interrupt priority for FMAC is set in `irq_priorities.h` and must stay numerically above the FreeRTOS max syscall priority when the handler calls `FromISR` APIs.
DMA channels used by FMAC are assigned in `dma_map.h`; do not reuse them for other peripherals without updating the request multiplexer settings.
