#!/usr/bin/env python3
"""Read-only safe metadata analysis of an owner-supplied GitHub draft release.
No factory-partition contents, encryption keys, user data or image files are published.
"""
import hashlib,os,pathlib,re,struct,sys,zipfile

ZIP=pathlib.Path(sys.argv[1])
DEST=pathlib.Path("/tmp/flix8054_work")
DEST.mkdir(parents=True,exist_ok=True)
SAFE={"mboot_a.img","uenv.img","super.img"}
EXPECTED={"mboot_a.img":10485760,"uenv.img":16777216,"super.img":2225078272}
print("Archive bytes:",ZIP.stat().st_size,flush=True)
with zipfile.ZipFile(ZIP,"r",allowZip64=True) as z:
    matching={}
    for info in z.infolist():
        n=info.filename.replace("\\","/")
        b=pathlib.PurePosixPath(n).name
        if "PRIVATE_FACTORY" in n.upper() or b.lower() in ("eeprom_a.img","persist.img","private.img","project_id.img","tvcertificate.img","tvconfig_a.img"):
            continue
        if b in SAFE and not info.is_dir():
            matching[b]=info
    print("Safe partition files present:",sorted(matching),flush=True)
    for name in ("mboot_a.img","uenv.img","super.img"):
        if name not in matching: print("MISSING",name,flush=True);continue
        info=matching[name]
        print("Extracting",name,"uncompressed bytes",info.file_size,flush=True)
        if info.file_size!=EXPECTED[name]:raise RuntimeError(name+" unexpected byte length")
        h=hashlib.sha256()
        with z.open(info,"r") as source,(DEST/name).open("wb") as out:
            while True:
                chunk=source.read(8*1024*1024)
                if not chunk:break
                h.update(chunk);out.write(chunk)
        print("Verified extracted",name,"SHA256",h.hexdigest(),flush=True)

TOKENS=[
  "mtkupgrade","upgrade_image.pkg","fastboot","recovery","bootcmd",
  "unlock","devicestate","saveenv","setenv","verify n","verify y",
  "usb start","usb reset","usb storage","usb upgrade","usbboot",
  "auto_upgrade","autoupgrade","bootdelay","loadb","tftpboot",
  "romusb","bootm","booti","bootargs","avb","secureboot",
  "ab_select","bootmenu","mmc read","mmc write","kernel"
]
print("\n=== Bootloader string presence (never printing raw strings) ===")
for name in ("mboot_a.img","uenv.img"):
    p=DEST/name
    if not p.exists():continue
    data=p.read_bytes().lower()
    print("Image",name,"start16",data[:16].hex(),flush=True)
    for token in TOKENS:
        count=data.count(token.encode("ascii"))
        if count:
            print("  token",repr(token),"count",count,flush=True)
    for label,pat in [
      ("MStar MTK USB upgrade command",b"mtkupgrade usb"),
      ("factory PKG image name",b"upgrade_image.pkg"),
      ("U-Boot build marker",b"u-boot"),
      ("AVB verified boot marker",b"avb_slot_verify"),
      ("unlock API marker",b"flashing unlock"),
    ]:
        print("  probe",label,pat in data,flush=True)

SUPER=DEST/"super.img"
if not SUPER.exists():
    print("Super file missing; skipping metadata parser",flush=True)
    sys.exit(0)
print("\n=== Android super partition table (read-only metadata parser) ===")
def u32(b,o):return struct.unpack_from("<I",b,o)[0]
def u64(b,o):return struct.unpack_from("<Q",b,o)[0]
def validgeo(b):
    if len(b)<52 or u32(b,0)!=0x616c4467 or u32(b,4)!=52:return None
    c=bytearray(b[:52]);c[8:40]=bytes(32)
    if hashlib.sha256(c).digest()!=b[8:40]:return None
    size,slots,block=struct.unpack_from("<III",b,40)
    if not(0<size<1048576 and 0<slots<8):return None
    return (size,slots,block)
def parse_meta(f,off,size):
    f.seek(off); b=f.read(size)
    if len(b)!=size or u32(b,0)!=0x414c5030:return None
    major,minor,hsize=struct.unpack_from("<HHI",b,4)
    if major!=10 or hsize<128 or hsize>=size:return None
    h=bytearray(b[:hsize]);h[12:44]=bytes(32)
    if hashlib.sha256(h).digest()!=b[12:44]:return None
    ts=u32(b,44)
    if ts>size-hsize:return None
    tables=b[hsize:hsize+ts]
    if hashlib.sha256(tables).digest()!=b[48:80]:return None
    descriptors=[struct.unpack_from("<III",b,80+i*12) for i in range(4)]
    o,n,sz=descriptors[0]
    eo,en,esz=descriptors[1]
    if sz<48 or esz<24 or o+n*sz>ts or eo+en*esz>ts:return None
    extents=[]
    for i in range(en):
        p=eo+i*esz
        extents.append((u64(tables,p),u32(tables,p+8),u64(tables,p+12),u32(tables,p+20)))
    parts=[]
    for i in range(n):
        p=o+i*sz
        name=tables[p:p+36].split(b"\0",1)[0].decode("ascii",errors="replace")
        attr,first,num=struct.unpack_from("<III",tables,p+36)
        if not name or first+num>len(extents):continue
        pext=extents[first:first+num]
        nbytes=sum(e[0]*512 for e in pext)
        suffix_flag=(attr&2)!=0
        parts.append((name,attr,first,num,nbytes,pext,suffix_flag))
    return (major,minor,parts)
with SUPER.open("rb") as f:
    geo=None
    for off in (4096,8192,0,512,1024):
        f.seek(off); g=validgeo(f.read(52))
        if g:geo=(off,*g);break
    if not geo:
        print("No standard geometry found; image may require different parser")
    else:
        off,maxsize,slots,block=geo
        print("Geometry at:",off,"max metadata:",maxsize,"slots:",slots,"logical block:",block)
        start=12288 if off>=4096 else off+4096
        for slot in range(slots):
            md=parse_meta(f,start+slot*maxsize,maxsize)
            if not md:
                print("Slot",slot,"no primary metadata")
                continue
            major,minor,parts=md
            print("Slot",slot,"LP metadata:",str(major)+"."+str(minor),"partitions:",len(parts))
            for name,attr,first,num,nbytes,pext,suff in parts:
                if not re.fullmatch("[A-Za-z0-9_.-]{1,36}",name):continue
                print(" ",name,"size MiB",round(nbytes/1048576,2),"attrs",attr,"extents",num,"slot_suffixed",suff)

print("\n=== Exact U-Boot environment triggers: safe, key-restricted inspection ===")
env=(DEST/"uenv.img").read_bytes()
boot=(DEST/"mboot_a.img").read_bytes().lower()
known=("bootcmd","bootdelay","auto_upgrade","upgrade_cmd","verify","devicestate","recoverycmd","boot_targets","bootmenu_0","bootmenu_delay","boot_mode","bootmode")
for key in known:
    bkey=key.encode("ascii")+b"="
    m=re.search(rb"(?:^|\x00)"+re.escape(bkey)+rb"([^\x00]{0,1024})\x00",env,re.I)
    if not m:
        print(" env",key,"not found as zero-delimited key=value")
        continue
    val=m.group(1).decode("ascii",errors="replace").lower()
    if key in ("bootdelay","verify","devicestate","auto_upgrade") and re.fullmatch(r"(?:0|1|2|3|4|5|6|7|8|9|10|lock|locked|unlock|unlocked|yes|no|y|n|true|false|on|off)",val):
        print(" env",key,"=",val)
    else:
        print(" env",key,"present, byte-length",len(val),
              "has_usb_upgrade",("mtkupgrade" in val or "usb upgrade" in val),
              "has_pkg",("upgrade_image.pkg" in val),
              "has_recovery",("recovery" in val),
              "has_fastboot",("fastboot" in val),
              "has_normal_boot",("bootm" in val or "booti" in val))
print(" bootloader has exact full 'mtkupgrade usb upgrade_image.pkg' command:",
      b"mtkupgrade usb upgrade_image.pkg" in boot)
print(" bootloader has USB reset + upgrade within 256 bytes:",
      any((b"usb reset" in boot[max(0,p-256):p+256] or b"usb start" in boot[max(0,p-256):p+256])
          for p in [m.start() for m in re.finditer(b"mtkupgrade",boot)]))

print("\n=== Super partition filesystem signatures ===")
with SUPER.open("rb") as f:
    for name,attrs,first,num,nbytes,ex,suff in (md[2] if geo and md else []):
        if not ex or not nbytes or not re.fullmatch(r"(system|vendor|system_ext|product)_[ab]",name):
            continue
        target=ex[0]
        if target[1]!=0:continue
        off=target[2]*512
        f.seek(off); data=f.read(2048)
        if len(data)<2048:continue
        fstype=("EROFS" if data[1024:1028]==bytes.fromhex("e2e1f5e0") else
                "EXT4" if data[1080:1082]==bytes.fromhex("53ef") else
                "SQUASHFS" if data[:4]==b"hsqs" else
                "UNKNOWN")
        print(" ",name,"filesystem",fstype,"start offset bytes",off)

print("DONE read-only; unique factory images were NOT extracted or uploaded.",flush=True)
