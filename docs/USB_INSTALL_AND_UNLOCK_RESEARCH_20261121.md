# 8054: установка кастомной RUIOS без компьютера, USB-автообновление и разблокировка

Дата исследования: **21.11.2026**. Цель: сделать пользовательскую кастомную RUIOS 8054 устанавливаемой без ПК и специфического USB-A↔USB-A кабеля **после явного согласия владельца устройства**. Все выводы отделяют наблюдения на реальном 8054 от признаков в бинарном MBOOT и от аналогий с другими моделями.

## Краткий вывод

1. **Реально подтверждено**: проектор 8054 разблокируется штатным `fastboot flashing unlock` (USB host Windows), после чего Android успешно загружается как `unlocked/orange`.
2. **Сильное статическое свидетельство**: exact-8054 MBOOT содержит USB-автообновление и сценарную обработку `mtkupgrade`. OEM factory image с 2×HDMI несёт собственный встроенный shell-like upgrade script.
3. **Пока не доказано**: что произвольный `*.txt` рядом с образом на USB будет прочитан MBOOT и сможет менять AVB device state, или что неизвестный пользователю кастомный `super` будет принят оригинальным USB package verifier. Файлы-маркеры у других проекторов **не** являются подтверждением для 8054.
4. **Реалистичные способы распространения без ПК**: (a) штатный USB updater с правильно собранным и принятым OEM package, если его подпись/политика позволят; (b) приложение-установщик в загруженной Android через stock signed OTA, если поддержка будет доказана; (c) Android-телефон в роли USB Fastboot host по OTG (**без ПК, но с кабелем и экраном подтверждения**); (d) потенциально U-Boot Fastboot по UDP через LAN — бинарная поддержка есть, рабочая точка входа и security не подтверждены.
5. **Нельзя публиковать** «флешку, которая автоматически на любом locked-проекторе разблокирует и перезапишет загрузчик» без подтверждения подлинности пакета, согласия владельца, защиты от подмены и контролируемого восстановления. При штатной модели Android разблокировка должна сопровождаться подтверждением владельца и может стирать user data.

## 1. Фактический сценарий USB upgrade внутри MBOOT 8054

Исходник: **не generic U-Boot**, а точный образ `mboot_a.img` из owner backup, SHA256
`ebf9a0adef859f568d792d182f4ace08d026a27dc7f322bab735c67b07cd34c1`.

Повторяемый offline static scan:
- [GitHub Actions, exact 8054 MBOOT strings](https://github.com/MAX-TAC/FlixTone_8054_Backup/actions/runs/43902935064);
- [Deep audit MBOOT/uenv](https://github.com/MAX-TAC/FlixTone_8054_Backup/actions/runs/43899264633);
- [tools/inspect_8054_mboot_avb_unlock.py](../tools/inspect_8054_mboot_avb_unlock.py);
- [tools/deep_audit_8054_stock.py](../tools/deep_audit_8054_stock.py).

**Выписанные точные литералы:**

```text
do_check_usb_auto_upgrade
check_usb_auto_upgrade
Not find usb_auto_upgrade in env, open & do USB auto-upgrade now!!!
usb_auto_upgrade = %s
do_mtkupgrade
mtkupgrade usb
mtkupgrade usb %s
PKG format default file name is /MTKUpgrade.bin
- ex: mtkupgrade usb
- ex: mtkupgrade usb CusUpgrade.bin
- ex: mtkupgrade usb -script
- ex: mtkupgrade usb -script [[mboot
usb start;mtkupgrade usb
/MTKUpgrade.bin
upgrade_image.pkg
This upgrade_image.pkg version is older than current version.
Unrecognized mtkupgrade usb parameters!!!
```

`-script` — **реально скомпилированная строка помощи загрузчика**, значит сценарный режим заслуживает глубокого анализа. Но **неясно**, какой файл в нём разрешён, применяется ли AES/RSA подпись, откуда берётся script body, может ли это быть внешний `*.txt` или лишь встраиваемый encrypted script из PKG. Последовательность символов после `-script [[mboot` в распечатке неполная; **не додумывать синтаксис**.

В `uenv.img` из архивной копии офлайн-проверка показала `verify=n` и `devicestate=lock`, `bootdelay=0`; отсутствовали standalone `auto_upgrade` и `upgrade_cmd` как NUL-delimited key/value. Из `verify=n` **нельзя** заключить, что package authentication / AVB полностью отключены. U-Boot environment может в точности отличаться от текущего после Fastboot unlock — не переписывать его вслепую.

**Статус:** `USB_UPGRADE_HANDLERS_PRESENT / SCRIPT_MODE_PRESENT / EXTERNAL_TEXT_SCRIPT_UNPROVEN / UNLOCK_FROM_USB_UNPROVEN`.

## 2. Особенно важная находка: заводская PKG 2×HDMI *блокирует* загрузчик

В **другом, уже существующем репозитории владельца** хранится реальный расшифрованный OEM upgrade command script из factory package для **CineLux с 2 HDMI**:

[analysis/Original_Firmware/decrypted/upgrade_script.txt](https://github.com/MAX-TAC/Everycom-Cinelux-Firmware/blob/main/analysis/Original_Firmware/decrypted/upgrade_script.txt)

В нём, ближе к завершению:

```text
setenv verify n
setenv devicestate lock
setenv usb_auto_upgrade enable
setenv force_boot_recovery false
setenv autoload 0
...
saveenv
```

Также присутствуют команды `gpt clean mmc 0`, создание GPT заново, многочисленные `partition erase`, запись `mboot_a/b`, `vbmeta_a/b`, `optee_a/b`, `super`, `tvservice`, `factory`, `persist`, `private`, `bootdata`, `tvconfig`, `project_id`, и `wipeuserdata`/операция с `eeprom_a`.

**Это не пакет для безопасной пользовательской установки Custom RUIOS!** Установка заводского PKG «как есть» потенциально затронет уникальные калибровки, ключи и разметку, а также переведёт `devicestate` в `lock` при модифицированной системе. Ошибочный порядок записи/блокировки может вызвать boot failure/brick.

**Что это доказывает:** OEM updater в доверенном packaged script умеет менять U-Boot `devicestate` и включать USB auto-upgrade. **Чего не доказывает:** что файл `unlock.txt` на флешке обойдёт проверки OEM PKG и станет выполняемой командой при обычном включении, либо что изменение переменной в `uenv` эквивалентно поддерживаемой операции `fastboot flashing unlock`.

**Для пользовательского релиза:** применять whitelist изменения конкретных разделов, не включать GPT clean, eMMC boot areas, factory calibration, сертификаты, `mboot`, `optee` и любые автоматические `devicestate lock`. Должна быть доказана авторизация OEM package и возможность recovery.

## 3. Что могли видеть владельцы других проекторов как «текстовый файл рядом с прошивкой»

В открытых источниках есть **несколько несовместимых механизмов**:

| Пример | Файл и смысл | Отношение к 8054 |
|---|---|---|
| Allwinner H713 (Magcubic HY310, L018) | `update/auto_update.txt` с командой `sunxi_flash ...`: loader этого SoC читает отдельный текстовый сценарий | **Другая платформа**, не переносить буквально |
| Некоторые XGIMI (Lumen OS recovery) | Пустой `factory.txt` рядом с именованным OEM *.bin — это триггер режима заводского восстановления | **Файл-маркер**, а не разблокировка fastboot и не универсальное выполнение shell |
| MTK/MStar U-Boot / PKG | `MTKUpgrade.bin` / `upgrade_image.pkg`, script встроен в контейнер или вызывается через `mtkupgrade` | **Ближайшая архитектура к 8054**; exact внешний `*.txt` ещё не доказан |

См. [Allwinner USB examples](https://github.com/well0nez/magcubic-root), [Lumen XGIMI factory.txt procedure](https://github.com/Project-Lumen-OS/lumen-os/blob/main/docs/install/hb/en.md), [AOSP lock/unlock guidance](https://source.android.com/docs/core/architecture/bootloader/locking_unlocking).

**Результат поиска именно «Everycom CineLux 2×HDMI + отдельный TXT unlock»:** достоверного инструкции с подтверждённым именем файла, его содержимым и логом выполнения на **таком же MBOOT** пока не найдено. По исходникам MBOOT режим сценария существует, но текстовый спутник прошивки ещё **гипотеза**, а не рецепт установки.

## 4. Обнаружена ещё одна потенциальная дорога: Fastboot по UDP

В точном `mboot_a.img` присутствуют строки:

```text
fastboot usb 0
fastboot udp error: %d
Listening for fastboot command on %pI4
run as a fastboot usb or udp device
```

Стандартный U-Boot может слушать Fastboot over UDP (обычно 5554/udp) и host fastboot умеет адрес `udp:IP:port`. См. [U-Boot Fastboot](https://docs.u-boot.org/en/latest/android/fastboot.html), [U-Boot Kconfig UDP](https://android.googlesource.com/platform/external/u-boot/+/e25919d3a133b78691b7287db3f461db74be0562/drivers/fastboot/Kconfig).

**Но:** на 8054 наблюдался **только USB Fastboot**: `is-userspace=no` в bootloader, `fastboot devices` через прямой USB. Не установлено, что `adb reboot bootloader` включает Ethernet/UDP Fastboot, что IP/PHY bootloader вообще инициализирует сеть, что Wi-Fi работает на этой ранней стадии (почти наверняка нет, пока не доказано), или что интерфейс не уязвим к постороннему управлению. Поэтому **не рекомендовать публично UDP-unlock по сети**, пока нет отдельного доказательства и модели безопасности. Для пользователя без ПК сеть по Ethernet могла бы стать альтернативой, но это низкодостоверная гипотеза.

## 5. Реальные способы установки без Windows-компьютера

| Способ | Требует ПК | Требует кабель | Достоверность для 8054 | Риски/ограничения |
|---|---|---|---|---|
| OEM USB auto-update подписанным/совместимым PKG | Нет | Только USB-flash | Механизм в MBOOT **static confirmed**, установка custom **untested** | Package signature, anti-rollback, модель, перечень записываемых разделов |
| Android-приложение с локальным обновлением/OTA | Нет | Необязательно | **NOT VERIFIED** для exact-8054 и кастомного пакета | Требования OEM подписи, current update_engine/payload policy, boot consistency |
| Android-телефон как USB host + Fastboot OTG | Нет | **Да**, OTG + USB к проектору | USB Fastboot target подтверждён, phone host **untested** | Драйверы USB host/API, доступ приложения к USB, физическое подтверждение unlock, пользовательские данные |
| Fastboot over UDP/Ethernet | Нет при Android-host инструменте | Ethernet/LAN | Строки реализации **static only** | Инициализация bootloader LAN, режим прослушивания, аутентификация/изоляция сети |
| Один `unlock.txt` на USB при boot | Нет | Только USB-flash | **NOT SUPPORTED BY EVIDENCE** | Нет установленного consumer-facing trust/confirmation path; risk unintended unlock |
| Замена лаунчера и IME через пользовательский APK | Нет | APK-файл через USB/сеть | Обычно возможна как установка приложений, но системные override могут требовать спецправ | Домашняя Activity default handler, IME enable, привилегии, Android UI compatibility |

**Наиболее перспективный UX:** сначала проверить возможность **обновлять системный раздел через OEM signed OTA с живой Android**, и отдельно — **заводской USB boot installer, который автоматически определяет exact 8054 и подтверждает подпись/совместимость**, но **не меняет devicestate без явного действия пользователя**. Телефон + OTG — безопаснее как запасной путь для технически подготовленных пользователей.

## 6. Безопасный план дальнейшего исследования (без запусков незнакомых USB-скриптов)

**Фаза A — OFFLINE, без воздействия на пользовательские устройства:**

1. Сравнить `mtkupgrade` parser в exact `mboot_a.img` с расшифрованным `upgrade_image.pkg` и установить точный источник script bytes: AES encrypted segment внутри пакета, `-script` external file или другой тип; call-site/branch-level доказательство, не только `strings`.
2. Выявить допустимые имена USB entrypoint и auto-trigger. Не дописывать гипотетический `unlock.txt` в instructions до выяснения загрузочного кода.
3. Проверить цепь доверия: RSA/AES проверки PKG, version rollback, проверки `ro.rjpj.machine.id`/DTBO, preflash compatibility, наличие подтверждения физического владельца.
4. Проверить локальный updater RUIOS/`RuiYunOta`, `update_engine` и условия подписи для exact 8054. OTA payload testkey 8052/8053 **не** гарантирует приём 8054.
5. Разработать *read-only* verifier/manifest для релиза: whitelist целевых разделов; SHA256; dry-run; блокировку несовместимых ID; исключение ключей/калибровок; план rollback.

**Фаза B — LIVE, только с явным разрешением владельца и сохранением original images:** сначала read-only доступность bootloader USB boot mode/recovery/update UI, затем валидированный **подписанный безвредный** тест реакции на механизм обновления без изменения partitions. Никаких произвольных text-script, `setenv devicestate 0`, `avb set-devicestate`, `mmc write`, erase, relock и загрузки на случайно подключённую флешку до доказанного threat model и recovery.

**Условие завершения исследования «без ПК»:** демонстрация на идентичном стоковом **LOCKED 8054** с согласия владельца, что устройство распознаёт официальный подписанный тестовый носитель, получает подтверждение от владельца, выполняет штатный unlock/OTA и умеет восстанавливаться. У текущего опытного устройства загрузчик **уже разблокирован** — на нём нельзя честно подтвердить путь unlock «из locked» без опасной повторной блокировки.

## 7. Что не делать

- Не использовать чужие `auto_update.txt`, `factory.txt`, `MstarUpgrade.bin` от Allwinner, Rockchip, Xiaomi или иной платы.
- Не раздавать модифицированный заводской PKG с командами `gpt clean`, `wipeuserdata`, записью `factory/tvcertificate/private/eeprom/project_id` и `devicestate lock`.
- Не делать relock ради эксперимента (в unlocked состоянии можно загрузить кастомный образ, но это нельзя считать гарантией запуска при LOCKED).
- Не считать простое присутствие строки `avb set-devicestate <0/1>` доказательством безопасного пользовательского USB unlock.
- Не оставлять в публичном репозитории без проверки уникальные заводские ключи/калибровки из owner backup.

## Статус на 21.11.2026

`FASTBOOT_USB_UNLOCK_DEVICE_VERIFIED / BOOTLOADER_USB_MTKUPGRADE_STATIC_CONFIRMED / FACTORY_PKG_SCRIPT_CONFIRMED / FACTORY_SCRIPT_RELOCK_RISK_CONFIRMED / UNTRUSTED_USB_TXT_AUTO_UNLOCK_NOT_PROVEN / OTA_APP_CUSTOM_INSTALL_UNVERIFIED / FASTBOOT_UDP_STATIC_ONLY / PHONE_OTG_UNTESTED`.
