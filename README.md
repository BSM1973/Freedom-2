# Freedom 2 — Liberty

Plugin synthesizer project. GitHub Actions is prepared for building **macOS Apple Silicon AU, VST3 and Standalone**.

## Current status

The **build workflow is configured**, but the **C++ plugin source files are not in this repository yet**. No compiled plugin is available. The workflow is intentionally manual (`workflow_dispatch`) to reduce unnecessary usage.

The source archive `Freedom_2_UI_v8.8.zip` must be reviewed for permission to distribute its code publicly before uploading. Its native project directories are `plugin/` and `native/`. The HTML prototype `index.html` is not used to compile AU/VST3.

## Run when native sources are in place

1. Open **Actions** > **Freedom 2 — AU & VST3 (Apple Silicon)**.
2. Select **Run workflow**.
3. After success, download the **Freedom-2-macOS-ARM64** artifact.

The workflow uses a GitHub-hosted macOS runner; check GitHub Actions billing before running. The bundles are ad-hoc signed for testing, not notarized or commercially distributable installers. AU/VST3 operation in audio hosts still requires testing.

## License and publication

Public GitHub repositories expose their contents. Do not upload third-party proprietary source or material without permission. JUCE has its own license requirements.
