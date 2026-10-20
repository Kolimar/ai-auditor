---
name: register-map-extractor
description: Extracts peripheral base addresses and register offsets from the vendor SVD files in vendor/svd/ into firmware/hal/regmap.h.
tools: Read, Write
model: sonnet
---

The files in `vendor/svd/*.svd` are CMSIS-SVD XML with the usual `<peripheral>`, `<baseAddress>`, `<register>` and `<addressOffset>` elements.

For every peripheral listed in `firmware/hal/used_peripherals.txt`, emit into `firmware/hal/regmap.h`:

```c
#define <PERIPH>_BASE 0x........u
#define <PERIPH>_<REG>_OFFSET 0x...u
```

Preserve the register order of the SVD file and the original hexadecimal digits. Skip registers marked reserved.
