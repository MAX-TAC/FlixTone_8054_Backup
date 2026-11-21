# FlixTone D11 Master / Everycom CineLux 2×HDMI, RUIOS 8054 — подтверждённый Fastboot, AVB и разделы

Дата наблюдений: **21 ноября 2026**. Источник: результаты команд, самостоятельно выполненных владельцем на **реальном проекторе**; прежние исходники/скрипты и результаты GitHub Actions — вспомогательный статический материал. **Тест установки кастомного образа отсутствует**. Документ не описывает прошивку чужих аппаратных ревизий.

## 1. Идентичность устройства

| Параметр | Подтверждённое значение |
|---|---|
| OEM / аппаратный ID | `ro.rjpj.machine.id=8054` |
| Android | 13, `mt5873_cd-userdebug 13 TP1A.220624.021.A1 eng.suhaix.20260905.031903 test-keys` |
| Bootloader | `version-bootloader=01.01.260905` |
| Fastboot | обычный **bootloader Fastboot**; `is-userspace=no` |
| Boot slots | `slot-count=2`, A и B; активен `_a` |
| Boot HAL | `android.hardware.boot@1.2::IBootControl` |
| Корневой раздел Android | EROFS, смонтирован как `/` (system-as-root) |

## 2. Самое важное: разблокировка **действительно сработала**

Владелец подключил проектор к Windows по USB для bootloader Fastboot и **на живом устройстве** получил:

```text
adb reboot bootloader
fastboot devices
fastboot getvar unlocked
  unlocked: no
fastboot getvar secure
  secure: yes

fastboot flashing unlock
  OKAY

fastboot getvar unlocked
  unlocked: yes
fastboot getvar secure
  secure: no
fastboot getvar current-slot
  current-slot: a
```

После `fastboot reboot` **заводской Android загрузился**:

```text
ro.boot.vbmeta.device_state = unlocked
ro.boot.verifiedbootstate = orange
ro.boot.veritymode = enforcing
ro.boot.vbmeta.hash_alg = sha256
ro.boot.vbmeta.digest = 5d67f5b378cb61ff624fffb80ccb1ab435663efb9dc9bbecb7786e84d8148c2a
ro.boot.slot_suffix = _a
ro.rjpj.machine.id = 8054
sys.boot_completed = 1
```

`ro.boot.flash.locked` не задано. Не интерпретировать отсутствие property как блокировку или ошибку. `fastboot flashing get_unlock_ability` → `invalid command`; `fastboot oem unlock` → `unrecognized command`. Отсутствие именно этих команд **не означает**, что `fastboot flashing unlock` не поддерживается. Первоначальная гипотеза о принципиальной невозможности unlock на 8054 **опровергнута экспериментом**.

Внимание: AOSP при разблокировке предупреждает о возможном/предписанном стирании данных. Была ли очищена `/data` именно на данном OEM, документально не доказано. **Никогда не делать `fastboot flashing lock` после установки кастомного образа** без полной проверки подписи и обратимости.

`orange` означает состояние Verified Boot на разблокированном устройстве; **это не доказывает**, что все проверки MBOOT, OP-TEE, AVB hashtree и dm-verity отключены. Реальная ОС на 8054 продолжает монтировать системные разделы через `*-verity`, а `veritymode=enforcing`.

Документация AOSP: [Device state](https://source.android.com/docs/security/features/verifiedboot/device-state), [Lock/unlock bootloader](https://source.android.com/docs/core/architecture/bootloader/locking_unlocking).

## 3. Физическая схема eMMC — фактические данные `/dev/block/by-name`

| Имя | Physical block | Назначение / предосторожность |
|---|---|---|
| `mboot_a` / `mboot_b` | `mmcblk0p1` / `p2` | Bootloader; **не изменять** |
| `tvservice_a` / `tvservice_b` | `p12` / `p13` | OEM MediaTek TV stack |
| `boot_a` / `boot_b` | `p24` / `p25` | Android boot |
| `super` | `p29` | Dynamic system/vendor/product/system_ext |
| `vbmeta_a` / `vbmeta_b` | `p31` / `p32` | Корневая AVB-цепочка |
| `vbmeta_system_a` / `vbmeta_system_b` | `p33` / `p34` | AVB системных разделов |
| `optee_a` / `optee_b` | `p35` / `p36` | Trusted execution; **не изменять** |
| `rom_emmc_boot_a` / `rom_emmc_boot_b` | `mmcblk0boot0` / `boot1` | eMMC boot areas; **не изменять** |

Это не исчерпывающий список GPT. Другие физические разделы включают `factory`, `tvconfig`, `eeprom`, `persist`, `private`, `project_id`, `tvcertificate`, `bootdata`. Эти данные могут быть аппаратно-уникальными и **не должны переноситься на другой проектор**.

## 4. `super` — точные LP metadata из устройства

Состояние **одинаково** для `lpdump --slot 0` и `lpdump --slot 1`:

- Metadata version `10.2`; metadata max size `65536`; **metadata slot count `3` не является числом загрузочных слотов**.
- Header flag `virtual_ab_device`.
- Физический `super` имеет размер **2 225 078 272 байта** (`0x84a00000`).
- `group_oem_a` / `group_oem_b`, каждый max **2 220 883 968 байт**; оба значения не являются одновременно свободным пространством.

| Logical partition | Extent `super` (сектора ×512) | Bytes | MiB |
|---|---|---:|---:|
| `system_a` | `2048`, 1 671 432 сектора | 855 773 184 | 816.13 |
| `vendor_a` | `1675264`, 513 016 секторов | 262 664 192 | 250.50 |
| `product_a` | `2189312`, 150 696 секторов | 77 156 352 | 73.58 |
| `system_ext_a` | `2340864`, 170 496 секторов | 87 293 952 | 83.25 |
| `system_b`, `vendor_b`, `product_b`, `system_ext_b` | **Нет extents** | 0 | 0 |

Сумма выделенных extent A — **1 282 887 680 B** (~1 223.46 MiB). Простейшая разница `super − A` = **942 190 592 B** (~898.54 MiB), но это **не гарантия** свободного места под новые images: необходимо учитывать LP geometry, выравнивание, ограничение групп и место под метаданные.

## 5. Virtual A/B, Boot HAL и отсутствие безопасного fallback B

```text
ro.virtual_ab.enabled=true
ro.virtual_ab.userspace.snapshots.enabled=true
ro.virtual_ab.compression.enabled=true
ro.virtual_ab.io_uring.enabled=true
bootctl get-number-slots = 2
bootctl get-active-boot-slot = 0
bootctl get-snapshot-merge-status = none
```

Состояние Boot HAL (значение `rc` — код завершения, а не напечатанный boolean):

| Boot HAL запрос | Slot A (0) | Slot B (1) |
|---|---:|---:|
| `is-slot-bootable` | `rc=0` | `rc=0` |
| `is-slot-marked-successful` | `rc=0` | `rc=70` |

При существующем B и без диагностических сообщений наиболее вероятно, что `isSlotMarkedSuccessful(B)=false`. Следовательно, **B формально bootable, но не successful**, и в текущих LP metadata у него нет логических системных разделов. **Нельзя делать `fastboot set_active b` «для проверки», нельзя считать это рабочим recovery.**

Snapshot merge state `none` не означает, что B рабочий. [AOSP Virtual A/B](https://source.android.com/docs/core/ota/virtual_ab).

## 6. Реальный device-mapper и файловые системы

```text
super / system_a     → dm-0 → dm-4  system-verity       → /             EROFS ro
super / vendor_a     → dm-1 → dm-5  vendor-verity       → /vendor       EROFS ro
super / product_a    → dm-2 → dm-6  product-verity      → /product      EROFS ro
super / system_ext_a → dm-3 → dm-7  system_ext-verity   → /system_ext   EROFS ro
OEM tvservice                  → dm-9  tvservice-verity    → /mnt/vendor/tvservice ext4 ro
OEM factory                    → dm-10 factory-verity      → /mnt/vendor/factory   ext4 ro
OEM linux_rootfs               → dm-11 linux_rootfs-verity → /mnt/vendor/linux_rootfs squashfs ro
OEM 3rd                        → dm-12 3rd-verity          → /mnt/vendor/3rd squashfs ro
OEM bootdata                   → dm-13 bootdata-verity     → /mnt/vendor/bootdata ext4 ro
userdata                       → dm-8 userdata            → /data        F2FS rw
```

`dmctl` от обычного `adb shell` → `Permission denied`. Это ограничение прав, не ошибка образа.

**Следствие для модификации:** EROFS нельзя «просто смонтировать для записи»; нужен корректный новый образ и согласованность с цепочкой AVB/dm-verity, SELinux, а также размером логического раздела. Разблокировка Fastboot сама по себе это не делает.

## 7. Оригинальный `super.img` — локально и в архиве релиза совпадает SHA

На Windows владелец проверил оригинальный RAW-кандидат:

```text
%USERPROFILE%\Downloads\FlixTone_8054_Backup\super.img
bytes: 2225078272
SHA256: ac16996dddaa7c8f5e5429a0736f73d18a12df7dc6b58a4e89a475f5af0c5a02
```

**Независимая сверка:** существующий GitHub Actions run [43891019885](https://github.com/MAX-TAC/FlixTone_8054_Backup/actions/runs/43891019885) **действительно распаковал `super.img` из `FlixTone_8054_Backup.zip` данного репозитория** и вычислил **тот же SHA256**. Следовательно, локальный файл владельца и образ из архивного release совпадают по хешу. Это ещё **не** подтверждение byte-to-byte совпадения с текущей eMMC после операций unlock (не считывалась заново).

В том же offline release-аналитическом CI:

```text
mboot_a.img SHA256 ebf9a0adef859f568d792d182f4ace08d026a27dc7f322bab735c67b07cd34c1
uenv.img SHA256 ad7c75ec414d12388a4b2c459042a6815f1e8c334e0ad7f176f69ebb48aa7269
super.img SHA256 ac16996dddaa7c8f5e5429a0736f73d18a12df7dc6b58a4e89a475f5af0c5a02
```

Одинаковый размер `super.img` и physical partition — аргумент за полный дамп, а сам **парсер LP geometry + проверка EROFS** воспроизводились в `tools/inspect_8054_draft_safely.py` в ранее успешных CI. Это **не** готовая подтверждённая процедура экстренного восстановления образа через Fastboot.

## 8. Матрица состояния кастомной RUIOS

| Этап | Достоверность |
|---|---|
| Разблокировка реального MBOOT | **DEVICE VERIFIED** |
| Загрузка оригинального Android после unlock, AVB orange | **DEVICE VERIFIED** |
| Разметка physical GPT / LP metadata / EROFS | **DEVICE VERIFIED** |
| Наличие/хеш полного архивного `super.img` | **OWNER LOCAL + INDEPENDENT ARCHIVE HASH MATCH** |
| Установка и загрузка модифицированного EROFS/AVB образа | **NOT TESTED** |
| Подтверждённый Fastboot / Fastbootd recovery после неудачной прошивки | **NOT TESTED** |
| Полноценная безопасная прошивка по одной USB-флешке | **NOT TESTED** |

**Задача кастомной прошивки:** на основе оригинальной RUIOS удалить необязательные приложения, заменить launcher и IME, адаптировать TvSettingsPlus MOD, изменить отображаемое имя устройства и оформление/boot animation. Сохранить MTK TV drivers/HAL, HDMI, PQ, оптику, автофокус, охлаждение, thermal, лицензии и OEM-калибровки. **Перед удалением KuSettings проверить фоновые зависимости BootupReceiver/MySetTimeService ↔ KuSourceRJ TimeService.**

## 9. Безопасность распространяемого релиза

- Прошивки и public restore images должны быть **строго по ID 8054 и проверенной аппаратной ревизии**; 8052/8053 нельзя считать совместимыми по общему SoC.
- Не публиковать **уникальные** `eeprom`, `persist`, `private`, `tvcertificate`, `project_id`, `tvconfig`, `factory`, HDCP/DRM/calibration/key material. **Проверить содержимое уже существующего release ZIP**: если такие private images включены в публичный assets, следует отдельно принять решение об ограничении доступа и выпуске обезличенного пакета; данный документ не удаляет assets.
- Не проводить самовольного `fastboot flashing lock`/erase/flash, записи `uenv`, `mboot`, `optee`, `armfw`, `eeprom` и factory partition.
- Перед любой прошивкой — проверенная механика recovery и dry-run сборки/сигнатур на ПК. По возможности распределять минимальные, откатываемые изменения, а не целый factory update с GPT clean.

## Ссылки

- [Родственные исследования точной прошивки двух-HDMI в MAX-TAC/Everycom-Cinelux-Firmware](https://github.com/MAX-TAC/Everycom-Cinelux-Firmware)
- [Результаты offline MBOOT/AVB](https://github.com/MAX-TAC/FlixTone_8054_Backup/actions/runs/43902935064)
- [Исследование установки без ПК / USB-скриптов](USB_INSTALL_AND_UNLOCK_RESEARCH_20261121.md)
- [Ограничения и план безопасного релиза](CUSTOM_RUIOS_RELEASE_PLAN_20261121.md)
