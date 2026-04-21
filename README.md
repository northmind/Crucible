# Crucible

Crucible is a Linux launcher for Windows games built around UMU and Proton.

## Features

- Drag and drop `.exe` files to add games
- Per-game launch settings, wrappers, environment variables, and DLL overrides
- Proton-GE download and management
- Bundled web-based UI inside a native desktop shell
- Steam artwork lookup and desktop shortcut support

## Download

Download the latest `Crucible-x86_64.AppImage` from [Releases](https://github.com/northmind/Crucible/releases).

```bash
chmod +x Crucible-x86_64.AppImage
./Crucible-x86_64.AppImage
```

Verify the release artifact:

```bash
sha256sum -c SHA256SUMS
```

## Releases

GitHub Actions builds the AppImage on version tag pushes matching `v*` and attaches the AppImage plus `SHA256SUMS` to the GitHub release.

## Local Builds

Local builds are self-managed and unsupported.

If you want to build locally, create a `.venv`, install `requirements.txt`, install the external build tools required by `build.sh`, and then run:

```bash
./build.sh
```

You can manage that local environment with Devbox, Nix, or anything else. Those local environment files are intentionally not part of this repository.

## Copyright

Copyright (c) 2026 .nakama. All rights reserved. No license is granted.
