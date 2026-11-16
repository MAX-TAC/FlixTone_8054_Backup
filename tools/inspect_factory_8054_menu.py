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

add('')
add('## Targeted UI handlers and concrete operations (JADX output)')
targets=[
 'mediatek/tvsetting/factory/ui/ApiService.java',
 'mediatek/tvsetting/factory/ui/ProjectorManager.java',
 'mediatek/tvsetting/factory/ui/designmenu/ExecuteShellActivity.java',
 'mediatek/tvsetting/factory/ui/designmenu/DesignMenuActivity.java',
 'mediatek/tvsetting/factory/ui/designmenu/PEQAdjustViewHolder.java',
 'mediatek/tvsetting/factory/ui/designmenu/AdvancedEffectDapViewHolder.java',
 'mediatek/tvsetting/factory/ui/designmenu/OtherOptionAdjustViewHolder.java',
 'mediatek/tvsetting/factory/ui/designmenu/FactoryPqUpdateActivity.java',
 'mediatek/tvsetting/factory/ui/designmenu/FactoryMemcActivity.java',
 'mediatek/tvsetting/factory/ui/factorymenu/OtherOptionForFactory.java',
 'mediatek/tvsetting/factory/ui/factorymenu/FactoryMenuActivity.java',
 'mediatek/tvsetting/factory/ui/factorymenu/FactoryCameraActivity.java',
 'mediatek/tvsetting/factory/ui/designmenu/FactoryProgramPresetActivity.java',
]
interesting=re.compile(r'Runtime\.getRuntime|\.exec\(|\b(sh|cmd|rm\s|dd\s)|getPEQ|setPEQ|setPeq|getPeq|PeqParam|DapParam|DolbyDap|\.getDap|\.setDap|\.setFactory|FactoryPartition|removeFactory|FactoryPq|PQUpdate|load.*File|\.update|updatePq|setUart|setWatchdog|setWatchDog|setPowerOn|setSource|setHdmi|factorymenu|startActivity|startService|bindService|mGain\d+Val|setAudio|sendBroadcast',re.I)
for target in targets:
    f=src/target
    if not f.exists():continue
    arr=f.read_text(errors='replace').splitlines()
    add('### '+target+f' ({len(arr)} total source lines)')
    # method declarations first
    declarations=[(i,row.strip()) for i,row in enumerate(arr) if re.search(r'^\s*(public|private|protected)\s+(static\s+)?[\w<>.\[\], ?]+\s+\w+\s*\([^;]*\)\s*(?:throws [^{]+)?\s*\{',row)]
    add('Method declarations:')
    for i,row in declarations[:75]:add(f'  {i+1}: {row[:250]}')
    hits=[i for i,row in enumerate(arr) if interesting.search(row)]
    add('Selected operation evidence:')
    shown=set()
    for i in hits[:100]:
        for k in range(max(0,i-1),min(len(arr),i+3)):
            if k in shown:continue
            shown.add(k)
            add(f'  {k+1}: {arr[k].strip()[:350]}')


add('')
add('## Extended security and functional mapping')
fullmanifest=subprocess.run(['aapt','dump','xmltree',str(factory),'AndroidManifest.xml'],capture_output=True,text=True,timeout=90).stdout
for row in fullmanifest.splitlines():
    if re.search(r'android:(sharedUserId|exported|permission|process|authorities|enabled|name|protectionLevel)',row):
        add('  '+row.strip()[:270])
add('')
add('## Every MediaTek Factory UI class and direct platform calls')
ui_root=src/'mediatek/tvsetting/factory/ui'
danger=re.compile(r'Runtime\.getRuntime\(\)\.exec|ProcessBuilder|SystemProperties\.(?:set|get)|Settings\.(?:Global|System|Secure)\.|\.sendBroadcast\(|\.startService\(|\.bindService\(|\.startActivity\(|setFactory|restoreToFactory|factoryReset|setWatchDog|setUart|setDolbyDapParam|setPEQEnable|setPeq|updatePq|saveAudioIni|MtkTvFApi|i2c\(|getI2c|setI2c|exec\(|\.setSource|\.setInput|setPicture|setMemc|\.set.*Calibration|\\.erase|\\.delete',re.I)
ui_files=sorted(ui_root.rglob('*.java'))
add(f'UI package total Java classes: {len(ui_files)}')
for javafile in ui_files:
    rel=javafile.relative_to(src)
    arr=javafile.read_text(errors='replace').splitlines()
    if any('/R.java' in str(rel) or '/BuildConfig.java' in str(rel) for _ in [0]):continue
    calls=[(i+1,line.strip()) for i,line in enumerate(arr) if danger.search(line)]
    decl=[(i+1,line.strip()) for i,line in enumerate(arr) if re.search(r'^\s*(public|private|protected)\s+(static\s+)?[\w<>, .\[\]?]+\s+\w+\s*\([^;]*\)\s*(?:throws [^{]+)?\s*\{',line)]
    if not calls and not decl:continue
    add('### '+str(rel)+f' — {len(arr)} lines, {len(calls)} API/callsite matches')
    for i,line in decl[:28]:add(f'   method L{i}: {line[:205]}')
    for i,line in calls[:45]:
        # Do not log content that may include embedded secrets or certificates
        if '-----BEGIN' in line or 'PRIVATE KEY' in line:continue
        add(f'   call L{i}: {line[:315]}')
add('')
add('## Entire implementation for small but security-sensitive Factory classes')
for target in (
 'mediatek/tvsetting/factory/ui/ApiService.java',
 'mediatek/tvsetting/factory/ui/ProjectorManager.java',
 'mediatek/tvsetting/factory/ui/FactoryIntent.java',
 'mediatek/tvsetting/factory/ui/designmenu/FactoryDolbyActivity.java',
 'mediatek/tvsetting/factory/ui/designmenu/FactoryDTSActivity.java',
 'mediatek/tvsetting/factory/ui/designmenu/FactoryUpgradeUrsaFwActivity.java',
 'mediatek/tvsetting/factory/ui/designmenu/FactoryKeyUpgradeActivity.java',
 'mediatek/tvsetting/factory/ui/designmenu/FactoryInstallQdaActivity.java',
 'mediatek/tvsetting/factory/ui/designmenu/FactoryInstallFvpIntermediateKeyActivity.java',
 'mediatek/tvsetting/factory/ui/designmenu/FactoryMemcActivity.java',
 'mediatek/tvsetting/factory/ui/designmenu/FactoryPqUpdateActivity.java',
 'mediatek/tvsetting/factory/ui/factorymenu/InfoViewHolder.java',
 'mediatek/tvsetting/factory/ui/designmenu/PanelInfoViewHolder.java',
 'mediatek/tvsetting/factory/ui/designmenu/SSCAdjustViewHolder.java',
 'mediatek/tvsetting/factory/ui/designmenu/TestPatternViewHolder.java',
):
    ff=src/target
    if not ff.exists():continue
    contents=ff.read_text(errors='replace').splitlines()
    add('### '+target+f' ({len(contents)} lines)')
    for i,line in enumerate(contents[:270],1):
        if '-----BEGIN' in line or 'PRIVATE KEY' in line:continue
        add(f'  {i}: {line[:300]}')
add('')
add('## Focused low-level constants and limits')
for target in ('com/mediatek/twoworlds/factory/common/MtkTvFApiAudioTypes.java',
               'com/mediatek/twoworlds/factory/MtkTvFApiAudio.java',
               'com/mediatek/twoworlds/factory/MtkTvFApiSystem.java',
               'com/mediatek/twoworlds/factory/MtkTvFApiDisplay.java'):
    ff=src/target
    if not ff.exists():continue
    ar=ff.read_text(errors='replace').splitlines()
    add('### '+target)
    rr=re.compile(r'PEQ_|PEQ_ADJUST|Dap|DOLBY|EnumSoundMode|FactoryPower|Factory.*Reset|UART|WatchDog|MFC|MEMC|xvYCC|HDMI_EDID|public (?:int|boolean|void|String|static)',re.I)
    for i,line in enumerate(ar,1):
        if rr.search(line):add(f'   L{i}: {line.strip()[:260]}')
        if i>8000:break

out.write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('FACTORY_APK_BYTES',factory.stat().st_size)
print('FACTORY_SHA256',hashlib.sha256(factory.read_bytes()).hexdigest())
print('TOTAL_APKS',total)
print('JADX_JAVA_FILES',len(java))
print('FACTORY_CALLERS',len(cross))
print('BEGIN_TECHNICAL_REPORT')
print('\n'.join(lines[:550]))
print('END_TECHNICAL_REPORT')
