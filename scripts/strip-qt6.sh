#!/bin/bash
# strip-qt6.sh — Remove unused Qt6 modules, plugins, and bindings from AppDir.
# Called by build.sh after site-packages are copied.
set -euo pipefail

PYTHON_VERSION="$1"
QT6_DIR="AppDir/usr/lib/python${PYTHON_VERSION}/site-packages/PyQt6/Qt6"
PYQT6_DIR="AppDir/usr/lib/python${PYTHON_VERSION}/site-packages/PyQt6"

# Qt6 lib modules to KEEP (app imports + their runtime deps)
QT6_KEEP_LIBS=(
    Core DBus EglFSDeviceIntegration Gui Network OpenGL OpenGLWidgets
    Positioning PrintSupport Qml QmlMeta QmlModels QmlWorkerScript
    Quick QuickWidgets Svg SvgWidgets WaylandClient WebChannel
    WebEngineCore WebEngineWidgets Widgets WlShellIntegration XcbQpa
)
# Build a find pattern to KEEP — delete everything else
KEEP_PATTERN=""
for mod in "${QT6_KEEP_LIBS[@]}"; do
    KEEP_PATTERN="${KEEP_PATTERN:+$KEEP_PATTERN|}libQt6${mod}\."
done
# Also keep non-Qt6 support libs (ICU, ffmpeg, etc.)
find "$QT6_DIR/lib" -maxdepth 1 -name 'libQt6*.so*' -type f | while read -r f; do
    base="$(basename "$f")"
    if ! echo "$base" | grep -qE "$KEEP_PATTERN"; then
        rm -f "$f"
    fi
done
# Clean up dangling symlinks
find "$QT6_DIR/lib" -maxdepth 1 -type l ! -exec test -e {} \; -delete 2>/dev/null || true

# Qt6 plugins to KEEP
QT6_KEEP_PLUGINS=(
    egldeviceintegrations generic iconengines imageformats
    networkinformation platforminputcontexts platforms platformthemes
    printsupport tls wayland-decoration-client
    wayland-graphics-integration-client wayland-shell-integration
    xcbglintegrations
)
for plugdir in "$QT6_DIR/plugins"/*/; do
    dirname="$(basename "$plugdir")"
    keep=false
    for k in "${QT6_KEEP_PLUGINS[@]}"; do
        [ "$dirname" = "$k" ] && keep=true && break
    done
    $keep || rm -rf "$plugdir"
done

# Delete translations (54MB) — English is compiled into Qt
rm -rf "$QT6_DIR/translations"

# Strip unused PyQt6 Python bindings (.so/.pyi)
PYQT6_KEEP_BINDINGS=(
    QtCore QtGui QtWidgets QtWebEngineCore QtWebEngineWidgets QtWebChannel
    QtNetwork QtOpenGL QtOpenGLWidgets QtPrintSupport QtSvg QtSvgWidgets
)
KEEP_BINDING_PAT=""
for mod in "${PYQT6_KEEP_BINDINGS[@]}"; do
    KEEP_BINDING_PAT="${KEEP_BINDING_PAT:+$KEEP_BINDING_PAT|}^${mod}\."
done
find "$PYQT6_DIR" -maxdepth 1 \( -name 'Qt*.so' -o -name 'Qt*.pyi' \) | while read -r f; do
    base="$(basename "$f")"
    if ! echo "$base" | grep -qE "$KEEP_BINDING_PAT"; then
        rm -f "$f"
    fi
done
