#!/usr/bin/env python3
"""Read-only exhaustive APK component inventory for actual FlixTone 8054 EROFS.
Produces text-only, non-sensitive artifacts. Does not infer runtime dependencies.
"""
import pathlib,subprocess,re,csv,json,zipfile,hashlib,collections
ROOT=pathlib.Path('/tmp/flix8054_erofs')
OUT=pathlib.Path('/tmp/fullmap8054');OUT.mkdir(parents=True,exist_ok=True)
parts=['system_a','vendor_a','product_a','system_ext_a']
apk_paths=[(part,p, p.relative_to(ROOT/(part+'_tree')).as_posix()) for part in parts
           for p in sorted((ROOT/(part+'_tree')).rglob('*.apk'))]
def cmd(args):
 try:
  p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=60,text=True,errors='replace')
  return p.stdout if p.returncode==0 else p.stdout+' '+p.stderr
 except Exception as exc:return 'ERROR '+str(exc)
def attr(lines,base,name):
 pat=re.compile(r'^\s*A:\s+'+re.escape(name)+r'(?:\([^)]*\))?=(?:"([^"]*)"|([^(\s]+))')
 for raw in lines:
  m=pat.search(raw)
  if m:return m.group(1) if m.group(1) is not None else m.group(2)
 return ''
def parse_components(aapt):
 output=[];rows=aapt.splitlines();key=re.compile(r'^(\s*)E: (activity|activity-alias|service|receiver|provider)\b')
 for i,line in enumerate(rows):
  m=key.match(line)
  if not m:continue
  depth=len(m.group(1))
  chunk=[]
  for nxt in rows[i+1:]:
   stripped=nxt.lstrip()
   if (stripped.startswith('E:') or stripped.startswith('A:')) and len(nxt)-len(stripped)<=depth:break
   if stripped.startswith('A:') and len(nxt)-len(stripped)==depth+2:chunk.append(nxt)
  name=attr(chunk,depth+2,'android:name')
  exported=attr(chunk,depth+2,'android:exported')
  permission=attr(chunk,depth+2,'android:permission')
  process=attr(chunk,depth+2,'android:process')
  enabled=attr(chunk,depth+2,'android:enabled')
  if name:output.append(dict(component_type=m.group(2),name=name,exported=exported,permission=permission,process=process,enabled=enabled))
 return output
def parse_badging(text):
 p=re.search(r"package: name='([^']+)'(?: versionCode='([^']*)')?(?: versionName='([^']*)')?",text)
 sdk=re.search(r"targetSdkVersion:'([^']+)'",text)
 return (p.group(1),p.group(2) or '',p.group(3) or '',sdk.group(1) if sdk else '') if p else ('','','','')
records=[];components=[];permissions=[];xref=[]
needles={
 'KuSettings':'com.my.settings','KuSourceRJ':'com.coolux.source',
 'FactoryUI':'mediatek.factorymenu.ui','FactoryApiService':'mediatek.tvsetting.factory.ui.ApiService',
 'FactoryDesignMenu':'DesignMenuActivity','MTKFactoryAPI':'MtkTvFApi','MTKFactoryHAL':'mtktvfactory',
 'RuiAutoFocus':'com.hysd.screen','KeystoneCorrection':'com.rjpj.tcorrection',
 'TvServices':'com.mediatek.tv.service','MTKInput':'com.mediatek.tvinput',
 'RuiYunOta':'com.rjpj.yunota','MultiMediaPlayer':'MultiMediaPlayer',
 'ADB':'android.intent.action.BOOT_COMPLETED'
}
for idx,(part,p,rel) in enumerate(apk_paths,1):
 print(f'[{idx}/{len(apk_paths)}] {part}/{rel}',flush=True)
 bad=cmd(['aapt','dump','badging',str(p)])
 pkg,vc,vn,sdk=parse_badging(bad)
 xt=cmd(['aapt','dump','xmltree',str(p),'AndroidManifest.xml'])
 su=attr(xt.splitlines(),0,'android:sharedUserId')
 manifest_perms=re.findall(r'E: uses-permission.*?\n\s*A:\s+android:name(?:\([^)]*\))?="([^"]+)"',xt)
 cs=parse_components(xt)
 sig=cmd(['apksigner','verify','--print-certs',str(p)])
 digest=re.search(r'certificate SHA-256 digest:\s*([0-9a-f]+)',sig)
 row=dict(partition=part,apk_path=rel,apk_filename=p.name,package=pkg,versionCode=vc,versionName=vn,targetSdk=sdk,sharedUserId=su,cert_sha256=digest.group(1) if digest else '',size_bytes=p.stat().st_size,activities=sum(x['component_type'].startswith('activity') for x in cs),services=sum(x['component_type']=='service' for x in cs),receivers=sum(x['component_type']=='receiver' for x in cs),providers=sum(x['component_type']=='provider' for x in cs))
 records.append(row)
 for c in cs:
  components.append(dict(partition=part,package=pkg,apk_path=rel,**c))
 for permission in manifest_perms:permissions.append(dict(package=pkg,permission=permission))
 counts=collections.Counter()
 try:
  with zipfile.ZipFile(p) as z:
   for info in z.infolist():
    if re.fullmatch(r'classes\d*\.dex',pathlib.PurePosixPath(info.filename).name):
     blob=z.read(info.filename)
     for name,nd in needles.items():
      n=blob.count(nd.encode())
      if n:counts[name]+=n
 except Exception as ex:counts['ZIP_ERROR']=1
 for name,n in counts.items():xref.append(dict(source_package=pkg,source_apk=rel,needle_name=name,matched_literal=needles.get(name,''),count=n,certainty='DEX_STRING_ONLY_NOT_RUNTIME_CALL'))
def writecsv(name,data):
 with (OUT/name).open('w',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(data[0]) if data else ['empty'])
  w.writeheader();w.writerows(data)
writecsv('APK_INVENTORY_8054.csv',records)
writecsv('MANIFEST_COMPONENTS_8054.csv',components)
writecsv('PERMISSIONS_8054.csv',permissions)
writecsv('DEX_REFERENCE_INDICATORS_8054.csv',xref)
(OUT/'ALL_APK_COMPONENTS_8054.json').write_text(json.dumps(dict(metadata=dict(date='2026-11-17',source='SHA256 verified exact 8054 super from user GitHub backup',note='static manifest, no claim of runtime call graph'),apks=records,components=components,permissions=permissions,reference_indicators=xref),ensure_ascii=False,indent=2),encoding='utf-8')
lines=['# FlixTone 8054 — exhaustive static APK + manifest inventory','',
       '## Provenance','Extracted read-only from original FlixTone_8054_Backup.zip / super.img. Signed APK metadata, AndroidManifest components, permission declarations, and DEX *literal indicators*. Not a runtime call graph.','',
       f'- APK files: **{len(records)}**',
       f'- Manifest components extracted: **{len(components)}**',
       f'- Declared uses-permissions: **{len(permissions)}**',
       f'- DEX string indicators: **{len(xref)}**','',
       '## Application and package inventory','',
       '| Partition | APK | Package | Activity | Service | Receiver | Provider | system UID |',
       '|---|---|---|---:|---:|---:|---:|---|']
for r in records:
 lines.append('| '+ ' | '.join(str(r[k]) or '—' for k in ('partition','apk_path','package','activities','services','receivers','providers','sharedUserId'))+' |')
lines+=['','## Potential cross-links found in classes.dex','',
        '**Important:** these are raw DEX string occurrences only. They do NOT establish actual invoke/startActivity/bindService calls.','',
        '| Source APK | Matched indicator | Count |','|---|---|---:|']
for e in xref:lines.append(f"| {e['source_apk']} | {e['needle_name']} | {e['count']} |")
lines+=['','## Need runtime/dex callsite analysis','',
        'For each target service/component, resolve exact invoke instructions, binder descriptor, intent action, permission and Side effects; compare original 8054 vs modified v33; test on physical device before disabling.', '']
(OUT/'STATIC_APK_DEPENDENCIES_8054.md').write_text('\n'.join(lines),encoding='utf-8')
print(json.dumps(dict(apks=len(records),components=len(components),permissions=len(permissions),xrefs=len(xref),errors=[r['apk_path'] for r in records if not r['package']][:35]),ensure_ascii=False))
