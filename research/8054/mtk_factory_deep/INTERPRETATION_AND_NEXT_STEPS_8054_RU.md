# Exact 8054: MediaTek Factory Menu — выводы глубокого статического аудита

Дата: 21 ноября 2026. Источник: заводской Factory.apk, SHA256 2f0e2cbc133c97cb4b1383f7a4576fab78715dae72a8e590deb479a4196e0996, извлечённый из подтверждённого owner-архива FlixTone_8054_Backup.zip. Успешная проверка: https://github.com/MAX-TAC/FlixTone_8054_Backup/actions/runs/44948075112

**Этот документ описывает реальные методы и ссылки из декомпиляции, но не является инструкцией по настройке Factory Menu.** Никаких изменений на проекторе в ходе аудита не выполнялось. Runtime видимость, поддержка функции конкретным SoC/SKU и физический эффект должны проверяться отдельно.

## 1. Что именно было сделано

- Из точного RAW super.img извлечён оригинальный Factory.apk, его SHA256 записан выше.
- JADX 1.5.6 декомпилировал 1866 Java-файлов, среди них 52 собственных класса/контроллера package mediatek.tvsetting.factory.ui (а не 352 «собственных» — 352 из старого аудита включали многочисленные связанные SDK-классы).
- Проверены методы и UI/backend callsite 32 важных собственных экранов/контроллеров.
- Собраны 2346 кандидатов API, GUI callback, getter/setter (эвристика: наличие вызова в исходнике не доказывает, что он достижим).
- Декодированы XML ресурсы Factory.apk; найдено 958 записей (учитываются повторы разных языковых ресурсов).
- Сформированы отдельные CSV для классов, вызовов, ресурсных строк, Dolby Vision и HDR и JSON с методами/исходными инструкциями.
- **Осталось:** развёрнуть call graph для всех условий customer/capability, сопоставить живые экраны с XML, проверить физические эффекты на настоящем проекторе 8054. Это нельзя установить статически на 100%.

## 2. Подтверждённая структура двух основных инженерных ветвей

### DesignMenuActivity — главное инженерное Design меню

Обработчик onClick() имеет точные маршруты (номера ViewFlipper — внутренние индексы представлений):

| Выбор в Design Menu | Кодовая цель |
|---|---|
| Picture Mode | PictureModeAdjustViewHolder, child=1 |
| Non-linear | NonLinearAdjustViewHolder, child=2 |
| Non-standard | NonStandardAdjustViewHolder, child=3 |
| SSC | SSCAdjustViewHolder, child=4 |
| PEQ | PEQAdjustViewHolder, child=5 |
| Panel Info | PanelInfoViewHolder, child=6 |
| Other Options | OtherOptionAdjustViewHolder, child=7 |
| Test Pattern | TestPatternViewHolder, child=8 |
| Advanced Effect | AdvancedEffectActivity |
| Factory Menu | отдельная FactoryMenuActivity |
| Execute Shell | явный инженерный диалог; не открывать в пользовательском тесте |
| Exit | выход из меню |

Основные evidence: FOCUS_SCREEN_METHODS_8054.json → DesignMenuActivity, onClick 124–240.

### FactoryMenuActivity — вторая ветвь Factory Menu

| Выбор | Кодовая цель |
|---|---|
| ADC | ADCAdjustViewHolder |
| White Balance | WBAdjustViewHolder |
| Overscan | OverScanAdjustViewHolder |
| Other | OtherOptionForFactory |
| Info | InfoViewHolder |
| Keystone calibration | отдельный OEM-компонент |
| Temperature control | отдельный OEM-компонент |
| Live TV | отдельный OEM-компонент |

Evidence: FactoryMenuActivity.onClick 41–120 и registerListeners 157–165.

**Не путать** две ветви Menu с обычными настройками Android TV и китайским com.my.settings: Factory.apk — отдельный пакет mediatek.factorymenu.ui.

## 3. Изображение, HDR, Dolby Vision и режимы PQ

**Ресурсы Factory реально содержат следующие названия профилей:**
- User, Cinema, Sport, Vivid, Hi Bright;
- Dovi Bright, Dovi Dark;
- Standard, Natural, Movie, Game, Energy Saving, AI PQ;
- Dolby Vision Vivid, Dolby Vision_Game;
- варианты с пометкой HDR10 (внутри того же массива str_arr_pic_mode_vals).

Это список строк factory resource, **не доказанная доступность всех перечисленных режимов на 8054**. Массив может быть общим для нескольких SoC/профилей OEM.

**В MediaTek API найдены:**
- ACFG_MSG_ENTER_DOLBY_VISION = 20;
- ACFG_MSG_QUITE_DOLBY_VISION = 21 (опечатка QUITE сохранена из оригинала);
- CFG_VIDEO_GLOBAL_DIMMING_SWITCH = g_video__vid_dolby_vision_global_dimming_switch.

Это подтверждает ветвления и имена конфигураций в ПО. Плюс прежний независимый трассировочный отчёт stock Android TV PictureFragment показывает Dolby Vision handling в onResume:
https://github.com/MAX-TAC/Projector-Soft/blob/audit/8054-tvsettingsplus-20261117/research/8054/PICTURE_BLOCK_STATUS_8054.md

**Не доказано:** активный Dolby Vision decoder/renderer, лицензия, EDID DV capability, соответствие телевизионного режима оптическому тракту, видимый пункт или реальное переключение DV на HDMI 8054.

**PictureModeAdjustViewHolder** (код метода onCreate/onKeyDown) оперирует отличающимися от обычного consumer slider величинами:
- mTvFApiDisplay.getPictureModeDefaultCfg(enum picture mode, enum input source, enum NonLinearPqType);
- mTvFApiDisplay.setPictureModeDefaultCfg(..., BACKLIGHT/BRIGHTNESS/CONTRAST/SATURATION/HUE/SHARPNESS, value);
- при выборе пресета mTvConfig.setConfigValue(g_video__picture_mode, index).

Это **factory preset defaults для пары picture mode + input source**, а не просто Global.picture_contrast в рамках текущего пользовательского профиля. Не копировать factory setter в обычный MOD-ползунок.

**NonLinearAdjustViewHolder** читает/пишет 5-точечную кривую v0, v25, v50, v75, v100 для BRIGHTNESS/CONTRAST/SATURATION/SHARPNESS/HUE/BACKLIGHT, а также ветвь Volume со входом/выходом. Вызовы MtkTvFApiDisplay.getNonLinearPqCurve/setNonLinearPqCurve относятся к калибровочной карте. Редактирование может влиять на многие уровни сразу, не пользовательский slider.

**WBAdjustViewHolder** содержит отдельную коррекцию white balance по source, color temperature и picture mode, параметры gain/offset RGB и вызов saveWbGainOffsetEx2(). Также в нём есть callback источника видеосигнала. Это **не** эквивалент пользовательских RGB настроек; копировать эти заводские gain/offset нельзя.

**MEMC:** FactoryMemcActivity имеет Off/Low/Middle/High и использует MtkTvConfig.setConfigValueForAllElements(g_video__vid_mjc_effect, index), а сброс — setConfigValue(g_video__vid_mjc_effect,0,6). Слово ForAllElements и аргумент 6 означают иной scope и требуют статического разбора перед переносом. Пользовательскому TvSettingsPlus следует оставить штатный Android TV MJC/MEMC обработчик, подтверждённый владельцем, а не переписать его factory вызовом.

**Overscan:** OverScanAdjustViewHolder позволяет выбрать источник и Right/Left/Top/Bottom, применяя mTvAVMode.setCrntOverscan и Customize.setOverScan(input type, screen mode, 4 values). Это source/format-dependent и затрагивает границы кадра, поэтому обычная настройка масштабирования должна идти через stock DisplayModeActivity или специально подтверждённый consumer обработчик.

## 4. Звук, Dolby и эквалайзеры

**Наблюдение владельца на живом 8054:** китайские пресеты, bass/treble/EQ не дают ожидаемого изменения при выводе на Bluetooth-саундбар, но действуют на внутренние динамики. Это hardware-observation с одним BT-устройством. Не экстраполировать на весь HDMI ARC/SPDIF/BT стек и не считать Settings.Global echo подтверждением DSP эффекта.

**Factory AUDIO_nonStan** имеет отдельные selectors:
- Audio input source: DTV, ATV, HDMI, CVBS, MM;
- Output types: SPDIF, HDMITX, SPEAKER, HEADPHONE, LINEOUT, HDMIARC, SCART, а в массиве NonLinear также ALL, LR, MAIN_SPEAKER, HDMI_TX;
- Prescale по input/output; Speaker Delay Default Offset; NR Threshold; TV sound mode; Dolby processing mode.
- Прямые getter/setter MtkTvFApiAudio.getPrescaleByAudioSource, setPrescaleByAudioSource, getSpeakerDelayDefaultOffset, setSpeakerDelayDefaultOffset, setNrThreshold, saveAudioIni() и TVConfig setters.

Имеющиеся перечисления не показывают BT output в данном factory submenu, но **это не доказывает**, что весь MediaTek backend не умеет Bluetooth. Это хороший повод сделать в MOD route-aware user controls.

**PEQAdjustViewHolder:** доказано 13 полос, индекс 0..12, профиль EnumSoundMode, get/setPeqFreq/Gain/Q/Type, get/setPEQEnable и saveAudioIni(). Это отдельный factory parametric EQ, не пользовательский 5-band EQ через Settings.Global.sound_equalizer_detail_*. Предыдущий repo-аналитический отчёт по PEQ:
https://github.com/MAX-TAC/Projector-Soft/blob/audit/8054-tvsettingsplus-20261117/research/8054/AUDIO_ADVANCED_ROUTES_8054.md

**FactoryDolbyActivity** — в первую очередь аудио:
- CFG_AUD_DOLBY_CERT_MODE (Banner);
- CFG_AUD_DOLBY_CMPSS (Compression);
- CFG_AUD_DOLBY_DRC (CompressionFactor).
Это не переключатель Dolby Vision, не доказательство лицензии Atmos.

**FactoryDTSActivity**: getDtsLoundnessEnable / setDtsLoundnessEnable. Не приравнивать к пользовательской настройке DTS при неподдерживаемом output.

**AdvancedEffectDapViewHolder**: конфигурация g_audio__dolby_audio_processing, g_audio__dolby_sound_mode и множество Dolby DAP компонентов (bass, virtual bass, GEQ, IEQ, regulator, volume leveler, surround virtualizer и др.) через Factory MtkTvFApiAudio, Customize.setDolbyDapParam, saveAudioIni.
Допустимые подписанные строки режимов DAP в factory XML: Off, Auto, Movie, Music, Game, News, Night, Voip, Standard, Stadium, User.
В ресурсе есть предупреждение, что текущий звуковой профиль не поддерживает DAP, и требуется Movie/Music/Game/News/Standard/Stadium/User. Следовательно, **режимные ограничения есть в оригинальном UI**; перенос без них небезопасен.

**GEQ DAP и factory PEQ:** ресурсы содержат отдельно GeqEnable, GeqNbBands (1..20), GeqBandCenter/Target, BassBoost/Cutoff/Width, VirtualBass и SuroundBoost. Это factory DAP coefficients/processing, не 5-band user EQ.

## 5. Прочие интересные, но потенциально опасные функции

OtherOptionAdjustViewHolder содержит **реальные вызовы**:
- Wake-on-LAN Ethernet: MtkTvNetwork.setEthernetWolCtl;
- Wake-on-LAN Wi-Fi: MtkTvNetwork.setWifiWolCtl;
- xvYCC: CFG_VIDEO_VID_XVYCC;
- MFC level: MtkTvFApiDisplay.setMfcLevel; resource labels Off/Low/Mid/High/Bypass;
- Flip/Mirror: CFG_MISC_EX_FLIP и CFG_MISC_EX_MIRROR;
- FactoryPowerMode: MtkTvFApiSystem.setFactoryPowerMode;
- UART factory port, watchdog, stream time sync;
- Factory reset (отдельный обработчик), PQ update, keys, shell и test patterns.

**Возможные будущие user features:** только те, что выдержат проверку реальной поддержки железом, readback, понятного safe revert и связи с consumer capabilities. Например WOL, xvYCC и MFC пока **предмет исследования**, не готовые переключатели MOD. Factory watchdog, UART, shell, ключи, FPGA/URSA update, калибровки исключаются из consumer UI.

FactoryMenuActivity содержит также отдельные OEM intents keystone calibration, temperature control и LiveTV. Наличие UI входа не оправдывает вызов factory motor/fan calibration из обычного MOD.

## 6. Как соотносятся три программы (предварительное сравнение, без полного audit KuSettings)

| Приложение | Путь изменения | Значение |
|---|---|---|
| Factory.apk | MtkTvFApi* / MtkTvConfig / Customize → MTK factory config/service | Может менять factory defaults, калибровки, source-specific tables |
| com.my.settings (KuSettings) | OEM user controller → Settings.Global / сервисы, собственные OEM компоненты | Китайский user GUI, часть фоновых сервисов обязательна |
| com.android.tv.settings (оригинал и MOD) | stock Picture/Sound fragments → PreferenceConfigUtils → Settings.Global → TVMenuSettingsService → TVSettingConfig → MTK | Consumer API и профильная OEM проверка; предпочтительный путь для MOD |

Три интерфейса могут обращаться к общим backend config IDs, **но не обязаны читать/писать одно и то же значение или одни и те же входы/профили**. Factory preset default, per-input calibrations и user current PQ — разные сущности. Поэтому не копировать setter Factory в MOD только потому, что подписи похожи.

## 7. Что проверить на устройстве

Для подтверждения реального дерева пунктов и доступности используются только **ручной обход без изменения значений** и ADB screenshots/foreground capture. Подготовлен Windows PowerShell скрипт:
[collect_8054_mtk_factory_ui_windows.ps1](../../../tools/collect_8054_mtk_factory_ui_windows.ps1)

- Пользователь открывает Factory Menu штатным способом и вручную переходит по каждому видимому подразделу.
- Перед снимком вводит краткое имя текущего экрана; скрипт записывает PNG, timestamp, focused Activity и разрешённые Settings.Global key values.
- Нет ADB keyevent, Settings put, root, remount, save, reset или flash. Скрипт не запускает Factory-классы автоматически.
- Даже простой вход в Factory UI иногда может иметь побочные эффекты и настраивать видеоисточник; не посещать Execute Shell, Calibration, Factory Update, Key Upgrade, Watchdog и сервисные Reset, если до входа неизвестны side effects.
- Скриншоты могут содержать серийные номера/калибровки; они остаются локально и не отправляются автоматически.

**Пока не установлены:** реальная Dolby Vision поддержка, какие скопированные пункты работают на 8054, все контексты HDMI/SDR/HDR и аудиовыходов, изменяет ли открытие отдельных страниц состояние системы. Нужна отдельная квалификация.

## 8. Критерии завершения этапа MTK и начало следующего этапа KuSettings

Сформировать реестр по каждому видимому пункту:
1. Design/Factory путь и Activity/Holder, конкретный resource, condition/gating.
2. Getter, setter, enum/range, input/picture mode/audio output scope, effect side effects, persist.
3. Состояние на exact-8054: PRESENT, HIDDEN_BY_CONFIG, FACTORY_ONLY, UNSUPPORTED, UNVERIFIED.
4. Есть ли аналог в stock Android TV и в KuSettings; если есть — одинаков ли setter и storage key.
5. Потенциал переноса в MOD: REUSE_STOCK, SAFE_NEW_USER_CONTROL, READONLY, FACTORY_EXCLUDED.
6. План теста, оригинальные значения и обратимый restore.

**Только после этого — отдельный полный обзор каждого тумблера KuSettings**: исходное onClick/onCheckedChange, setter/getter, диапазоны, проверка readback, затем единая матрица KuSettings → stock AndroidTV → Factory → TvSettingsPlus MOD.
