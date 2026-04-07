# Crucible

A game launcher for running Windows games on Linux using [UMU](https://github.com/Open-Wine-Components/umu-launcher) and [Proton](https://github.com/GloriousEggroll/proton-ge-custom).

## Features

- Drag and drop `.exe` files to add games
- Per-game configuration: executable, install directory, Wine prefix, launch arguments, DLL overrides, wrapper commands, and environment variables
- Download and manage Proton-GE versions
- Launch and stop games from a library view
- Desktop shortcuts with artwork
- Automatic Steam artwork fetching
- Winetricks integration
- Theming with custom colors
- Per-game log viewer

## Install

Download the latest AppImage from [Releases](https://github.com/northmind/Crucible/releases).

```bash
chmod +x Crucible-x86_64.AppImage
./Crucible-x86_64.AppImage
```

Verify the download:
```bash
sha256sum -c SHA256SUMS
```

## Copyright

Copyright (c) 2026 .nakama. -- All Rights Reserved. No license is granted.
