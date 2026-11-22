#!/usr/bin/env python3
"""Read-only exact-8054 static audit of system audio output routing configuration.
No device commands. No factory keys or full manifest dumps exported.
Requires EROFS directories extracted by tools/deep_audit_8054_stock.py.
"""
import collections
import pathlib
import re
import subprocess
import xml.etree.ElementTree as ET

ROOT=pathlib.Path("/tmp/flix8054_erofs")
PARTS=("system_a","system_ext_a","vendor_a","product_a")
AUDIO_RE=re.compile(r"audio_policy|audio_effect|mixer_paths|audio_platform|audio.*xml|audio.*conf|bluetooth.*audio",re.I)
PORT_RE=re.compile(r"(A2DP|BLUETOOTH|SPEAKER|HDMI|ARC|EARC|SPDIF|USB|LINE_OUT|HEADPHONE|REMOTE_SUBMIX|EFFECT)",re.I)
PKGS=("TvSettingsPlus","TvServices","KuSourceRJ","RJBluetoothSpeaker")
PRIV=("android.permission.MODIFY_AUDIO_ROUTING","android.permission.QUERY_AUDIO_STATE",
      "android.permission.MODIFY_AUDIO_SETTINGS","android.permission.BLUETOOTH_CONNECT",
      "android.permission.BLUETOOTH_PRIVILEGED","android.permission.WRITE_SECURE_SETTINGS",
      "android.permission.STATUS_BAR_SERVICE")
found=[]
for part in PARTS:
    t=ROOT/(part+"_tree")
    if not t.exists(): continue
    for p in t.rglob("*"):
        if not p.is_file(): continue
        rel=p.relative_to(t).as_posix()
        if AUDIO_RE.search(p.name) and p.suffix.lower() in (".xml",".conf"):
            # Only public config names; ignore private vendor values.
            found.append((part,rel,str(p)))
print("## Audio policy/effects XML and configs present (path only)")
for part,rel,_ in found[:100]: print(part,rel)
print("CONFIG_TOTAL",len(found))

print("\n## audio_policy_configuration.xml route/devicePort/mixPort names (static)")
total=0
for part,rel,full in found:
    if not ("audio_policy_configuration" in rel or "audio_policy_volumes" in rel): continue
    if not rel.endswith(".xml"):continue
    try: root=ET.parse(full).getroot()
    except Exception as exc: print("XML_PARSE_ERROR",part,rel,type(exc).__name__);continue
    devices=[];mixes=[];routes=[]
    for v in root.iter():
        if v.tag=="devicePort":
            name=v.attrib.get("tagName","")
            typ=v.attrib.get("type","")
            if name or typ:devices.append((name[:60],typ[:90],v.attrib.get("role","")[:12]))
        elif v.tag=="mixPort":
            name=v.attrib.get("name","")
            if name: mixes.append((name[:80],v.attrib.get("role","")[:12]))
        elif v.tag=="route":
            sink=v.attrib.get("sink","")
            sources=v.attrib.get("sources","")
            if sink:routes.append((sink[:85],sources[:150]))
    print("CONFIG",part,rel,"deviceports",len(devices),"mixports",len(mixes),"routes",len(routes))
    for v in devices[:100]:print("PORT",*v)
    for v in mixes[:60]:print("MIX",*v)
    for v in routes[:90]:print("ROUTE",*v)
    total+=len(devices)
print("DEVICEPORTS_TOTAL",total)
print("NOTICE: A2DP endpoints may be registered dynamically by BT service rather than vendor XML.")

print("\n## AudioEffect engine configuration (public effect names only)")
for part,rel,full in found:
    if not (("audio_effects" in rel or "audio_effect" in rel) and rel.endswith(".xml")):continue
    try: root=ET.parse(full).getroot()
    except Exception: continue
    descriptors=[]
    for v in root.iter():
        if v.tag in ("effect","apply","lib","library","stream","deviceEffects","devicePort"):
            name=v.attrib.get("name",v.attrib.get("effect",v.attrib.get("type","")))
            if name and not re.search(r"password|private|serial|license|token|cert",name,re.I):
                descriptors.append((v.tag,name[:80]))
    print("EFFECT_CONFIG",part,rel,"entries",len(descriptors))
    for entry in descriptors[:45]:print("EFFECT",*entry)

print("\n## TvSettingsPlus stock installed APK manifest permission declarations")
apks=[]
for part in PARTS:
    t=ROOT/(part+"_tree")
    if not t.exists():continue
    for p in t.rglob("*.apk"):
        if p.stem in PKGS: apks.append((part,p))
for part,p in sorted(apks):
    cmd=["aapt","dump","permissions",str(p)]
    try:
        r=subprocess.run(cmd,capture_output=True,text=True,timeout=40)
        if r.returncode:
            print("APK_AAPT_ERROR",part,p.stem,r.returncode); continue
        raw=r.stdout
        print("APK",part,p.stem)
        for permission in PRIV:
            # Output one boolean per known permission; never emit additional manifest contents.
            print("PERMISSION_DECLARED",p.stem,permission.split(".")[-1],
                  bool(re.search(re.escape(permission)+r"(?=['\s])",raw)))
    except Exception as e:print("APK_INSPECT_ERROR",p.stem,type(e).__name__)
print("APK_MATCHES",len(apks))

print("\n## Privapp allowlist in factory partitions")
for part in PARTS:
    t=ROOT/(part+"_tree")
    if not t.exists():continue
    for p in sorted(t.rglob("*.xml")):
        if "privapp-permissions" not in p.name:continue
        try: root=ET.parse(p).getroot()
        except Exception:continue
        for entry in root.iter("privapp-permissions"):
            pkg=entry.attrib.get("package","")
            if pkg not in ("com.android.tv.settings","com.my.settings",
                          "com.mediatek.tvinput","com.mediatek.tvservice"):
                continue
            grants=[v.attrib.get("name","") for v in entry.findall("permission")]
            denied=[v.attrib.get("name","") for v in entry.findall("deny-permission")]
            print("PRIVAPP",part,p.relative_to(t),pkg)
            for permission in PRIV:
                print("ALLOWLIST",pkg,permission.split(".")[-1],permission in grants,
                      "DENIED",permission in denied)
print("NOTE: privapp allowlist ≠ runtime grant. Actual permission grant and audio route require on-device dumpsys.")

print("\n## Exact installed android framework versus TvSettingsPlus signing certificate")
system_tree=ROOT/"system_a_tree"
framework=system_tree/"system/framework/framework-res.apk"
tvsettings=ROOT/"system_ext_a_tree/priv-app/TvSettingsPlus/TvSettingsPlus.apk"
digest_re=re.compile(r"Signer #1 certificate SHA-256 digest:\s*([a-f0-9]+)",re.I)
digests={}
for tag,p in (("android_framework_res",framework),("TvSettingsPlus",tvsettings)):
    if not p.is_file():
        print("APK_CERT_MISSING",tag)
        continue
    try:
        proc=subprocess.run(["apksigner","verify","--print-certs",str(p)],capture_output=True,text=True,timeout=45)
        match=digest_re.search(proc.stdout)
        if proc.returncode==0 and match:
            digests[tag]=match.group(1).lower()
            print("APK_CERT_SHA256",tag,digests[tag])
        else: print("APK_CERT_UNVERIFIED",tag,proc.returncode)
    except Exception as exc:print("APK_CERT_ERROR",tag,type(exc).__name__)
if len(digests)==2:
    print("FRAMEWORK_TVSETTINGS_CERT_EQUAL",digests["android_framework_res"]==digests["TvSettingsPlus"])
print("NOTE: cert equality is strong evidence that a future properly signed APK could qualify for signature permissions, but it does NOT prove actual grant or MediaTek Audio HAL route acceptance.")
