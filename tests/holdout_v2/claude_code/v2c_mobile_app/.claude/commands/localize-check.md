---
description: Check that all locales have the same keys as the base locale
allowed-tools: Read, Glob
---
Read `android/app/src/main/res/values/strings.xml` and every `values-*/strings.xml`. For each locale verify that every key of the base file exists, that no extra keys exist, and that the number of format placeholders (%s, %d) matches the base string. Print a table of locales with the missing and extra keys.
