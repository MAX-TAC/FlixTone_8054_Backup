#!/usr/bin/env python3
"""Read-only offline 8054 Factory Menu code and APK inventory audit.
Never export APKs, factory-partition data or calibration content.
"""
from pathlib import Path
import hashlib, zipfile, re, subprocess, collections, sys

E=Path('/tmp/flix8054_erofs')
factory=E/'system_ext_a_tree/app/Factory/Factory.apk'
src=Path('/tmp/factory_src/sources')
out=Path('/tmp/factory_report/FactoryMenu_8054_Static_Audit.md')
assert factory.is_file(),factory
assert src.is_dir(),src
out.parent.mkdir(parents=True,exist_ok=True)
lines=[]
add=lines.append
add('# Factory Menu static analysis — actual FlixTone 8054 firmware')
add('')
add('Only code identifiers and non-device-specific values. Never deploy or publish original APK contents.')
add('')
add('## Exact APK')
add('- Relative path: system_ext/app/Factory/Factory.apk')
add(f'- Size bytes: {factory.stat().st_size}')
add(f'- SHA256: {hashlib.sha256(factory.read_bytes()).hexdigest()}')
with zipfile.ZipFile(factory) as z:
    d=[n for n in z.namelist() if re.fullmatch(r'classes\d*\.dex',Path(n).name)]
    libs=[n for n in z.namelist() if n.endswith('.so')]
add(f'- DEX count: {len(d)}; embedded native libs: {libs[:25]}')
for cmd,label in [
    (['aapt','dump','badging',str(factory)],'Android badging'),
    (['apksigner','verify','--print-certs',str(factory)],'Signing certificate'),
]:
    p=subprocess.run(cmd,capture_output=True,text=True,timeout=90)
    add('### '+label)
    for line in (p.stdout+p.stderr).splitlines()[:25]:
        if label=='Android badging' and not re.search(r'package:|sdkVersion|targetSdkVersion|application-label|launchable-activity|uses-permission',line):continue
        add('    '+line[:300])
add('')
add('## All APKs found in the super image')
total=0
for part in ('system_a','vendor_a','product_a','system_ext_a'):
    tree=E/(part+'_tree')
    apks=sorted(tree.rglob('*.apk'))
    total+=len(apks)
    add(f'### {part} ({len(apks)} APKs)')
    for p in apks:add('- '+str(p.relative_to(tree)))
add(f'Total APK inventory count: {total}')
add('')
add('## Factory manifest components')
p=subprocess.run(['aapt','dump','xmltree',str(factory),'AndroidManifest.xml'],capture_output=True,text=True,timeout=90)
manifest=p.stdout.splitlines()
for i,line in enumerate(manifest):
    if re.search(r'E: (activity|service|receiver|provider|uses-permission)\b',line):
        add('  '+line.strip()[:300])
        for q in manifest[i+1:i+6]:
            if 'android:name' in q or 'android:exported' in q or 'android:permission' in q:
                add('    '+q.strip()[:300])
add('')
add('## Factory Java class inventory: selected package names')
java=list(src.rglob('*.java'))
add(f'JADX produced {len(java)} Java source files.')
names=re.compile(r'factory|designmenu|dap|peq|source|hdmi|input|api.?service|uart|shell|pq|dolby|picture|watchdog|calib|testpattern|panel',re.I)
files=[p for p in java if names.search(str(p.relative_to(src)))]
add(f'Matched classes by name: {len(files)}')
for p in files[:200]:add('- '+str(p.relative_to(src)))
add('')
add('## Factory call-site evidence (decompiled Java)')
terms=re.compile(r'factorymenu|designmenu|ApiService|MtkTvFApi|setPeq|setPEQ|getPEQ|getPeq|Dap|DAP|executeShell|exec\(|FactoryPQ|PQUpdate|Uart|UART|WatchDog|watchdog|setPowerOn|setInputSource|setSource|startActivity|startService|bindService|remove.*[Pp]artition|[Kk]eystone',re.I)
matches=[]
for p in java:
    rel=str(p.relative_to(src))
    if not names.search(rel):continue
    rows=p.read_text(errors='replace').splitlines()
    hits=[(i,row.strip()) for i,row in enumerate(rows) if terms.search(row)]
    if not hits:continue
    score=len(hits)+sum(4 for i,row in hits if re.search(r'Exec|Uart|PQUpdate|Peq|DAP|ApiService|FactoryPQ|setSource',row,re.I))
    matches.append((score,rel,hits))
for score,rel,hits in sorted(matches,reverse=True)[:120]:
    add('### '+rel+f' ({len(hits)} matches)')
    for i,row in hits[:14]:add(f'  {i+1}: {row[:320]}')
add('')
add('## Factory API references from other installed APKs')
needles=[b'mediatek.factorymenu.ui',b'mediatek.tvsetting.factory.ui',b'MtkTvFApi',b'mtktvfactory',b'DesignMenuActivity',b'FactoryCameraActivity']
cross=[]
for part in ('system_a','vendor_a','product_a','system_ext_a'):
    tree=E/(part+'_tree')
    for apk in tree.rglob('*.apk'):
        if apk==factory:continue
        counts={}
        try:
            with zipfile.ZipFile(apk) as z:
                for name in z.namelist():
                    if not re.fullmatch(r'classes\d*\.dex',Path(name).name):continue
                    data=z.read(name)
                    for needle in needles:
                        count=data.count(needle)
                        if count:counts[needle.decode()]=counts.get(needle.decode(),0)+count
        except Exception:continue
        if counts:cross.append((part,str(apk.relative_to(tree)),counts))
for part,fn,counts in sorted(cross):
    add('- '+part+'/'+fn+': '+', '.join(f'{k} x{n}' for k,n in sorted(counts.items())))
out.write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('FACTORY_APK_BYTES',factory.stat().st_size)
print('FACTORY_SHA256',hashlib.sha256(factory.read_bytes()).hexdigest())
print('TOTAL_APKS',total)
print('JADX_JAVA_FILES',len(java))
print('FACTORY_CALLERS',len(cross))
print('BEGIN_TECHNICAL_REPORT')
print('\n'.join(lines[:550]))
print('END_TECHNICAL_REPORT')
