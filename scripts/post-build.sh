#!/usr/bin/env bash
# Post-build script to rename portable executable
# This script runs after `pnpm tauri build` completes

set -e

RELEASE_DIR="desktop/src-tauri/target/release"
SOURCE_EXE="$RELEASE_DIR/soundhunter.exe"
TARGET_EXE="$RELEASE_DIR/寻音殿.exe"

if [ -f "$SOURCE_EXE" ]; then
    echo "Renaming portable executable..."
    cp "$SOURCE_EXE" "$TARGET_EXE"
    echo "✓ Created: $TARGET_EXE"
else
    echo "⚠ Warning: $SOURCE_EXE not found"
    exit 1
fi
