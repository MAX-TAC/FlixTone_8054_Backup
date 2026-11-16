#!/usr/bin/env python3
"""OFFLINE ONLY. Test whether existing Projector-Soft 8052 mod hooks apply to exact 8054 OEM APK."""
import hashlib,pathlib,re,shutil,subprocess,sys,zipfile
root=pathlib.Path("/tmp/flix8054_erofs")
apk=root/"system_ext_a_tree/priv-app/TvSettingsPlus/TvSettingsPlus.apk"
framework=root/"system_a_tree/system/framework/framework-res.apk"
work=pathlib.Path("/tmp/8054_port");work.mkdir(exist_ok=True)
assert apk.is_file(),apk
assert framework.is_file(),framework
def call(args,timeout=240):
    r=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=timeout)
    print("$", " ".join(str(x) for x in args))
    print(" exit",r.returncode,"\n",(r.stdout or "")[-2200:])
    return r.returncode
print("\n=== STOCK 8054 TvSettingsPlus metadata ===",flush=True)
call(["aapt","dump","badging",str(apk)])
call(["apksigner","verify","--verbose","--print-certs",str(apk)])
print("LIVE 8054 TvSettingsPlus SHA256",hashlib.sha256(apk.read_bytes()).hexdigest())
with zipfile.ZipFile(apk) as z:
    libs=[x for x in z.namelist() if x.endswith(".so")]
    print("Shared native libraries:",sorted(libs)[:40])
    print("Number of original DEX:",len([x for x in z.namelist() if re.match(r"classes\d*\.dex",x)]))
print("\n=== NON-INSTALLABLE OFFLINE 8054 hook compatibility test ===")
source=pathlib.Path("/tmp/projector-soft")
assert source.is_dir()
java=pathlib.Path("/tmp/apktool.jar")
assert java.is_file()
fw=work/"framework"; decoded=work/"decoded"
if call(["java","-jar",str(java),"if",str(framework),"-p",str(fw)],timeout=120)!=0:sys.exit(4)
if call(["java","-jar",str(java),"d","-f","-r","-p",str(fw),str(apk),"-o",str(decoded)],timeout=240)!=0:sys.exit(4)
results={}
for tool in ["patch_customer0_lightmode_smali.py","patch_aosp_root_menu_smali.py","patch_oem_sleep_menu_smali.py"]:
    p=source/"tools"/tool
    rr=work/(tool+".json")
    code=call([sys.executable,str(p),str(decoded),str(rr)])
    results[tool]=code==0
print("8054 patch hooks applied:",results)
if all(results.values()):
    candidate=work/"UNSIGNED_DO_NOT_INSTALL_8054.apk"
    build=call(["java","-jar",str(java),"b","-p",str(fw),str(decoded),"-o",str(candidate)],timeout=240)
    print("Noninstallable rebuilt 8054 APK:",build==0,
          "Size:",candidate.stat().st_size if candidate.is_file() else 0)
else:
    print("Skipping build: at least one 8052 hook incompatible with 8054.")
print("THIS IS A PREFLIGHT ONLY: no APK deployed, installed, published or flashed.")
