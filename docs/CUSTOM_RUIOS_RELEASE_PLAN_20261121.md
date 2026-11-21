# План Custom RUIOS 8054 — заводская база без лишних китайских приложений

Дата планирования: 21.11.2026. Цель: готовая к распространению **модифицированная оригинальная** RUIOS для FlixTone D11 Master / Everycom CineLux **с двумя HDMI, точная ревизия 8054**, а не сторонний AOSP/LineageOS. Не использовать на 8052/8053 и иных платформах.

## 1. Состав изменений

| Направление | План | Статус |
|---|---|---|
| Android TV launcher | Замена китайского launcher на совместимый TV launcher; корректная Home Activity и D-pad | Реализуемо технически, совместимость на точном 8054 ещё не испытана |
| Экранная клавиатура | Замена IME, включение безопасного default input method; учесть ввод с пульта/BT | Реализуемо, системная интеграция не испытана |
| Настройки | `TvSettingsPlus MOD` вместо китайского user-facing меню; сохранить OEM Android TV Picture/Sound callbacks и совместимость по подписи/permission | В разработке в [MAX-TAC/Projector-Soft](https://github.com/MAX-TAC/Projector-Soft) |
| Debloat | Удаление только доказанно ненужных APK и startup components | Требуется карта сервисных зависимостей и тест каждого пакета |
| Отображаемое имя | Найти отдельно Android device name, Bluetooth name, Cast/AirPlay/UPnP label и OEM info string | Разные интерфейсы могут брать имя из разных storage/backend |
| Анимация загрузки | Изменение `bootanimation`/Android assets после определения реального пути | Не равно раннему аппаратному логотипу MBOOT |
| Ранний splash/logo | Изучение MBOOT/bootdata/logo resources, но **не** менять bootloader в первом релизе | Пока только исследование |
| Системные дефолты | Проверяемые overlays/configuration, без нарушения SELinux/AVB | Не испытано |

**Что обязано сохраниться:** MTK stock kernel, HAL, HDMI 1/2, TV Services, PQ/DSP, звук, DRM/HDCP, оптика, autofocus, keystone, sensors/ToF, fan/thermal, питание и штатное поведение после холодного старта.

Критическая зависимость: **`com.my.settings` может владеть фоновыми сервисами**, в частности BootupReceiver/MySetTimeService в связке с KuSourceRJ TimeService. Поэтому снять китайский интерфейс с пользовательского пути **не** то же самое, что удалить пакет; сначала доказать автономную замену сервисов и безопасный rollback.

## 2. Варианты формата релиза

### Канал A: пользовательский APK-пакет обновлений

- Там, где штатная подпись, manifest, privileges и Android package upgrade policy позволяют, поставлять signed APK-подмену TvSettingsPlus и альтернативный launcher/IME отдельным установщиком.
- Преимущества: без прошивки целого `super`, ниже риск, можно обслуживать функциональность.
- Ограничения: не все системные компоненты можно заменить из UI, critical privileged app / preload default могут требовать системную сборку; неизвестно, можно ли обновить OEM приложение обычной установкой на конкретном устройстве.
- Это не равно полноценной Custom RUIOS, но даёт **промежуточную пользовательскую версию без ПК**.

### Канал B: signed OEM OTA / локальное обновление

- Исследовать exact-8054 RuiYunOta, update_engine, тип принимаемых пакетов, OEM package signatures, проверку `pre-device`, anti-rollback и процедуру восстановления.
- Анализ 8052/8053 показывает некоторые OTA testkey сертификаты, но их подпись **не** эквивалентна доверию MBOOT PKG/AVB или exact-8054 accept policy.
- Обновление должно проверять аппаратный ID и владельцу предоставлять выбор с объяснением изменения boot state/риска wipe.
- Нельзя автоматически объявлять OTA возможной из-за наличия `update_engine`.

### Обновление исследования USB TXT от 21.11.2026

На **точном MBOOT 8054** вновь проверен литерал `Script format default file name is /usb_auto_update.txt`; отдельно есть `mtkupgrade usb -script` и `scriptstar [script_file_name]`. Это делает разработку **USB-инсталлятора с текстовым сценарием** предметной задачей, но **не** подтверждает запуск `usb_auto_update.txt` автоматически при старте (bootflow видит `usb start;mtkupgrade usb`, который может выбирать PKG), тем более разрешённую разблокировку с locked state без consent. [Точный офлайн тест](https://github.com/MAX-TAC/FlixTone_8054_Backup/actions/runs/44944317009); [детали](USB_INSTALL_AND_UNLOCK_RESEARCH_20261121.md).

### Канал C: USB bootloader recovery/upgrade

- Exact MBOOT содержит `mtkupgrade usb`, auto-upgrade и `-script`; детали [USB analysis](USB_INSTALL_AND_UNLOCK_RESEARCH_20261121.md).
- Заводской USB PKG запускает destructive GPT/MMC/bootloader/calibration path и `setenv devicestate lock` — **не копировать этот сценарий**.
- Только ограниченный, проверенный и авторизованный пакет whitelist, который не меняет заводские уникальные данные; гарантий пока нет.
- Определить распознаваемое имя образа, parser, signature acceptance, source of scripts и exact boot entry trigger; до этого USB auto-update **не release-ready**.

### Канал D: Fastboot / телефон OTG — продвинутым пользователям

- Владелец доказал, что стандартная команда `fastboot flashing unlock` работает в bootloader Fastboot.
- Телефон с USB-OTG *потенциально* заменяет ПК, если USB host приложение умеет Fastboot и Android предоставляет к устройству USB permissions; это всё равно **кабель к проектору**.
- В отличие от неизвестных текстовых скриптов владелец явно инициирует unlock. Устройство может стереть user data.
- USB Fastboot по текущим наблюдениям работает; телефон-host ещё не проверен.

**Идеальное целевое пользовательское UX:** проверенная модель/ревизия → понятное согласие → предварительный backup/export → проверка оригинального состояния → USB/OTA подписанный пакет → запись **только** разрешённых разделов → проверка после перезагрузки → процедура восстановления. Самовольная разблокировка при каждом включении с флешкой неприемлема.

## 3. Recovery / риски

### Прежде чем модифицировать SYSTEM_EXT

- Подтверждён полный резервный `super.img`: 2 225 078 272 B, SHA256 `ac16996dddaa7c8f5e5429a0736f73d18a12df7dc6b58a4e89a475f5af0c5a02`. Совпадает с независимым извлечением из архивного release в GitHub Actions.
- LP metadata `10.2`, Virtual A/B compressed; активен слот A, B bootable-but-not-successful, без logical extents. **B — не доказанный fallback**.
- Смонтированы EROFS через dm-verity, включая `system_ext-verity`. Прежде записи требуются корректная EROFS сборка, совместимость SELinux и корректная AVB цепочка.
- Проверить восстановление физического `super` в bootloader Fastboot или fastbootd без рисков для заводских ключей. Один RAW backup **не** гарантия recovery.
- OEM-программа записи может требовать иной формат/сегментацию, max download size может быть меньше физического `super`; не отправлять full RAW незнакомой командой.
- Никогда не считать наличие `boot_b` аналогом копии полного Android.
- Не изменять `mboot`, OP-TEE, ARM firmware, `eeprom`, `private`, `tvcertificate`, заводские `factory/tvconfig/persist/project_id`.

### Публичный backup: исключение уникальных данных

В существующем репозитории могут присутствовать публичные GitHub release assets с **владельческими резервными образами**, включая PRIVATE_FACTORY. Они потенциально содержат уникальные серийные сведения, токены, лицензионные и DRM/HDCP данные, заводскую коррекцию и calibration. **Провести аудит приватности архива и, при необходимости, заменить публичный релиз обезличенным комплектом.** Это независимая задача: сейчас ничего не удалялось/не переупаковывалось. Тексты исследований таких данных не публикуют.

## 4. Критерии готовности релиза

**M1 — исходная база:** подтверждён exact ID 8054; checksum/version/SHA manifest для исходных PKG/APK; список системы/пакетов, backup и restore.

**M2 — минимальная Custom RUIOS:** новый launcher, IME, экранные настройки без китайского user GUI, аппаратные службы сохранены; проверки холодной загрузки/HDMI/оптики/thermal/audio/BT/CEC.

**M3 — инженерная прошивка:** на отдельном разрешённом тестовом цикле доказано, что модифицированный EROFS/system_ext (и AVB/verity) можно установить, загрузить и восстановить. Не выполнять этот тест без репетированной recovery.

**M4 — доступная установка:** отдельно доказано, что signed OTA/USB package без ПК работает и не стирает чужие заводские ключи. Если нет — начать со способа Fastboot USB с ПК или Android OTG, без выдуманной «однокнопочной флешки».

**M5 — публичный релиз:** reproducible build, исходники/licensing, checksums, changelog, модельный allowlist, clear risks, stop conditions, rollback и конфиденциальность, отсутствие embedded unique device keys.

## 5. Текущая оценка

| Вопрос | Ответ |
|---|---|
| Реально ли сделать модифицированную заводскую RUIOS? | **Высокая техническая вероятность** при сохранении MTK BSP и OEM HAL |
| Доказана ли разблокировка загрузчика? | **Да, на реальном 8054** |
| Доказана ли загрузка модифицированной прошивки? | **Нет** |
| Есть ли полноценный `super.img` backup? | **Да, SHA совпадает с архивным release** |
| Доказан ли recovery через Fastboot? | **Нет** |
| Можно ли уже обещать TXT-флешку с auto-unlock? | **Нет** |
| Как сделать установку доступной без ПК? | Исследовать signed OTA/USB update; резерв — телефон-host Fastboot OTG |

Связанные документы: [Verified hardware](8054_UNLOCK_AVB_PARTITIONS_VERIFIED_20261121.md), [USB unlock/install research](USB_INSTALL_AND_UNLOCK_RESEARCH_20261121.md), [MAX-TAC/Projector-Soft](https://github.com/MAX-TAC/Projector-Soft).
