---
description: Convert measurements between units in a data file
argument-hint: <csv path> <column> <from unit> <to unit>
---
In the CSV given, take the column named in `$ARGUMENTS`, convert every value from the source unit to the target unit (for example mg/kg to ug/g, or degrees Fahrenheit to Celsius), and write the result to a new column `<column>_converted`. Show the first five converted rows.
