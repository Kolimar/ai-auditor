---
name: ship-testflight
description: Upload the current build to TestFlight.
allowed-tools: Bash
---
Steps:
1. `cd ios && bundle exec fastlane match appstore --readonly`
2. `bundle exec fastlane gym --scheme Trailmate`
3. `bundle exec fastlane pilot upload --skip_waiting_for_build_processing`
4. `git tag testflight-$(date +%Y%m%d%H%M)`
5. `git push --tags`
