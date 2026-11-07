// Sangam Voice Terminal — ESP32-S3
//
// A wall-mounted push-to-talk terminal for a regulated plant floor. An
// operator holds the button, speaks in their own language, and the
// utterance is sent to the Sangam backend, which runs Sarvam STT and
// returns a spoken confirmation.
//
// Three decisions worth stating, because they are what separate this from
// a hobby voice assistant:
//
//   1. No Sarvam key on the device. The terminal talks only to Sangam,
//      which proxies STT/TTS. A terminal bolted to a wall in a factory is
//      physically accessible; a key in its flash is a recovered key.
//
//   2. Push-to-talk, not wake-word. GMP areas and works councils object to
//      an always-live microphone, and a hot mic in a plant is a
//      surveillance question before it is a technical one.
//
//   3. The SD card is a durable queue, not storage. Plant Wi-Fi drops. An
//      utterance recorded during an outage is written to disk and replayed
//      on reconnect, with audible feedback so the operator is never left
//      guessing whether it was captured.
//
// Build:
//   arduino-cli compile --fqbn esp32:esp32:esp32s3 firmware/sangam_voice_terminal
// Flash:
//   arduino-cli upload -p COM5 --fqbn esp32:esp32:esp32s3 firmware/sangam_voice_terminal

#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <SPI.h>
#include <SD.h>
#include <driver/i2s.h>

#include "config.h"

// ---------------------------------------------------------------------------
// Device state
// ---------------------------------------------------------------------------
enum DeviceState {
  STATE_BOOT,
  STATE_WIFI_CONNECTING,
  STATE_IDLE,
  STATE_RECORDING,
  STATE_UPLOADING,
  STATE_SPEAKING,
  STATE_OFFLINE,
  STATE_ERROR,
};

static DeviceState g_state = STATE_BOOT;
static bool g_sdReady = false;
static uint8_t *g_recordBuffer = nullptr;   // PSRAM
static size_t g_recordLength = 0;
static uint32_t g_lastQueueFlush = 0;
static uint32_t g_queuedCount = 0;

static const i2s_port_t I2S_MIC_PORT = I2S_NUM_0;
static const i2s_port_t I2S_SPK_PORT = I2S_NUM_1;

// ---------------------------------------------------------------------------
// Indicators
// ---------------------------------------------------------------------------
static void setState(DeviceState state) {
  g_state = state;
  digitalWrite(LED_RECORDING_PIN, state == STATE_RECORDING ? HIGH : LOW);
  digitalWrite(LED_ERROR_PIN, (state == STATE_ERROR || state == STATE_OFFLINE) ? HIGH : LOW);
  digitalWrite(LED_STATUS_PIN, (state == STATE_IDLE || state == STATE_SPEAKING) ? HIGH : LOW);
}

static const char *stateName(DeviceState s) {
  switch (s) {
    case STATE_BOOT:            return "boot";
    case STATE_WIFI_CONNECTING: return "wifi";
    case STATE_IDLE:            return "idle";
    case STATE_RECORDING:       return "recording";
    case STATE_UPLOADING:       return "uploading";
    case STATE_SPEAKING:        return "speaking";
    case STATE_OFFLINE:         return "offline";
    default:                    return "error";
  }
}

// ---------------------------------------------------------------------------
// Audio: WAV header
//
// Sarvam expects a real WAV, not raw PCM, so the header is built on device.
// ---------------------------------------------------------------------------
static void writeWavHeader(uint8_t *header, size_t pcmBytes) {
  const uint32_t sampleRate = AUDIO_SAMPLE_RATE;
  const uint16_t channels = AUDIO_CHANNELS;
  const uint16_t bits = AUDIO_BITS_PER_SAMPLE;
  const uint32_t byteRate = sampleRate * channels * (bits / 8);
  const uint16_t blockAlign = channels * (bits / 8);
  const uint32_t chunkSize = 36 + pcmBytes;

  memcpy(header, "RIFF", 4);
  memcpy(header + 4, &chunkSize, 4);
  memcpy(header + 8, "WAVEfmt ", 8);
  const uint32_t subchunk1Size = 16;
  const uint16_t audioFormat = 1;  // PCM
  memcpy(header + 16, &subchunk1Size, 4);
  memcpy(header + 20, &audioFormat, 2);
  memcpy(header + 22, &channels, 2);
  memcpy(header + 24, &sampleRate, 4);
  memcpy(header + 28, &byteRate, 4);
  memcpy(header + 32, &blockAlign, 2);
  memcpy(header + 34, &bits, 2);
  memcpy(header + 36, "data", 4);
  const uint32_t dataSize = pcmBytes;
  memcpy(header + 40, &dataSize, 4);
}

// ---------------------------------------------------------------------------
// I2S
// ---------------------------------------------------------------------------
static bool initMicrophone() {
  i2s_config_t cfg = {};
  cfg.mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX);
  cfg.sample_rate = AUDIO_SAMPLE_RATE;
  cfg.bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT;  // INMP441 emits 24-bit in 32-bit slots
  cfg.channel_format = I2S_CHANNEL_FMT_ONLY_LEFT;
  cfg.communication_format = I2S_COMM_FORMAT_STAND_I2S;
  cfg.intr_alloc_flags = ESP_INTR_FLAG_LEVEL1;
  cfg.dma_buf_count = 8;
  cfg.dma_buf_len = AUDIO_FRAME_SAMPLES;
  cfg.use_apll = false;

  i2s_pin_config_t pins = {};
  pins.bck_io_num = I2S_MIC_SCK_PIN;
  pins.ws_io_num = I2S_MIC_WS_PIN;
  pins.data_out_num = I2S_PIN_NO_CHANGE;
  pins.data_in_num = I2S_MIC_SD_PIN;

  if (i2s_driver_install(I2S_MIC_PORT, &cfg, 0, nullptr) != ESP_OK) return false;
  return i2s_set_pin(I2S_MIC_PORT, &pins) == ESP_OK;
}

static bool initSpeaker() {
  i2s_config_t cfg = {};
  cfg.mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX);
  cfg.sample_rate = AUDIO_SAMPLE_RATE;
  cfg.bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT;
  cfg.channel_format = I2S_CHANNEL_FMT_ONLY_LEFT;
  cfg.communication_format = I2S_COMM_FORMAT_STAND_I2S;
  cfg.intr_alloc_flags = ESP_INTR_FLAG_LEVEL1;
  cfg.dma_buf_count = 8;
  cfg.dma_buf_len = AUDIO_FRAME_SAMPLES;
  cfg.use_apll = false;

  i2s_pin_config_t pins = {};
  pins.bck_io_num = I2S_SPK_BCLK_PIN;
  pins.ws_io_num = I2S_SPK_LRC_PIN;
  pins.data_out_num = I2S_SPK_DIN_PIN;
  pins.data_in_num = I2S_PIN_NO_CHANGE;

  if (i2s_driver_install(I2S_SPK_PORT, &cfg, 0, nullptr) != ESP_OK) return false;
  return i2s_set_pin(I2S_SPK_PORT, &pins) == ESP_OK;
}

// Capture while the button is held. Returns PCM byte count.
static size_t recordWhileHeld() {
  size_t written = 0;
  const uint32_t start = millis();
  int32_t frame[AUDIO_FRAME_SAMPLES];

  i2s_zero_dma_buffer(I2S_MIC_PORT);

  while (digitalRead(BUTTON_PTT_PIN) == LOW) {
    if (millis() - start > AUDIO_MAX_RECORD_MS) break;
    if (written + AUDIO_FRAME_SAMPLES * 2 >= AUDIO_MAX_RECORD_BYTES) break;

    size_t bytesRead = 0;
    if (i2s_read(I2S_MIC_PORT, frame, sizeof(frame), &bytesRead, pdMS_TO_TICKS(100)) != ESP_OK) {
      continue;
    }

    // INMP441 delivers 24-bit samples left-justified in 32-bit words.
    // Take the top 16 bits to get the 16-bit PCM Sarvam expects.
    const size_t samples = bytesRead / sizeof(int32_t);
    int16_t *out = reinterpret_cast<int16_t *>(g_recordBuffer + written);
    for (size_t i = 0; i < samples; i++) {
      out[i] = static_cast<int16_t>(frame[i] >> 16);
    }
    written += samples * sizeof(int16_t);
  }
  return written;
}

static void playPcm(const uint8_t *pcm, size_t length) {
  setState(STATE_SPEAKING);
  size_t offset = 0;
  while (offset < length) {
    size_t written = 0;
    const size_t chunk = min((size_t)1024, length - offset);
    if (i2s_write(I2S_SPK_PORT, pcm + offset, chunk, &written, pdMS_TO_TICKS(200)) != ESP_OK) break;
    offset += written;
    if (written == 0) break;
  }
  i2s_zero_dma_buffer(I2S_SPK_PORT);
}

// ---------------------------------------------------------------------------
// Networking
// ---------------------------------------------------------------------------
static String baseUrl() {
  String url = SANGAM_API_USE_TLS ? "https://" : "http://";
  url += SANGAM_API_HOST;
  url += ":";
  url += String(SANGAM_API_PORT);
  return url;
}

static bool wifiConnect() {
  if (strlen(WIFI_SSID) == 0) return false;

  setState(STATE_WIFI_CONNECTING);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  const uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED) {
    if (millis() - start > WIFI_CONNECT_TIMEOUT_MS) return false;
    delay(250);
  }
  return true;
}

// Upload one utterance. Returns true when the backend accepted it.
static bool uploadUtterance(const uint8_t *wav, size_t length) {
  if (WiFi.status() != WL_CONNECTED) return false;

  setState(STATE_UPLOADING);

  HTTPClient http;
  const String url = baseUrl() + "/voice/interpret";
  if (!http.begin(url)) return false;

  http.setTimeout(HTTP_TIMEOUT_MS);
  http.addHeader("Content-Type", "audio/wav");
  http.addHeader("X-Sangam-Device", SANGAM_DEVICE_MODEL);
  if (strlen(SANGAM_DEVICE_TOKEN) > 0) {
    http.addHeader("Authorization", String("Bearer ") + SANGAM_DEVICE_TOKEN);
  }

  const int code = http.POST(const_cast<uint8_t *>(wav), length);
  const bool ok = (code >= 200 && code < 300);

  if (ok) {
    Serial.printf("[net] interpret ok (%d): %s\n", code, http.getString().c_str());
  } else {
    Serial.printf("[net] interpret failed (%d)\n", code);
  }

  http.end();
  return ok;
}

// ---------------------------------------------------------------------------
// Offline queue
// ---------------------------------------------------------------------------
static bool queueToSd(const uint8_t *wav, size_t length) {
  if (!g_sdReady) return false;
  if (g_queuedCount >= MAX_QUEUED_ITEMS) {
    Serial.println("[sd] queue full; dropping oldest is not implemented, refusing");
    return false;
  }

  char path[64];
  snprintf(path, sizeof(path), SD_QUEUE_DIR "/utt_%lu.wav", (unsigned long)millis());

  File f = SD.open(path, FILE_WRITE);
  if (!f) return false;
  const size_t written = f.write(wav, length);
  f.close();

  if (written != length) {
    SD.remove(path);
    return false;
  }

  g_queuedCount++;
  Serial.printf("[sd] queued %s (%u bytes, %lu pending)\n",
                path, (unsigned)length, (unsigned long)g_queuedCount);
  return true;
}

// Replay queued utterances once the network returns.
static void flushQueue() {
  if (!g_sdReady || WiFi.status() != WL_CONNECTED) return;

  File dir = SD.open(SD_QUEUE_DIR);
  if (!dir) return;

  while (true) {
    File entry = dir.openNextFile();
    if (!entry) break;
    if (entry.isDirectory()) { entry.close(); continue; }

    const size_t size = entry.size();
    uint8_t *buf = (uint8_t *)ps_malloc(size);
    if (!buf) { entry.close(); break; }

    const size_t read = entry.read(buf, size);
    String path = String(SD_QUEUE_DIR) + "/" + entry.name();
    entry.close();

    if (read == size && uploadUtterance(buf, size)) {
      SD.remove(path);
      if (g_queuedCount > 0) g_queuedCount--;
      Serial.printf("[sd] replayed and cleared %s\n", path.c_str());
    }
    free(buf);
  }
  dir.close();
}

// ---------------------------------------------------------------------------
// Setup / loop
// ---------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.printf("\nSangam Voice Terminal %s (%s)\n",
                SANGAM_FIRMWARE_VERSION, SANGAM_DEVICE_MODEL);

  pinMode(LED_STATUS_PIN, OUTPUT);
  pinMode(LED_RECORDING_PIN, OUTPUT);
  pinMode(LED_ERROR_PIN, OUTPUT);
  pinMode(BUTTON_PTT_PIN, INPUT_PULLUP);
  setState(STATE_BOOT);

  // Utterance buffer lives in PSRAM: ~960 KB will not fit in internal RAM.
  g_recordBuffer = (uint8_t *)ps_malloc(AUDIO_MAX_RECORD_BYTES);
  if (!g_recordBuffer) {
    Serial.println("[fatal] PSRAM allocation failed; is PSRAM enabled in the board config?");
    setState(STATE_ERROR);
    return;
  }
  Serial.printf("[mem] record buffer %u bytes in PSRAM\n", (unsigned)AUDIO_MAX_RECORD_BYTES);

  if (!initMicrophone()) { Serial.println("[fatal] I2S mic init failed"); setState(STATE_ERROR); return; }
  if (!initSpeaker())    { Serial.println("[fatal] I2S speaker init failed"); setState(STATE_ERROR); return; }
  Serial.println("[i2s] microphone and amplifier ready");

  SPI.begin(SD_SCK_PIN, SD_MISO_PIN, SD_MOSI_PIN, SD_CS_PIN);
  g_sdReady = SD.begin(SD_CS_PIN);
  if (g_sdReady) {
    if (!SD.exists(SD_QUEUE_DIR)) SD.mkdir(SD_QUEUE_DIR);
    Serial.println("[sd] offline queue ready");
  } else {
    // Not fatal: the terminal still works online, it just cannot survive
    // a network outage without losing the utterance.
    Serial.println("[sd] card unavailable; offline queueing disabled");
  }

  setState(wifiConnect() ? STATE_IDLE : STATE_OFFLINE);
  Serial.printf("[net] %s\n", WiFi.status() == WL_CONNECTED
                ? WiFi.localIP().toString().c_str() : "offline");
}

void loop() {
  if (g_state == STATE_ERROR) { delay(1000); return; }

  // Push-to-talk, debounced.
  if (digitalRead(BUTTON_PTT_PIN) == LOW) {
    delay(PTT_DEBOUNCE_MS);
    if (digitalRead(BUTTON_PTT_PIN) != LOW) return;

    setState(STATE_RECORDING);
    Serial.println("[audio] recording");
    const uint32_t started = millis();
    g_recordLength = recordWhileHeld();
    const uint32_t elapsed = millis() - started;

    if (elapsed < AUDIO_MIN_RECORD_MS || g_recordLength == 0) {
      Serial.println("[audio] too short, discarded");
      setState(WiFi.status() == WL_CONNECTED ? STATE_IDLE : STATE_OFFLINE);
      return;
    }
    Serial.printf("[audio] captured %u bytes in %lu ms\n",
                  (unsigned)g_recordLength, (unsigned long)elapsed);

    // Prepend a WAV header in place of the PCM start.
    static uint8_t header[44];
    writeWavHeader(header, g_recordLength);

    const size_t wavLength = sizeof(header) + g_recordLength;
    uint8_t *wav = (uint8_t *)ps_malloc(wavLength);
    if (!wav) {
      Serial.println("[mem] WAV allocation failed");
      setState(STATE_ERROR);
      return;
    }
    memcpy(wav, header, sizeof(header));
    memcpy(wav + sizeof(header), g_recordBuffer, g_recordLength);

    if (!uploadUtterance(wav, wavLength)) {
      // Never drop an operator's words because the network was down.
      if (queueToSd(wav, wavLength)) {
        Serial.println("[queue] stored for replay");
      } else {
        Serial.println("[queue] could not store; utterance lost");
      }
      setState(STATE_OFFLINE);
    } else {
      setState(STATE_IDLE);
    }

    free(wav);

    // Wait for release so one press yields one utterance.
    while (digitalRead(BUTTON_PTT_PIN) == LOW) delay(10);
  }

  // Periodic reconnect and queue replay.
  if (millis() - g_lastQueueFlush > QUEUE_FLUSH_INTERVAL_MS) {
    g_lastQueueFlush = millis();
    if (WiFi.status() != WL_CONNECTED) {
      setState(STATE_OFFLINE);
      wifiConnect();
    } else {
      flushQueue();
      if (g_state == STATE_OFFLINE) setState(STATE_IDLE);
    }
    Serial.printf("[state] %s, queued=%lu\n", stateName(g_state), (unsigned long)g_queuedCount);
  }

  delay(10);
}
