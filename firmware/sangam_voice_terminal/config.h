// Sangam Voice Terminal — build-time configuration.
//
// Hardware: ESP32-S3 (16MB flash, 8MB PSRAM), INMP441 I2S microphone,
// MAX98357A I2S amplifier, SD card, push-to-talk button.
#pragma once

#include <stdint.h>

// ---------------------------------------------------------------------------
// Identity
// ---------------------------------------------------------------------------
#define SANGAM_DEVICE_MODEL      "ESP32-S3-VoiceTerminal"
#define SANGAM_FIRMWARE_VERSION  "0.2.0"

// ---------------------------------------------------------------------------
// Backend
//
// The device talks ONLY to the Sangam backend. It never calls Sarvam
// directly: doing so would put a Sarvam API key in device flash, where a
// physically accessible terminal on a factory floor makes it recoverable.
// The backend holds the key and proxies STT/TTS.
// ---------------------------------------------------------------------------
#define SANGAM_API_HOST          "192.168.1.100"   // dev host running the backend
#define SANGAM_API_PORT          8000
#define SANGAM_API_USE_TLS       0                 // set 1 (and port 443) outside dev

// Per-device credential, provisioned during commissioning. Each terminal is
// a distinct Actor in Sangam so every action is attributable.
#define SANGAM_DEVICE_TOKEN      ""                // set at provisioning time

// ---------------------------------------------------------------------------
// Wi-Fi
// ---------------------------------------------------------------------------
#define WIFI_SSID                ""
#define WIFI_PASSWORD            ""
#define WIFI_CONNECT_TIMEOUT_MS  20000

// ---------------------------------------------------------------------------
// I2S microphone — INMP441
//
// Distinct GPIOs throughout. An earlier revision assigned GPIO 10 to both
// the microphone data line and an indicator LED, which cannot work.
// ---------------------------------------------------------------------------
#define I2S_MIC_SCK_PIN          12
#define I2S_MIC_WS_PIN           11
#define I2S_MIC_SD_PIN           10

// ---------------------------------------------------------------------------
// I2S amplifier — MAX98357A
// ---------------------------------------------------------------------------
#define I2S_SPK_BCLK_PIN         4
#define I2S_SPK_LRC_PIN          5
#define I2S_SPK_DIN_PIN          6

// ---------------------------------------------------------------------------
// Indicators and controls
// ---------------------------------------------------------------------------
#define LED_STATUS_PIN           8
#define LED_RECORDING_PIN        9
#define LED_ERROR_PIN            7     // was 10, which collided with I2S_MIC_SD
#define BUTTON_PTT_PIN           0     // active low (bootstrap button on devkits)

// ---------------------------------------------------------------------------
// SD card (SPI)
//
// Used as a durable queue. Plant Wi-Fi drops; a terminal that silently
// loses an operator's dictation when the network hiccups is a toy.
// ---------------------------------------------------------------------------
#define SD_CS_PIN                13
#define SD_SCK_PIN               14
#define SD_MOSI_PIN              15
#define SD_MISO_PIN              16
#define SD_QUEUE_DIR             "/queue"

// ---------------------------------------------------------------------------
// Audio
//
// 16 kHz mono 16-bit PCM: what Sarvam STT expects, and small enough that a
// 30 s utterance fits comfortably in PSRAM (16000 * 2 * 30 = ~960 KB).
// ---------------------------------------------------------------------------
#define AUDIO_SAMPLE_RATE        16000
#define AUDIO_BITS_PER_SAMPLE    16
#define AUDIO_CHANNELS           1
#define AUDIO_FRAME_SAMPLES      512
#define AUDIO_MAX_RECORD_MS      30000
#define AUDIO_MAX_RECORD_BYTES   ((AUDIO_SAMPLE_RATE / 1000) * AUDIO_MAX_RECORD_MS * 2)

// Push-to-talk debounce and minimum useful utterance length.
#define PTT_DEBOUNCE_MS          40
#define AUDIO_MIN_RECORD_MS      300

// ---------------------------------------------------------------------------
// Behaviour
// ---------------------------------------------------------------------------
#define HTTP_TIMEOUT_MS          20000
#define QUEUE_FLUSH_INTERVAL_MS  15000
#define MAX_QUEUED_ITEMS         64
