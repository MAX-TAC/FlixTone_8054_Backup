#!/usr/bin/env python3
"""Read-only deep inspection of live 8054 EROFS images and Mboot.
Reads from local working /tmp extracted by previous audit, never writes to projector.
Prints only public firmware file paths, U-Boot command literals, and selected non-unique settings.
"""
import hashlib, os, pathlib, re, subprocess, sys
root=pathlib.Path("/tmp/flix8054_work")
superimg=root/"super.img"
assert superimg.is_file()
OUT=pathlib.Path("/tmp/flix8054_erofs");OUT.mkdir(parents=True,exist_ok=True)

# Based on previously verified liblp metadata from this exact super image
parts=[
    ("system_a",1048576, 0),
    ("vendor_a",857735168, 0),
    ("product_a",1120927744,0),
    ("system_ext_a",1198522368,0),
]
# Parse the actual metadata again rather than trusting offsets or precomputed sizes.
def u32(data,o):return int.from_bytes(data[o:o+4],"little")
def u64(data,o):return int.from_bytes(data[o:o+8],"little")
with superimg.open("rb") as f:
    f.seek(4096); geo=f.read(52)
    assert u32(geo,0)==0x616c4467 and u32(geo,4)==52
    c=bytearray(geo);c[8:40]=bytes(32);assert hashlib.sha256(c).digest()==geo[8:40]
    ms=u32(geo,40)
    f.seek(12288);h=f.read(ms)
    assert u32(h,0)==0x414c5030
    hs=u32(h,8); tables=h[hs:hs+u32(h,44)]
    assert hashlib.sha256(tables).digest()==h[48:80]
    descriptors=[(u32(h,80+i*12),u32(h,84+i*12),u32(h,88+i*12)) for i in range(4)]
    po,pn,ps=descriptors[0];eo,en,es=descriptors[1]
    ext=[(u64(tables,eo+i*es),u32(tables,eo+i*es+8),
          u64(tables,eo+i*es+12),u32(tables,eo+i*es+20)) for i in range(en)]
    partmap={}
    for i in range(pn):
        off=po+i*ps
        name=tables[off:off+36].split(b"\0",1)[0].decode("ascii","replace")
        attrs=u32(tables,off+36)
        first=u32(tables,off+40);count=u32(tables,off+44)
        if name in ("system_a","vendor_a","product_a","system_ext_a") and count and first+count<=len(ext):
            partmap[name]=ext[first:first+count]
    assert len(partmap)==4,partmap.keys()

for name,expected_off,_ in parts:
    spans=partmap[name];amount=sum(e[0]*512 for e in spans)
    image=OUT/(name+".img")
    print("\n### Extracting",name,amount,"bytes from super",flush=True)
    with superimg.open("rb") as src,image.open("wb") as dest:
        for nsectors,typ,start,source in spans:
            assert typ==0 and source==0,(name,typ,source)
            off=start*512
            assert off>=0 and off+nsectors*512<=superimg.stat().st_size
            src.seek(off)
            remain=nsectors*512
            while remain>0:
                buf=src.read(min(remain,4*1024*1024))
                if not buf:raise RuntimeError("Unexpected end of "+name)
                dest.write(buf);remain-=len(buf)
    print("  logical image size MiB:",round(amount/1048576,2),flush=True)
    # If EROFS occupies only first portion, ignore AVB hashtree and FEC at the image tail.
    out=OUT/(name+"_tree");out.mkdir(exist_ok=True)
    cmd=["fsck.erofs","--extract="+str(out),str(image)]
    result=subprocess.run(cmd,capture_output=True,text=True,timeout=450)
    print("  fsck.erofs exit:",result.returncode,flush=True)
    print("  fsck.erofs status:",(result.stdout+"\n"+result.stderr)[-950:].replace(str(OUT),"<working_dir>"),flush=True)
    if result.returncode!=0:
        print("  Extraction error; skipping file enumeration",flush=True)
        continue
    allfiles=[p for p in out.rglob("*") if p.is_file() and not p.is_symlink()]
    apks=sorted(p for p in allfiles if p.name.lower().endswith(".apk"))
    print("  total regular files:",len(allfiles),"APK count:",len(apks),flush=True)
    def sanitize(path):
        x=str(path.relative_to(out))
        return x[:200] if len(x)<200 else x[:200]+"..."
    print("  APK paths:",flush=True)
    for p in apks[:140]:
        print("   ",sanitize(p),flush=True)
    print("  APK remainder:",max(0,len(apks)-140),flush=True)
    # Does not log proprietary firmware bytes, only filenames and selected non-sensitive init configs.
    important=re.compile(r"(ota|upgrade|recovery|fastboot|unlock|verity|avb|mtkupgrade|factory|magisk|cec|keylayout|keystone|projector)",re.I)
    matches=[p for p in allfiles if important.search(p.name) and
            p.suffix.lower() in (".rc",".xml",".json",".prop",".conf",".ini",".sh",".txt",".apk",".kl")]
    print("  Relevant code/config paths:",flush=True)
    for p in sorted(matches)[:100]:print("   ",sanitize(p),flush=True)
    for prop in ("build.prop","etc/build.prop"):
        p=out/prop
        if p.exists():
            for line in p.read_text(errors="replace").splitlines():
                if re.match(r"^(ro\.(build\.fingerprint|product\.device|build\.version\.release|rjpj\.machine\.id|rjpj\.yunota\.(zip|bin|url))|ro\.hardware)\s*=",line):
                    print("  selected build.prop:",line[:170],flush=True)
    print("  APK hash of OEM updater:",flush=True)
    for p in apks:
        if "RuiYunOta" in p.name:
            print("   ",sanitize(p),"sha256",hashlib.sha256(p.read_bytes()).hexdigest(),flush=True)

# Print selected nearby printable Mboot strings; these do not contain private key material.
print("\n### Mboot upgrade / signing / USB implementation clues")
data=(root/"mboot_a.img").read_bytes()
segments=re.findall(rb"[\x20-\x7e]{5,240}",data)
terms=re.compile(rb"mtkupgrade|upgrade_image\.pkg|auto_upgrade|usb_upgrade|usb_boot|bootdelay|recoverycmd|fastboot.*unlock|unlock.*fastboot|verify.*(rsa|sig|hash)|secure.*boot|rsa.*verify|avb_slot_verify|env.*upgrade",re.I)
found=[]
for raw in segments:
    if terms.search(raw):
        txt=raw.decode("ascii","replace").strip()
        # Avoid unbounded or private binary data if a string unexpectedly contains serial/cert.
        if len(txt)>220 or "-----BEGIN" in txt or "serialno=" in txt.lower():continue
        if txt not in found:found.append(txt)
print("Matching distinct U-Boot string count:",len(found))
for txt in found[:110]:print("  UBOOT:",txt,flush=True)

env=(root/"uenv.img").read_bytes()
for key in ("bootcmd","recoverycmd","bootdelay","verify","devicestate","usb_upgrade","usb_upgrade_path","auto_upgrade","upgrade_loader","upgrade_path","boot_mode"):
    m=re.search(rb"(?:^|\x00)"+key.encode()+rb"=([^\x00]{0,300})\x00",env,re.I)
    if m:
        s=m.group(1).decode("ascii","replace")
        if "serial" in s.lower() or "mac" in s.lower() or "key" in s.lower():
            s="<redacted for device privacy>"
        print("  ENV",key,"=",s[:270],flush=True)
    else:print("  ENV",key,"=<absent>",flush=True)

print("\n### Compare APK signing certificates against PUBLIC AOSP platform test certificate")
platform=pathlib.Path("/tmp/aosp-platform.x509.pem")
baseline=None
if platform.exists():
    r=subprocess.run(["openssl","x509","-in",str(platform),"-outform","DER"],capture_output=True)
    if r.returncode==0:
        baseline=hashlib.sha256(r.stdout).hexdigest()
        print("AOSP platform.x509.pem sha256",baseline,flush=True)
wanted={"KuSettings","KuSourceRJ","RuiAutoFocus","trdservice","trdmiddle",
        "TvSettingsPlus","RuiYunOta","KeystoneCorrection","zxlauncher",
        "zxstore","Provision","Factory","LiveTV","TvServices",
        "TrdFactoryTest","FTAirplayWireless","SystemUI"}
for part in ("system_a","vendor_a","system_ext_a","product_a"):
    tree=OUT/(part+"_tree")
    for apk in sorted(tree.rglob("*.apk")) if tree.exists() else []:
        if apk.stem not in wanted:continue
        try:
            ret=subprocess.run(["apksigner","verify","--print-certs",str(apk)],
                               capture_output=True,text=True,timeout=60)
        except Exception as e:
            print(" APK",apk.stem,"ERROR",repr(e)[:120]);continue
        match=re.search(r"Signer #1 certificate SHA-256 digest:\s*([0-9a-fA-F]+)",ret.stdout)
        if not match:
            print(" APK",apk.stem,"signature error:",(ret.stderr+"\n"+ret.stdout)[-240:],flush=True)
            continue
        h=match.group(1).lower()
        print(" APK",apk.stem,"SHA256",h,
              "MATCH_AOSP_PLATFORM",h==baseline if baseline else "unknown",
              "VALID",ret.returncode==0,flush=True)

print("\n### Additional bootloader acceptance strings (presence only)")
sigterms=["hashset","verify pkg","pkg hash","signature","rsa","signed","rsa_verify",
          "secure boot","pkg version","older than current","automatic upgrade",
          "usb_auto_upgrade","check_usb_auto_upgrade","fastboot flashing","fastboot oem"]
low=(root/"mboot_a.img").read_bytes().lower()
for term in sigterms:
    print(" BOOTLOADER",repr(term),"count",low.count(term.encode()),flush=True)

print("\nFinished offline stock build inspection. NO flashing or installation.")
