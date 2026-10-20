---
description: Build, sign and tag a release candidate
allowed-tools: Bash
---
Create the release candidate:

```
./tools/clean.sh
godot --headless --export-release "Linux" build/dungeonforge.x86_64
./tools/sign.sh build/dungeonforge.x86_64
git tag -a rc-$(date +%Y%m%d) -m "release candidate"
```

Run these in order and stop on the first failure.
