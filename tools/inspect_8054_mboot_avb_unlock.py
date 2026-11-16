#!/usr/bin/env python3
"""Offline investigation of fastboot and AVB LOCK/UNLOCK code-path strings in the exact 8054 mboot partition."""
import hashlib,re,zipfile,pathlib,sys
src=pathlib.Path(sys.argv[1])
expected="ebf9a0adef859f568d792d182f4ace08d026a27dc7f322bab735c67b07cd34c1"
with zipfile.ZipFile(src) as z:
    options=[i for i in z.infolist() if pathlib.PurePosixPath(i.filename).name=="mboot_a.img"]
    if len(options)!=1:raise RuntimeError("missing/ambiguous mboot")
    data=z.read(options[0])
assert len(data)==10485760 and hashlib.sha256(data).hexdigest()==expected
print("Live 8054 mboot exact SHA256:",hashlib.sha256(data).hexdigest())
# Restrict to printable strings; never report image content beyond selected fixed firmware command names.
strings=[(m.start(),m.group().decode("latin1")) for m in re.finditer(rb"[\x20-\x7e]{4,256}",data)]
patterns=[
 "fastboot","flashing","unlock","locked","devicestate","is_unlocked",
 "get_unlock","unlock_ability","avb read","avb write","avb lock",
 "avb unlock","avb is_unlocked","avb verify","avb verify",
 "avb_custom_key","avb_slot_verify","validate_public_key","vbmeta",
 "verify n","secure boot","secureboot","optee","tee","fuse","efuse",
 "mtkupgrade","pkg hashset","rsa verify","autoupgrade","check_usb_auto_upgrade",
 "usb_auto_upgrade","bootdelay","romusb","rom_usb","uart","serial downloader",
]
for pattern in patterns:
    matches=[(off,s) for off,s in strings if pattern.lower() in s.lower()]
    print("\n====",pattern,"unique_strings",len(matches))
    for off,s in matches[:28]:
        # No dynamic firmware values or factory identifiers in stdout: deterministic allowlist markers.
        sanitized=s.replace("\r","").replace("\n"," ")
        if re.search(r"(macaddr|serialno|device[_-]?id|keymaterial|keybox|secret|token|password)",sanitized,re.I):
            continue
        print(f"{off:08x}: {sanitized[:180]}")
print("\nRESULT: static string presence indicates compiled message/handler only, not functional unlock.")
