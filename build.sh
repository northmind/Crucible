#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# --- Resolve project venv Python ---
if [ ! -x .venv/bin/python3 ]; then
    echo "ERROR: .venv/bin/python3 not found."
    echo "  Create a virtualenv, install requirements.txt, then run ./build.sh"
    exit 1
fi

for tool in wget patchelf file strip ldd sha256sum; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "ERROR: required tool '$tool' not found on PATH."
        exit 1
    fi
done

VENV_PYTHON="$(readlink -f .venv/bin/python3)"
PYTHON_VERSION="$("$VENV_PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
PYTHON_PREFIX="$("$VENV_PYTHON" -c 'import sys; print(sys.base_prefix)')"
SITE_PACKAGES="$("$VENV_PYTHON" -c 'import site; print(site.getsitepackages()[0])')"

echo "Python:        $VENV_PYTHON"
echo "Prefix:        $PYTHON_PREFIX"
echo "Version:       $PYTHON_VERSION"
echo "Site-packages: $SITE_PACKAGES"

if [ ! -d "$SITE_PACKAGES/PyQt6" ]; then
    echo "ERROR: PyQt6 not found in venv site-packages."
    echo "  Install dependencies from requirements.txt into .venv first"
    exit 1
fi

# --- Download appimagetool ---
APPIMAGETOOL="$SCRIPT_DIR/appimagetool-x86_64.AppImage"
APPIMAGETOOL_URL="https://github.com/AppImage/appimagetool/releases/download/1.9.1/appimagetool-x86_64.AppImage"
APPIMAGETOOL_SHA256="ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0"
if [ ! -f "$APPIMAGETOOL" ]; then
    echo "Downloading appimagetool..."
    wget -q "$APPIMAGETOOL_URL" \
        -O "$APPIMAGETOOL"
    chmod +x "$APPIMAGETOOL"
fi
echo "$APPIMAGETOOL_SHA256  $APPIMAGETOOL" | sha256sum -c -

# --- Set up AppDir ---
echo "Setting up AppDir..."
rm -rf AppDir
mkdir -p AppDir/usr/bin AppDir/usr/lib AppDir/usr/share/crucible

# --- Copy and patch Python binary ---
echo "Bundling Python ${PYTHON_VERSION}..."
cp "$VENV_PYTHON" AppDir/usr/bin/python3
chmod u+wx AppDir/usr/bin/python3
patchelf --set-interpreter /lib64/ld-linux-x86-64.so.2 AppDir/usr/bin/python3
patchelf --set-rpath '$ORIGIN/../lib' AppDir/usr/bin/python3
echo "  patched interpreter and rpath"

# --- Bundle Python's shared library dependencies ---
echo "Bundling Python native deps..."

# Collect all Nix .so deps (skip glibc, gcc_s, system libs the host provides)
_bundle_nix_deps() {
    local binary="$1"
    local deps
    deps="$(ldd "$binary" 2>/dev/null | grep "/nix/store/" | awk '{print $3}' || true)"
    [ -z "$deps" ] && return 0
    local lib base
    for lib in $deps; do
        [ -z "$lib" ] || [ ! -f "$lib" ] && continue
        base="$(basename "$lib")"
        # Skip glibc/gcc — host provides these
        case "$base" in
            libc.so*|libm.so*|libpthread.so*|libdl.so*|librt.so*|\
            ld-linux*.so*|libresolv.so*|libnss*.so*|libutil.so*|libcrypt.so*)
                continue ;;
        esac
        if [ ! -f "AppDir/usr/lib/$base" ]; then
            cp "$lib" "AppDir/usr/lib/$base"
            chmod u+w "AppDir/usr/lib/$base"
            echo "  bundled $base"
        fi
    done
}

_bundle_nix_deps "$VENV_PYTHON"

# Also bundle libpython with proper symlinks
LIBPYTHON="$(ldd "$VENV_PYTHON" 2>/dev/null | awk '/libpython[0-9.]+\.so/{print $3; exit}')"
if [ -z "$LIBPYTHON" ] || [ ! -f "$LIBPYTHON" ]; then
    for candidate in \
        "$PYTHON_PREFIX/lib/libpython${PYTHON_VERSION}.so.1.0" \
        "$PYTHON_PREFIX/lib/libpython${PYTHON_VERSION}.so" \
        "$PYTHON_PREFIX/lib/x86_64-linux-gnu/libpython${PYTHON_VERSION}.so.1.0" \
        "$PYTHON_PREFIX/lib/x86_64-linux-gnu/libpython${PYTHON_VERSION}.so"; do
        if [ -f "$candidate" ]; then
            LIBPYTHON="$(readlink -f "$candidate")"
            break
        fi
    done
fi
if [ -f "$LIBPYTHON" ]; then
    cp "$LIBPYTHON" "AppDir/usr/lib/libpython${PYTHON_VERSION}.so.1.0"
    chmod u+w "AppDir/usr/lib/libpython${PYTHON_VERSION}.so.1.0"
    ln -sf "libpython${PYTHON_VERSION}.so.1.0" "AppDir/usr/lib/libpython${PYTHON_VERSION}.so"
    ln -sf "libpython${PYTHON_VERSION}.so.1.0" "AppDir/usr/lib/libpython3.so"
    echo "  bundled libpython${PYTHON_VERSION}.so.1.0 (+ symlinks)"
    # Bundle libpython's own Nix deps too
    _bundle_nix_deps "$LIBPYTHON"
else
    echo "ERROR: libpython${PYTHON_VERSION} shared library not found"
    exit 1
fi

# --- Copy Python stdlib ---
echo "Copying Python stdlib..."
STDLIB_SRC="$PYTHON_PREFIX/lib/python${PYTHON_VERSION}"
cp -rL "$STDLIB_SRC" "AppDir/usr/lib/python${PYTHON_VERSION}"

# Fix Nix store read-only permissions
chmod -R u+w "AppDir/usr/lib/python${PYTHON_VERSION}"

# Remove stdlib bloat (tests, tkinter, idle, turtle)
rm -rf "AppDir/usr/lib/python${PYTHON_VERSION}/test" \
       "AppDir/usr/lib/python${PYTHON_VERSION}/tests" \
       "AppDir/usr/lib/python${PYTHON_VERSION}/ensurepip" \
       "AppDir/usr/lib/python${PYTHON_VERSION}/idlelib" \
       "AppDir/usr/lib/python${PYTHON_VERSION}/tkinter" \
       "AppDir/usr/lib/python${PYTHON_VERSION}/turtle"*.py \
       "AppDir/usr/lib/python${PYTHON_VERSION}/turtledemo"

# --- Copy site-packages (excluding dev-only packages) ---
echo "Copying site-packages..."
rm -rf "AppDir/usr/lib/python${PYTHON_VERSION}/site-packages"

# Dev-only packages to exclude from the AppImage
EXCLUDE_PKGS=(
    mypy mypyc pip setuptools _distutils_hack distutils pkg_resources
    pygments pytest _pytest coverage black blib2to3 blackd pathspec
    platformdirs click iniconfig pluggy tomli exceptiongroup nodeenv
    virtualenv filelock pre_commit cfgv identify
)

cp -rL "$SITE_PACKAGES" "AppDir/usr/lib/python${PYTHON_VERSION}/site-packages"

# Fix Nix store read-only permissions on site-packages
chmod -R u+w "AppDir/usr/lib/python${PYTHON_VERSION}/site-packages"

# Remove dev-only packages
SP_DIR="AppDir/usr/lib/python${PYTHON_VERSION}/site-packages"
for pkg in "${EXCLUDE_PKGS[@]}"; do
    rm -rf "$SP_DIR/$pkg" "$SP_DIR/${pkg//-/_}"*.dist-info 2>/dev/null || true
done

# --- Strip unused Qt6 modules ---
echo "Stripping unused Qt6 modules..."
"$SCRIPT_DIR/scripts/strip-qt6.sh" "$PYTHON_VERSION"

# --- Strip debug symbols from all bundled .so files ---
echo "Stripping debug symbols..."
find AppDir/usr/lib -name '*.so*' -type f -exec strip --strip-unneeded {} + 2>/dev/null || true

# Strip __pycache__ and .pyc to save space
find AppDir/usr/lib -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# --- Patch RPATHs and bundle Nix deps for all .so files in AppDir ---
echo "Patching .so RPATHs and bundling native deps..."
while IFS= read -r sofile; do
    # Skip symlinks (already handled by the real file)
    [ -L "$sofile" ] && continue
    # Only process ELF files
    file "$sofile" 2>/dev/null | grep -q "ELF" || continue

    # Bundle any Nix deps this .so needs (BEFORE patching RPATH so ldd resolves)
    _bundle_nix_deps "$sofile" || true

    # Patch RPATH if it points to Nix store
    current_rpath="$(patchelf --print-rpath "$sofile" 2>/dev/null || true)"
    if echo "$current_rpath" | grep -q "/nix/store/"; then
        chmod u+w "$sofile" 2>/dev/null || true
        patchelf --remove-rpath "$sofile" 2>/dev/null || true
    fi
done < <(find AppDir/usr/lib -name '*.so*' -type f 2>/dev/null)
echo "  processed .so files in AppDir"

# --- Copy crucible source ---
cp -r python/crucible AppDir/usr/share/crucible/crucible

# --- Bundle icoutils ---
echo "Bundling icoutils..."
for tool in wrestool icotool; do
    bin=$(which "$tool" 2>/dev/null || true)
    if [ -n "$bin" ]; then
        cp "$bin" AppDir/usr/bin/
        ldd "$bin" 2>/dev/null | grep "=>" | awk '{print $3}' | while read -r lib; do
            [ -z "$lib" ] && continue
            basename="$(basename "$lib")"
            case "$basename" in
                libc.so*|libm.so*|libpthread.so*|libdl.so*|librt.so*|\
                libgcc_s.so*|libstdc++.so*|ld-linux*.so*|libz.so*|\
                libresolv.so*|libnss*.so*|libutil.so*|libcrypt.so*)
                    continue ;;
            esac
            [ -f "$lib" ] && cp --no-clobber "$lib" AppDir/usr/bin/ 2>/dev/null || true
        done
        echo "  bundled $tool"
    else
        echo "  WARNING: $tool not found on PATH"
    fi
done

# --- Convert icon ---
echo "Converting icon..."
"$VENV_PYTHON" -c "
from PIL import Image
img = Image.open('python/crucible/assets/images/icon.jpg').convert('RGBA')
img = img.resize((256, 256), Image.LANCZOS)
img.save('AppDir/crucible.png')
"

# --- Generate .desktop file ---
cat > AppDir/crucible.desktop << 'DESKTOP'
[Desktop Entry]
Type=Application
Name=Crucible
Exec=crucible
Icon=crucible
Categories=Game;
Comment=Linux Game Launcher
DESKTOP

# --- Generate AppRun ---
QT6_LIB="usr/lib/python${PYTHON_VERSION}/site-packages/PyQt6/Qt6/lib"
QT6_PLUGINS="usr/lib/python${PYTHON_VERSION}/site-packages/PyQt6/Qt6/plugins"
PILLOW_LIBS="usr/lib/python${PYTHON_VERSION}/site-packages/pillow.libs"

cat > AppDir/AppRun << APPRUN
#!/bin/bash
HERE="\$(dirname "\$(readlink -f "\$0")")"

# Save the user's original environment BEFORE we overwrite with AppImage paths.
# Crucible restores these when launching child processes (games, umu-run) so
# they don't inherit our bundled Python/Qt/library paths.
export CRUCIBLE_ORIG_LD_LIBRARY_PATH="\${LD_LIBRARY_PATH:-}"
export CRUCIBLE_ORIG_PYTHONHOME="\${PYTHONHOME:-}"
export CRUCIBLE_ORIG_PYTHONPATH="\${PYTHONPATH:-}"
export CRUCIBLE_ORIG_QT_PLUGIN_PATH="\${QT_PLUGIN_PATH:-}"
export CRUCIBLE_ORIG_PATH="\${PATH:-}"

export PYTHONHOME="\$HERE/usr"
export PYTHONPATH="\$HERE/usr/share/crucible:\$HERE/usr/lib/python${PYTHON_VERSION}/site-packages"
export LD_LIBRARY_PATH="\$HERE/usr/lib:\$HERE/${QT6_LIB}:\$HERE/${PILLOW_LIBS}\${LD_LIBRARY_PATH:+:\$LD_LIBRARY_PATH}"
export QT_PLUGIN_PATH="\$HERE/${QT6_PLUGINS}"
export PATH="\$HERE/usr/bin:\${PATH}"
exec "\$HERE/usr/bin/python3" -m crucible "\$@"
APPRUN
chmod +x AppDir/AppRun

# --- Build AppImage ---
echo "Building AppImage..."
rm -f Crucible-x86_64.AppImage
ARCH=x86_64 "$APPIMAGETOOL" --appimage-extract-and-run AppDir Crucible-x86_64.AppImage

echo ""
echo "Done: Crucible-x86_64.AppImage"
echo "Size: $(du -h Crucible-x86_64.AppImage | cut -f1)"
