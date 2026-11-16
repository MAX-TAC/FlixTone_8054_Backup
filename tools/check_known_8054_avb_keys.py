#!/usr/bin/env python3
"""Read-only comparison of live vbmeta RSA key against public known-test-key corpus."""
import glob,os,pathlib,subprocess,sys
p=pathlib.Path(sys.argv[1]); data=p.read_bytes()
assert data[:4]==b"AVB0"
auth=int.from_bytes(data[12:20],"big")
puboff=int.from_bytes(data[64:72],"big")
pubsize=int.from_bytes(data[72:80],"big")
key=data[256+auth+puboff:256+auth+puboff+pubsize]
assert len(key)==1032,("unrecognized public key size",len(key))
nbits=int.from_bytes(key[:4],"big")
assert nbits==4096
mod=int.from_bytes(key[8:8+512],"big")
print("Live OEM RSA bits:",nbits,"public key bytes:",len(key))
cands=sorted(pathlib.Path(sys.argv[2]).glob("**/*.pem"))
match=[]
ok=0
for f in cands:
    r=subprocess.run(["openssl","rsa","-in",str(f),"-noout","-modulus"],capture_output=True,text=True)
    if r.returncode!=0:continue
    try: value=int(r.stdout.strip().split("=",1)[1],16)
    except Exception:continue
    ok+=1
    yes=value==mod
    print("KNOWN_KEY",f.name,"MATCH:",yes)
    if yes:match.append(str(f))
print("Checked known private signing keys:",ok)
print("MATCH FOUND:",bool(match))
if match:print("MATCHING PUBLICLY KNOWN KEY(S):",[pathlib.Path(x).name for x in match])
