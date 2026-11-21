#!/usr/bin/env python3
"""8054 exact Factory.apk: read-only static inventory of screens, callbacks and vendor calls."""
import argparse
import collections
import csv
import json
import pathlib
import re
import xml.etree.ElementTree as ET

NAMES = ("FactoryMenuActivity","DesignMenuActivity","FactoryDolbyActivity",
"FactoryDTSActivity","AdvancedEffectActivity","AdvancedEffectDapViewHolder",
"PictureModeAdjustViewHolder","PEQAdjustViewHolder","FactoryMemcActivity",
"WBAdjustViewHolder","NonLinearAdjustViewHolder","NonStandardAdjustViewHolder",
"OtherOptionAdjustViewHolder","FactoryMenuViewHolder","DesignMenuViewHolder",
"OverScanAdjustViewHolder","PanelInfoViewHolder","SSCAdjustViewHolder",
"AUDIO_nonStan","TestImagePatternsActivity","FactoryPqUpdateActivity",
"AdvancedEffectViewHolder","FactoryProgramPresetActivity","FactoryKeyUpgradeActivity",
"ExecuteShellActivity","FactoryCameraActivity","VIF","VD","ADCAdjustViewHolder",
"UrsaInfoViewHolder","MicViewHolder","IPEnableMappingViewHolder")
AREAS={
"PQ/HDR/Dolby Vision":("picture","nonlinear","wbadjust","overscan","pq","panel","hdr","dolbyvision"),
"MEMC":("memc","mjc","motion"),
"Audio/Dolby/DTS/EQ":("audio","sound","peq","eq","dts","dap","dolby","advancedeffect"),
"Factory IO/calibration":("ssc","vif","demod","adc","ursa","camera","upgrade","shell"),
}
SETS=re.compile(r"\b(?:\w+\.)?(?:set|Set|write|Write|save|Save|update|Update|apply|Apply|put|Put)[A-Z]\w*\s*\(")
GETS=re.compile(r"\b(?:\w+\.)?(?:get|Get|read|Read|query|Query|is|Is)[A-Z]\w*\s*\(")
CALLS=re.compile(r"\b(?:MtkTv\w+|IMtkTv\w+|Tv\w+|TV\w+|Settings\.Global|Settings\.System|TVSettingConfig|PreferenceConfigUtils)\b")
UI=re.compile(r"\b(?:onClick|onPreferenceChange|onItemSelected|onCheckedChanged|onFocusChange|onCreate|onResume|onPause|onStart|onStop|onValueChange)\s*\(")
DV=re.compile(r"dolby[\W_]*vision|\bdovi\b|dolbyvision|\bdv[-_](?:mode|enable|flag|setting)",re.I)
HDR=re.compile(r"\bhdr10?\b|\bhlg\b",re.I)
SECRET=re.compile(r"password|private|keybox|hdcp|widevine|certificate|secret|serialno|api[_-]?key|token",re.I)
METHOD=re.compile(r"^\s*(?:public|protected|private|static|final|synchronized|\s)*(?:[\w\[\]<>?,.]+\s+){1,3}([A-Za-z_]\w*)\s*\([^;]*\)\s*(?:throws\s+[^\{]+)?\{")
LITERAL=re.compile(r'"([^"\r\n]{2,90})"')
def area(name):
    s=name.lower()
    for group,terms in AREAS.items():
        if any(t in s for t in terms):return group
    return "Other"
def sanitize(s):
    s=s.strip()
    if len(s)>250 or SECRET.search(s) or re.search(r"[A-Za-z0-9+/]{48,}",s):return ""
    if any(k in s.lower() for k in ("gpt clean","partition erase","rm -rf","execute(","system(")):return ""
    return s[:230]
def csvout(path,headers,rows):
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.writer(f);w.writerow(headers);w.writerows(rows)
def inspect(jadx,res,out):
    root=jadx/"sources"
    alljava=sorted(root.rglob("*.java"))
    owners=[p for p in alljava if "mediatek/tvsetting/factory/ui" in p.as_posix()]
    focus=[p for p in owners if p.stem in NAMES]
    classlist=[(area(p.stem),p.relative_to(root).as_posix()) for p in owners]
    events=[]; dv=[]; hdr=[]; screens={}
    for p in alljava:
        if p.stat().st_size>700000:continue
        rel=p.relative_to(root).as_posix()
        if not ("mediatek/tvsetting" in rel or "mediatek/twoworlds" in rel):continue
        lines=p.read_text(errors="replace").splitlines()
        if p in focus:
            methods=[];calls=[];literals=[]
            for i,s in enumerate(lines,1):
                if (m:=METHOD.search(s)):methods.append((m.group(1),i))
                if (CALLS.search(s) or SETS.search(s) or UI.search(s) or
                    re.search(r"setOnClick|setOnItem|setOnChecked|R\.(?:array|string|id)|setAdapter|setEntries",s)):
                    value=sanitize(s)
                    if value:calls.append((i,value))
            for s in LITERAL.findall("\n".join(lines)):
                v=sanitize(s)
                if v and len(v)>2 and v not in literals:literals.append(v)
            screens[p.stem]={"path":rel,"line_count":len(lines),"methods":methods[:200],
                             "callsite_candidates":calls[:220],"literal_candidates":literals[:100]}
        for i,s in enumerate(lines,1):
            if DV.search(s):
                v=sanitize(s)
                if v:dv.append((rel,i,v))
            if HDR.search(s):
                v=sanitize(s)
                if v:hdr.append((rel,i,v))
            if p in owners:
                typ=("SETTER" if SETS.search(s) else "GETTER" if GETS.search(s)
                     else "UI_CALLBACK" if UI.search(s) else "API_TYPE" if CALLS.search(s) else None)
                if typ and (CALLS.search(s) or p in focus):
                    v=sanitize(s)
                    if v:events.append((area(p.stem),rel,i,typ,v))
    labels=[]
    if res.is_dir():
        for p in sorted(res.rglob("*.xml")):
            if not any(k in p.as_posix() for k in ("/values","/layout","/xml")):continue
            try:xml=ET.parse(p).getroot()
            except Exception:continue
            for e in xml.iter():
                if e.tag not in ("string","item","string-array","integer-array","array"):continue
                name=e.get("name","")
                v=" ".join(" ".join(e.itertext()).split())[:200]
                if sanitize(name) and sanitize(v): labels.append((p.relative_to(res).as_posix(),e.tag,name,v))
    out.mkdir(parents=True,exist_ok=True)
    csvout(out/"FACTORY_CLASSES_8054.csv",("area","source"),classlist)
    csvout(out/"FACTORY_BACKEND_CALLS_8054.csv",("area","source","line","heuristic","snippet"),events)
    csvout(out/"FACTORY_RESOURCE_LABELS_8054.csv",("xml","type","name","display_value"),labels)
    csvout(out/"FACTORY_DOLBY_VISION_8054.csv",("source","line","snippet"),dv)
    csvout(out/"FACTORY_HDR_8054.csv",("source","line","snippet"),hdr)
    (out/"FOCUS_SCREEN_METHODS_8054.json").write_text(json.dumps(screens,ensure_ascii=False,indent=2),encoding="utf-8")
    md=[
    "# MediaTek Factory Menu 8054 — полный статический обзор декомпилированного UI",
    "",
    "Источник: точный OEM Factory.apk из подтверждённого backup FlixTone 8054. Анализ только на CI, без записи на устройство.",
    "Ограничение: декомпилированный метод и текст меню не доказывают runtime видимость, лицензии или физический эффект на конкретном профиле.",
    "",
    "## Охват",
    "- Всего декомпилировано Java: "+str(len(alljava)),
    "- Собственных Java классов Factory UI: "+str(len(owners)),
    "- Детально обследованы основные UI компоненты: "+str(len(focus)),
    "- Найдено кандидатов UI/API вызовов: "+str(len(events)),
    "- XML resource labels: "+str(len(labels)),
    "- Dolby Vision/DOVI references: "+str(len(dv)),
    "- HDR/HLG references: "+str(len(hdr)),
    "",
    "## Полный перечень Factory UI классов по направлениям",
    ]
    by=collections.defaultdict(list)
    for group,path in classlist:by[group].append(path)
    for group,files in by.items():
        md+=["### "+group,""]+["- "+p for p in files]+[""]
    md+=["## Проверка Dolby Vision/DOVI (ВИДЕО, не Dolby DAP audio)",""]
    if dv:
        md+=["- "+p+":"+str(i)+" — "+s for p,i,s in dv[:180]]
    else:md+=["Буквальных упоминаний Dolby Vision/DOVI в Java не обнаружено. Native/ресурсный путь отдельно.",""]
    md+=["","## Подробности главных экранов и обработчиков",""]
    for name,item in screens.items():
        md+=["### "+name,"", "Файл: "+item["path"]+"; строк: "+str(item["line_count"]),"",
              "**Обнаруженные методы (строка):**"]
        md+=["- "+name+"() : "+str(n) for name,n in item["methods"][:120]]
        md+=["","**Текстовые подписи / идентификаторы (кандидаты):**"]
        md+=["- "+x for x in item["literal_candidates"][:60]]
        md+=["","**UI callbacks и API вызовы (строка: исходная инструкция):**"]
        md+=["- "+str(n)+": "+v for n,v in item["callsite_candidates"][:155]]
        md+=[""]
    md+=["## Что это исследование не позволяет делать","",
       "- Не объявлять factory-only WB, PEQ, MEMC calibration, Dolby vendor переключатели потребительскими функциями без OEM capability.",
       "- Не менять с Factory UI заводские PQ tables, ключи, EEPROM, настройки мотора, HDMI/CEC и тестовые паттерны в ходе анализа.",
       "- Следующий шаг: сопоставить обработчики KuSettings и stock Android TV, затем выполнить реальный read-only обход видимых экранов.",
       "",
       "## Структурированные приложения",
       "- FACTORY_CLASSES_8054.csv",
       "- FACTORY_BACKEND_CALLS_8054.csv",
       "- FACTORY_RESOURCE_LABELS_8054.csv",
       "- FACTORY_DOLBY_VISION_8054.csv",
       "- FACTORY_HDR_8054.csv",
       "- FOCUS_SCREEN_METHODS_8054.json",""]
    (out/"FACTORY_DEEP_AUDIT_8054.md").write_text("\n".join(md)+"\n",encoding="utf-8")
    print(json.dumps({"java_total":len(alljava),"owner_classes":len(owners),
      "focus":len(focus),"events":len(events),"labels":len(labels),"dolby_vision_refs":len(dv),
      "hdr_refs":len(hdr),"files":{x.name:x.stat().st_size for x in out.iterdir()}},ensure_ascii=False))
    print("DOLBY_VISION_PREVIEW",json.dumps(dv[:16],ensure_ascii=False))
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--jadx",type=pathlib.Path,required=True)
    p.add_argument("--resources",type=pathlib.Path,required=True)
    p.add_argument("--out",type=pathlib.Path,required=True)
    a=p.parse_args()
    inspect(a.jadx,a.resources,a.out)
