#!/usr/bin/env python3
"""Exact 8054 MBOOT: strictly offline/non-invasive lookup of USB script and upgrade names.

Input: owner-hosted backup release ZIP. Reads ONLY mboot_a.img.
Emits allowlisted public U-Boot help/upgrade markers, never partition data,
keys, unique identifiers, or embedded command script payload.
Not evidence that USB script mode executes unsigned external text.
"""
import hashlib
import pathlib
import re
import sys
import zipfile

EXPECTED_SHA256 = "ebf9a0adef859f568d792d182f4ace08d026a27dc7f322bab735c67b07cd34c1"
EXPECTED_SIZE = 10_485_760

if len(sys.argv) != 2:
    raise SystemExit("Usage: audit_8054_usb_upgrade_script_hints.py <stock_backup.zip>")
src = pathlib.Path(sys.argv[1])
with zipfile.ZipFile(src) as z:
    entries = [
        e for e in z.infolist()
        if pathlib.PurePosixPath(e.filename.replace("\\", "/")).name == "mboot_a.img"
        and not e.is_dir()
    ]
    if len(entries) != 1 or entries[0].file_size != EXPECTED_SIZE:
        raise ValueError("Unexpected exact 8054 mboot image")
    blob = z.read(entries[0])
assert hashlib.sha256(blob).hexdigest() == EXPECTED_SHA256, "MBOOT SHA mismatch"
print("EXACT OWNER 8054 MBOOT SHA VERIFIED:", EXPECTED_SHA256)

print("\n# Static literal occurrence counts (not proof of executed branches)")
tokens = [
    b"mtkupgrade usb -script", b"mtkupgrade usb", b"check_usb_auto_upgrade",
    b"usb_auto_upgrade", b"MTKUpgrade.bin", b"upgrade_image.pkg",
    b"fastboot udp", b"Listening for fastboot command on", b"avb set-devicestate",
    b"devicestate", b"scriptstar", b"auto_update.txt", b"factory.txt",
    b"MScript.txt", b"usb_upgrade.txt", b"auto_upgrade.txt",
]
low = blob.lower()
for t in tokens:
    print(f"{t.decode('ascii')}: {low.count(t.lower())}")

print("\n# Selected exact U-Boot help/command literals (sanitized)")
target = re.compile(
    r"mtkupgrade|check_usb_auto_upgrade|usb_auto_upgrade|"
    r"PKG format default file name|MstarUpgrade|MTKUpgrade|"
    r"fastboot udp|Listening for fastboot command|avb set-devicestate|"
    r"scriptstar|\.txt\b", re.I
)
redact = re.compile(
    r"macaddr|serialno|password|private|secret|keybox|"
    r"hdcp|widevine|certificate|device[_-]?id|token|"
    r"[0-9a-f]{2}(?::[0-9a-f]{2}){5}", re.I
)
seen = set()
for mat in re.finditer(rb"[\x20-\x7e]{5,190}", blob):
    candidate = mat.group(0).decode("ascii", errors="replace").strip()
    if not target.search(candidate) or redact.search(candidate):
        continue
    # Never print arbitrary long scripts, shell-side partition writes, or memory dumps.
    if len(candidate) > 170 or any(
        t in candidate.lower() for t in
        ["gpt clean", "mmc erase", "partition write", "setenv ", "aes-256", "rsa4096"]
    ):
        continue
    if candidate in seen:
        continue
    seen.add(candidate)
    print(f"0x{mat.start():08x} {candidate}")
    if len(seen) >= 70:
        print("[TRUNCATED: 70 unique safe strings]")
        break
print("\nStatic string-only evidence. No firmware writes or code execution performed.")
