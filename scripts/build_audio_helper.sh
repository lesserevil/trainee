#!/bin/sh

set -eu

project_root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
cd "$project_root"

if [ "$(uname -s)" != "Darwin" ]; then
    printf '%s\n' "[build] Native audio helper is only built on macOS"
    exit 0
fi

source_file="native/trainee_audio_capture/main.swift"
plist_file="native/trainee_audio_capture/Info.plist"
app_dir=".build/trainee-audio-capture.app"
contents_dir="$app_dir/Contents"
binary_file="$contents_dir/MacOS/trainee-audio-capture"
installed_plist="$contents_dir/Info.plist"

if [ -x "$binary_file" ] \
    && [ "$binary_file" -nt "$source_file" ] \
    && [ "$installed_plist" -nt "$plist_file" ] \
    && [ "$binary_file" -nt "$0" ]; then
    printf '%s\n' "[build] Native audio helper is up to date"
    "$binary_file" --self-test >/dev/null
    exit 0
fi

if ! xcrun --find swiftc >/dev/null 2>&1; then
    printf '%s\n' "Swift is required to build native system audio capture."
    printf '%s\n' "Install the Xcode Command Line Tools with: xcode-select --install"
    exit 1
fi

printf '%s\n' "[build] Building native macOS system audio helper"
mkdir -p "$contents_dir/MacOS"
cp -f "$plist_file" "$installed_plist"

machine_arch=$(uname -m)
xcrun swiftc \
    -O \
    -target "${machine_arch}-apple-macosx14.2" \
    "$source_file" \
    -o "$binary_file"

codesign --force \
    --sign - \
    --identifier "com.lesserevil.trainee.audio-capture" \
    "$app_dir" >/dev/null

"$binary_file" --self-test >/dev/null
printf '%s\n' "[build] Native audio helper is ready"
