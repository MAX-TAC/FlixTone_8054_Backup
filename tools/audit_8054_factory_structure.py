#!/usr/bin/env python3
"""Read-only offline inspection of the owner's explicit PRIVATE_FACTORY backup.
Extract locally in ephemeral CI, print structural metadata, never upload raw content or private keys.
"""
import hashlib,os,pathlib,subprocess,sys,zipfile,re
zpath=pathlib.Path(sys.argv[1])
root=pathlib.Path("/tmp/d11-private-extract")
root.mkdir(exist_ok=True)
expected={
"eeprom_a.img":2097152,
"persist.img":20971520,
"private.img":20971520,
"project_id.img":5242880,
"tvcertificate.img":8388608,
"tvconfig_a.img":157286400}
with zipfile.ZipFile(zpath,"r",allowZip64=True) as z:
    for name,size in expected.items():
        matches=[x for x in z.infolist() if x.filename.replace("\\","/").split("/")[-1]==name and "PRIVATE_FACTORY" in x.filename.upper()]
        if len(matches)!=1:print("MISSING/AMBIGUOUS",name,len(matches));continue
        item=matches[0]
        if item.file_size!=size:raise RuntimeError("unexpected length "+name)
        p=root/name
        h=hashlib.sha256()
        with z.open(item,"r") as src,p.open("wb") as out:
            while True:
                b=src.read(2*1024*1024)
                if not b:break
                h.update(b);out.write(b)
        if p.stat().st_size!=size:raise RuntimeError("size mismatch "+name)
        data=p.read_bytes()
        magic=data[:16]
        typ=subprocess.run(["file","-b",str(p)],capture_output=True,text=True).stdout.strip()
        sigs=[]
        if len(data)>=2048 and data[1080:1082]==b"\x53\xef":sigs.append("ext4")
        if len(data)>=2048 and data[1024:1028]==bytes.fromhex("e2e1f5e0"):sigs.append("EROFS")
        if data[:4]==b"hsqs":sigs.append("SquashFS")
        if data[:4]==b"AVB0":sigs.append("AVB")
        print(name,"BYTES",size,"SHA256",h.hexdigest(),"MAGIC",magic.hex(),"FILE",typ[:130],"FS",",".join(sigs) or "unknown")
        for tok in ["upgrade_image.pkg","mtkupgrade","usb_auto_upgrade","bootcmd","bootdelay","board_id","ro.rjpj.machine.id","aml_upgrade"]:
            n=data.lower().count(tok.encode().lower())
            if n:print("  firmware config marker",tok,"occurrences",n)
        if "ext4" in sigs:
            result=subprocess.run(["debugfs","-R","ls -p /",str(p)],capture_output=True,text=True,timeout=30)
            lines=[x.strip() for x in result.stdout.splitlines() if x.strip()]
            # List entry types and filename only if simple non-secret name
            simple=[]
            for l in lines:
                f=l.split("/")
                if len(f)>5:
                    namepart=f[-2]
                    if re.fullmatch(r"[a-zA-Z0-9_.\-]{1,50}",namepart) and not any(t in namepart.lower() for t in ["key","cert","id","imei","mac","serial","token"]):
                        simple.append(namepart)
            print("  ext4 top-level safe filenames:",sorted(set(simple))[:40])
print("PRIVATE_FACTORY images checked, originals not changed and no raw bytes uploaded.")
