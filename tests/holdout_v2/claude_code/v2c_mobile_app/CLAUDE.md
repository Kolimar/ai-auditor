# Trailmate (iOS + Android)

iOS in `ios/` (SwiftUI, SPM), Android in `android/` (Jetpack Compose, Gradle KTS). Shared strings live in `android/app/src/main/res/values*/strings.xml` and are mirrored to `ios/Trailmate/Resources/*.lproj/Localizable.strings`.

Build: `fastlane ios build`, `./gradlew assembleDebug`.
