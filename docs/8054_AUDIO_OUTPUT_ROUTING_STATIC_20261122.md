# FlixTone / RUIOS 8054 — проверка Audio Policy и доступа TvSettingsPlus

Дата: 22 ноября 2026. Исходник: оригинальный резервный super.img ревизии 8054. Анализ файлов EROFS выполнен на GitHub Actions без доступа к проектору, без изменений прошивки.

## Проверенные источники

- [Audio Policy, Manifest и permissions — успешный CI](https://github.com/MAX-TAC/FlixTone_8054_Backup/actions/runs/45015345541)
- [Сверка сертификатов Android Framework / TvSettingsPlus — успешный CI](https://github.com/MAX-TAC/FlixTone_8054_Backup/actions/runs/45015766483)
- [Воспроизводимый скрипт](../tools/audit_8054_audio_output_policy.py)
- [Требования к интерфейсу в Projector-Soft](https://github.com/MAX-TAC/Projector-Soft/blob/research/8054-direct-mediat-ek-api-contracts-20261122/docs/TVSETTINGSPLUS_8054_PICTURE_SOUND_OUTPUT_REQUIREMENTS_20261122.md)

## 1. Что поддерживает конфигурация MediaTek

Физический файл vendor/etc/audio_policy_configuration.xml извлечён из точного vendor_a образа. В нём 21 devicePort, 9 mixPort, 17 route. В отличие от Android API-документации, это фактическое содержимое прошивки данного проектора.

| Output | Audio policy device type | От primary output есть route |
|---|---|---|
| Встроенные динамики | AUDIO_DEVICE_OUT_SPEAKER | Да |
| Bluetooth A2DP Speaker | AUDIO_DEVICE_OUT_BLUETOOTH_A2DP_SPEAKER | Да |
| Bluetooth A2DP / Headphones | AUDIO_DEVICE_OUT_BLUETOOTH_A2DP, AUDIO_DEVICE_OUT_BLUETOOTH_A2DP_HEADPHONES | Да |
| HDMI ARC | AUDIO_DEVICE_OUT_HDMI_ARC | Да |
| HDMI Out | AUDIO_DEVICE_OUT_AUX_DIGITAL | Да |
| SPDIF | AUDIO_DEVICE_OUT_SPDIF | Да |
| USB Audio | AUDIO_DEVICE_OUT_USB_ACCESSORY, USB_DEVICE, USB_HEADSET | Да |

**Ограничение:** записи в XML не означают, что все физические outputs поддерживаются одновременно, текущий медиапоток можно переместить без разрыва A2DP или что HDMI eARC согласован. Заявленная HDMI ARC capability не является проверкой реального HDMI eARC handshake. Входы Bluetooth могут быть созданы системой динамически.

## 2. Запрошенные permissions в оригинальных APK

| APK | MODIFY_AUDIO_ROUTING | QUERY_AUDIO_STATE | BLUETOOTH_CONNECT | BLUETOOTH_PRIVILEGED |
|---|---|---|---|---|
| TvSettingsPlus | Нет | Нет | Да | Да |
| RJBluetoothSpeaker | Нет | Нет | Да | Да |
| TvServices | Нет | Нет | Нет | Нет |

Файл system_ext/etc/permissions/privapp-permissions-mediatek.xml не содержит MODIFY_AUDIO_ROUTING для com.android.tv.settings. Это само по себе не запрещает выдачу разрешения по совпадению платформенной подписи, но исходный APK даже не объявляет требуемого permission.

## 3. Важнейший результат: framework-res.apk и TvSettingsPlus.apk подписаны одним сертификатом

Сравнение `apksigner verify --print-certs` двух *оригинальных* файлов из super.img:

```text
system_a_tree/system/framework/framework-res.apk
  cert SHA256 = c8a2e9bccf597c2fb6dc66bee293fc13f2fc47ec77bc6b2b0d52c11f51192ab8
system_ext_a_tree/priv-app/TvSettingsPlus/TvSettingsPlus.apk
  cert SHA256 = c8a2e9bccf597c2fb6dc66bee293fc13f2fc47ec77bc6b2b0d52c11f51192ab8
FRAMEWORK_TVSETTINGS_CERT_EQUAL True
```

В Android 13 MODIFY_AUDIO_ROUTING защищено `signature|privileged|role`. Это даёт **предметное основание** ожидать, что совместимо подписанный обновлённый TvSettingsPlus, добавив uses-permission, сможет получить **signature permission**, потенциально без изменений privileged allowlist в системном образе. Нельзя делать вывод, что permission уже выдан: оно отсутствует в исходном Manifest. Решающий тест — actual granted=true на реальном проекторе, затем read-only listing и отдельный согласованный тест routing.

Системное Android 13 API: `AudioManager.setPreferredDevicesForStrategy()` с `AudioProductStrategy`, требует MODIFY_AUDIO_ROUTING. Это @SystemApi, правильная среда компиляции или поддерживаемый точной ROM способ вызова дополнительно исследуется. Для медиа-аудио не использовать `AudioManager.setCommunicationDevice()` (это звонки/VoIP).

## 4. Ограничения EQ

В ROM есть vendor/etc/audio_effects.xml и system/etc/audio_effects.conf, но данный инспектор не декодирует полное устройство эффектов; 0 имен из текущего XML-среза не означает отсутствие эквалайзера. OEM 5-band Sound EQ наблюдался владельцем на встроенных динамиках, но не Bluetooth. Нельзя предполагать работу заводского 13-band PEQ на A2DP или HDMI ARC.

## 5. Следующая read-only аппаратная диагностика

С одновременно подключённым Bluetooth-саундбаром и HDMI ARC/eARC устройством из Windows CMD:

```bat
adb shell dumpsys audio > "%USERPROFILE%\Downloads\8054_audio.txt"
adb shell dumpsys media.audio_policy > "%USERPROFILE%\Downloads\8054_audio_policy.txt"
adb shell dumpsys media.audio_flinger > "%USERPROFILE%\Downloads\8054_audio_flinger.txt"
adb shell dumpsys hdmi_control > "%USERPROFILE%\Downloads\8054_hdmi_control.txt"
adb shell dumpsys package com.android.tv.settings > "%USERPROFILE%\Downloads\8054_tvsettings_package.txt"
```

Эти файлы могут содержать BT MAC и имена устройств — проверить перед публикацией. На устройстве в рамках этой задачи ничего не выполнялось и не переключалось. Следующий критерий: actual route, feature/permission grant и проверка обратимости при сохранённом BT connection.