#ifndef MAIN_H
#define MAIN_H

#include <stdint.h>
#include <stdbool.h>
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

// Device configuration
#define SANGAM_DEVICE_NAME      "sangam-voice-agent"
#define SANGAM_DEVICE_MODEL     "ESP32-S3-VoiceAgent"
#define SANGAM_FIRMWARE_VERSION "1.0.0"

// Hardware pins (adjust for your specific board)
#define I2S_MIC_SCK_PIN         12   // INMP441 SCK
#define I2S_MIC_WS_PIN          11   // INMP441 WS
#define I2S_MIC_SD_PIN          10   // INMP441 SD
#define I2S_SPK_BCLK_PIN        4    // MAX98357A BCLK
#define I2S_SPK_LRC_PIN         5    // MAX98357A LRC
#define I2S_SPK_DIN_PIN         6    // MAX98357A DIN

// LED indicators
#define LED_STATUS_PIN          8    // Status LED
#define LED_RECORDING_PIN       9    // Recording LED
#define LED_ERROR_PIN           10   // Error LED

// Button
#define BUTTON_PTT_PIN          0    // Push-to-talk button (active low)

// SD Card
#define SD_CARD_MOUNT_POINT     "/sdcard"
#define SD_CARD_CS_PIN          13

// Audio configuration
#define SAMPLE_RATE             16000
#define SAMPLE_BITS             16
#define CHANNELS                1
#define FRAME_SIZE              512
#define BUFFER_COUNT            8

// Audio buffers
#define AUDIO_BUFFER_SIZE       (FRAME_SIZE * 2)
#define AUDIO_BUFFER_COUNT      4

// Network
#define WIFI_SSID_MAX_LEN       32
#define WIFI_PASSWORD_MAX_LEN   64
#define SANGAM_API_BASE_URL     "https://api.sangam.ai"
#define SANGAM_WS_URL           "wss://api.sangam.ai/ws/voice"
#define SARVAM_API_BASE_URL     "https://api.sarvam.ai"

// Audio format
#define AUDIO_FORMAT_PCM_16K    1
#define AUDIO_FORMAT_OPUS       2

// Compliance action types
typedef enum {
    ACTION_NONE = 0,
    ACTION_VERIFY_VENDOR,
    ACTION_CHECK_NPPA,
    ACTION_CREATE_PO,
    ACTION_VERIFY_GST,
    ACTION_CHECK_RERA,
    ACTION_VERIFY_FSSAI,
    ACTION_VERIFY_GEM,
    ACTION_CHECK_ICEGATE,
    ACTION_VERIFY_IEC,
    ACTION_VERIFY_DIN,
    ACTION_VERIFY_EPFO,
    ACTION_VERIFY_PAN,
    ACTION_VERIFY_DIGILOCKER,
    ACTION_GET_SCHEMES,
    ACTION_GET_MOSPI_INDICATOR,
    ACTION_GET_LABOR_DATA,
    ACTION_ANALYZE_LOCATION,
    ACTION_GET_POWER_DATA,
    ACTION_CREATE_ESCROW,
    ACTION_RELEASE_ESCROW,
    ACTION_CREATE_INVOICE,
    ACTION_VERIFY_PAYMENT,
    ACTION_VERIFY_DIGILOCKER,
    ACTION_VERIFY_ICEGATE,
    ACTION_VERIFY_IEC,
    ACTION_VERIFY_RERA,
    ACTION_VERIFY_FSSAI,
    ACTION_VERIFY_GEM,
    ACTION_VERIFY_PAN,
    ACTION_VERIFY_EPFO,
    ACTION_VERIFY_DIN,
    ACTION_VERIFY_DIGILOCKER,
    ACTION_VERIFY_ICEGATE,
    ACTION_VERIFY_IEC,
    ACTION_VERIFY_RERA,
    ACTION_VERIFY_FSSAI,
    ACTION_VERIFY_GEM,
} compliance_action_type_t;

// Device state
typedef enum {
    DEVICE_STATE_INIT = 0,
    DEVICE_STATE_WIFI_CONNECTING,
    DEVICE_STATE_WIFI_CONNECTED,
    DEVICE_STATE_AUTHENTICATING,
    DEVICE_STATE_AUTHENTICATED,
    DEVICE_STATE_IDLE,
    DEVICE_STATE_LISTENING,
    DEVICE_STATE_PROCESSING,
    DEVICE_STATE_SPEAKING,
    DEVICE_STATE_ERROR,
    DEVICE_STATE_OTA_UPDATE,
} device_state_t;

// Audio format
typedef enum {
    AUDIO_FORMAT_PCM_16K = 1,
    AUDIO_FORMAT_OPUS = 2,
} audio_format_t;

// Configuration structure
typedef struct {
    char wifi_ssid[64];
    char wifi_password[64];
    char sangam_api_key[128];
    char sarvam_api_key[128];
    char device_id[64];
    char device_token[128];
    bool use_sarvam_stt;
    bool use_sarvam_tts;
    bool use_sarvam_llm;
    int sample_rate;
    int frame_size;
    int buffer_count;
    bool debug_mode;
} device_config_t;

// Audio frame structure
typedef struct {
    int16_t *data;
    size_t size;
    uint64_t timestamp;
    uint32_t sequence;
} audio_frame_t;

// Compliance action request
typedef struct {
    compliance_action_type_t type;
    char payload[2048];
    char request_id[64];
    uint64_t timestamp;
} compliance_request_t;

// Compliance action response
typedef struct {
    char request_id[64];
    bool success;
    char response[4096];
    int error_code;
    char error_message[256];
} compliance_response_t;

// Function prototypes
esp_err_t app_init(void);
esp_err_t audio_pipeline_init(void);
esp_err_t sangam_client_init(void);
esp_err_t sarvam_client_init(void);
esp_err_t compliance_actions_init(void);
esp_err_t wifi_provisioning_init(void);
esp_err_t sd_logger_init(void);
esp_err_t ui_indicators_init(void);
esp_err_t audio_pipeline_start(void);
esp_err_t audio_pipeline_stop(void);
void device_state_set(device_state_t state);
device_state_t device_state_get(void);
void button_ptt_callback(void *arg);
void audio_record_task(void *arg);
void audio_playback_task(void *arg);
void websocket_task(void *arg);
void compliance_task(void *arg);
void status_led_task(void *arg);
void button_task(void *arg);

#ifdef __cplusplus
}
#endif

#endif // MAIN_H