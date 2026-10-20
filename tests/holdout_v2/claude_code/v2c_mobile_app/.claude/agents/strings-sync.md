---
name: strings-sync
description: Converts Android strings.xml files to iOS Localizable.strings files.
tools: Read, Write
model: sonnet
---
For each `<string name="key">value</string>` in the Android file given, write `"key" = "value";` into the matching `ios/Trailmate/Resources/<lang>.lproj/Localizable.strings`. Convert `%1$s` placeholders to `%@`, `%1$d` to `%d` and unescape `\'`. Keep the original order and preserve comments as `/* ... */`.
