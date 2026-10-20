---
name: version-bumper
description: Bumps the app version and build number in both platforms.
tools: Read, Edit
model: opus
---
Given the new version X.Y.Z, set `CFBundleShortVersionString` to X.Y.Z and increment `CFBundleVersion` by one in `ios/Trailmate/Info.plist`, and set `versionName` to X.Y.Z and increment `versionCode` by one in `android/app/build.gradle.kts`.
