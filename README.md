# FlixTone D11 Master / Everycom CineLux — резервная копия и исследование RUIOS 8054

Репозиторий с резервной копией прошивки проектора **аппаратной ревизии 8054, двумя HDMI и Android 13**, а также read-only исследованием загрузчика MediaTek, GPT/LP dynamic partitions, Android Verified Boot и OEM-приложений.

**Статус на 21.11.2026:** загрузчик реального проектора успешно разблокирован штатной командой `fastboot flashing unlock`, оригинальный Android после этого загрузился в состоянии **AVB `orange`**. Внутренняя разметка `super` и оригинальный RAW backup подтверждены; **запись и загрузка кастомной прошивки пока НЕ испытаны**. Применимость к другим аппаратным ревизиям не доказана.

## Главные документы

- [**Проверенные факты на реальном 8054: unlock, AVB, Boot HAL, Virtual A/B, eMMC, dm-verity, super и SHA-256**](docs/8054_UNLOCK_AVB_PARTITIONS_VERIFIED_20261121.md)
- [**Установка без ПК: USB auto-update, MBOOT `mtkupgrade`, TXT-файлы, Fastboot UDP, телефон OTG и варианты OTA**](docs/USB_INSTALL_AND_UNLOCK_RESEARCH_20261121.md)
- [**План кастомной RUIOS: удаление мусора, замена лаунчера и клавиатуры, TvSettingsPlus MOD, безопасность и восстановление**](docs/CUSTOM_RUIOS_RELEASE_PLAN_20261121.md)

## Уже подтверждённое владельцем

| Факт | Результат |
|---|---|
| Точная ревизия | `ro.rjpj.machine.id=8054` |
| Загрузчик | MBOOT `01.01.260905` |
| Fastboot unlock | `unlocked: no→yes`, `secure: yes→no`, `fastboot flashing unlock=OKAY` |
| Android после unlock | Android 13 загрузился, `ro.boot.vbmeta.device_state=unlocked`, `verifiedbootstate=orange` |
| AVB/verity | `ro.boot.veritymode=enforcing`, реальные `*-verity` mapper устройства |
| Слоты | A текущий и successful; B bootable, но not successful; `system_b/vendor_b/product_b/system_ext_b` без extents |
| Динамические разделы | Virtual A/B + userspace compression, `system_a/vendor_a/product_a/system_ext_a`, EROFS RO |
| Полный `super.img` | 2 225 078 272 байта, `SHA256 ac16996dddaa7c8f5e5429a0736f73d18a12df7dc6b58a4e89a475f5af0c5a02` |
| Сверка резервной копии | Hash локального `super.img` совпал с независимо извлечённым из release ZIP на GitHub Actions |
| USB auto-update | Присутствует в точном MBOOT **по статическому анализу**, приём кастомной прошивки не подтверждён |
| `unlock.txt` рядом с прошивкой | **НЕ доказан**; не применять скрипты от других SoC |

## Обнаружен конкретный USB TXT entrypoint в MBOOT

Новая [офлайн-проверка exact 8054 MBOOT](https://github.com/MAX-TAC/FlixTone_8054_Backup/actions/runs/44944317009) установила в бинарном загрузчике буквальный текст **`Script format default file name is /usb_auto_update.txt`** и поддержку `mtkupgrade usb -script`. **Это подтверждённое имя файла для сценарного режима**, а не доказанная «флешка с автоматической разблокировкой». Не подтверждены автозапуск такого TXT при подаче питания, его подпись/допуск на заблокированном устройстве и возможность безопасного `unlock` через этот путь. Подробнее — [исследование установки без ПК](docs/USB_INSTALL_AND_UNLOCK_RESEARCH_20261121.md).

## Исходные средства исследования

Каталог [`tools/`](tools/) содержит read-only офлайн-анализаторы прошивки. [GitHub Actions](https://github.com/MAX-TAC/FlixTone_8054_Backup/actions) содержит результаты проверки оригинального MBOOT, U-Boot environment, AVB и EROFS без установки на проектор.

Родственные репозитории:
- [Everycom-Cinelux-Firmware](https://github.com/MAX-TAC/Everycom-Cinelux-Firmware) — заводские прошивки и **расшифрованный upgrade script для двух-HDMI CineLux**. В его сценарии есть `setenv usb_auto_upgrade enable` **и `setenv devicestate lock`** — не использовать заводской PKG как готовый пользовательский кастомный обновитель.
- [Projector-Soft](https://github.com/MAX-TAC/Projector-Soft) — разработка TvSettingsPlus MOD и исследование аппаратных настроек.

## Предупреждение о распространении

**Этот репозиторий предназначен для исследования, не является готовой инструкцией по прошивке.** Не прошивать в другой проектор raw `eeprom`, `persist`, `private`, `tvcertificate`, `factory`, `tvconfig`, `project_id` и не изменять MBOOT/OP-TEE без отдельного плана восстановления. Уникальные заводские разделы могут содержать личные или лицензионные ключи и калибровки. **Состав ранее опубликованных release-архивов следует отдельно проверить на такие данные; если они открыты публично, может потребоваться заменить их обезличенным релизом.**

Наличие unlock и бэкапа не подтверждает возможность восстановить устройство после неправильной записи `super` или `vbmeta`. Не делать relock с модифицированной системой.
