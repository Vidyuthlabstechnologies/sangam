#include "main.h"
#include "esp_log.h"
#include "esp_system.h"
#include "esp_spi_flash.h"
#include "esp_ota_ops.h"
#include "nvs_flash.h"
#include "esp_netif.h"
#include "esp_event.h"
#include "esp_wifi.h"
#include "esp_spiffs.h"
#include "esp_vfs_fat.h"
#include "driver/sdmmc_host.h"
#include "driver/sdspi_host.h"
#include "sdmmc_cmd.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "freertos/semphr.h"
#include "freertos/event_groups.h"
#include "driver/gpio.h"
#include "driver/i2s.h"
#include "driver/sdmmc_host.h"
#include "driver/sdspi_host.h"
#include "driver/i2s_std.h"
#include "driver/i2s_std_gpio.h"
#include "esp_vfs_fat.h"
#include "esp_timer.h"
#include "esp_ota_ops.h"
#include "esp_app_format.h"
#include "esp_app_desc.h"
#include "esp_ota_ops.h"
#include "esp_ota_ops.h"
#include "esp_app_format.h"
#include "esp_app_desc.h"
#include "esp_ota_ops.h"
#include "esp_ota_ops.h"
#include "esp_app_format.h"
#include "esp_app_desc.h"
#include "esp_ota_ops.h"
#include "esp_ota_ops.h"
#include "esp_app_format.h"
#include "esp_app_desc.h"
#include "esp_ota_ops.h"

static const char *TAG = "MAIN";

static device_state_t g_device_state = DEVICE_STATE_INIT;
static device_config_t g_device_config = {0};
static QueueHandle_t g_audio_record_queue = NULL;
static QueueHandle_t g_audio_playback_queue = NULL;
static QueueHandle_t g_compliance_queue = NULL;
static SemaphoreHandle_t g_state_mutex = NULL;
static EventGroupHandle_t g_wifi_event_group = NULL;
static const int WIFI_CONNECTED_BIT = BIT0;
static const int WIFI_FAIL_BIT = BIT1;

static const char *WIFI_EVENT_TAG = "WIFI";
static const char *AUDIO_TAG = "AUDIO";
static const char *WS_TAG = "WEBSOCKET";
static const char *COMPLIANCE_TAG = "COMPLIANCE";
static const char *NVS_TAG = "NVS";

static int s_retry_num = 0;
#define MAX_WIFI_RETRY 5

static void event_handler(void *arg, esp_event_base_t event_base, int32_t event_id, void *event_data) {
    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        if (s_retry_num < MAX_WIFI_RETRY) {
            esp_wifi_connect();
            s_retry_num++;
            ESP_LOGI(WIFI_EVENT_TAG, "Retry to connect to the AP (%d/%d)", s_retry_num, MAX_WIFI_RETRY);
        } else {
            xEventGroupSetBits(g_wifi_event_group, WIFI_FAIL_BIT);
        }
        ESP_LOGI(WIFI_EVENT_TAG, "Failed to connect to WiFi");
    } else if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *event = (ip_event_got_ip_t *)event_data;
        ESP_LOGI(WIFI_EVENT_TAG, "Got IP:" IPSTR, IP2STR(&event->ip_info.ip));
        s_retry_num = 0;
        xEventGroupSetBits(g_wifi_event_group, WIFI_CONNECTED_BIT);
    }
}

void device_state_set(device_state_t state) {
    if (g_state_mutex) {
        xSemaphoreTake(g_state_mutex, portMAX_DELAY);
    }
    g_device_state = state;
    if (g_state_mutex) {
        xSemaphoreGive(g_state_mutex);
    }
    ESP_LOGI(TAG, "Device state changed to: %d", state);
}

device_state_t device_state_get(void) {
    device_state_t state = DEVICE_STATE_INIT;
    if (g_state_mutex) {
        xSemaphoreTake(g_state_mutex, portMAX_DELAY);
    }
    state = g_device_state;
    if (g_state_mutex) {
        xSemaphoreGive(g_state_mutex);
    }
    return state;
}

static void wifi_init_sta(void) {
    g_wifi_event_group = xEventGroupCreate();

    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    ESP_ERROR_CHECK(esp_event_handler_instance_register(WIFI_EVENT, ESP_EVENT_ANY_ID, &event_handler, NULL, NULL));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(IP_EVENT, IP_EVENT_STA_GOT_IP, &event_handler, NULL, NULL));

    wifi_config_t wifi_config = {
        .sta = {
            .ssid = "",
            .password = "",
            .threshold.authmode = WIFI_AUTH_WPA2_PSK,
            .pmf_cfg = {
                .capable = true,
                .required = false
            },
        },
    };

    // Load from NVS if available
    nvs_handle_t nvs_handle;
    if (nvs_open("wifi", NVS_READONLY, &nvs_handle) == ESP_OK) {
        size_t ssid_len = sizeof(((wifi_config_t *)0)->sta.ssid);
        size_t pass_len = sizeof(((wifi_config_t *)0)->sta.password);
        nvs_get_str(nvs_handle, "ssid", (char *)wifi_config.sta.ssid, &ssid_len);
        nvs_get_str(nvs_handle, "password", (char *)wifi_config.sta.password, &pass_len);
        nvs_close(nvs_handle);
    }

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());

    ESP_LOGI(WIFI_EVENT_TAG, "WiFi initialization complete");
}

static void nvs_init(void) {
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);
    ESP_LOGI(NVS_TAG, "NVS initialized");
}

void app_main(void) {
    ESP_LOGI(TAG, "Starting Sangam Voice Agent v%s", SANGAM_FIRMWARE_VERSION);
    ESP_LOGI(TAG, "Device: %s, Model: %s", SANGAM_DEVICE_NAME, SANGAM_DEVICE_MODEL);
    ESP_LOGI(TAG, "Free heap: %lu bytes", esp_get_free_heap_size());
    ESP_LOGI(TAG, "PSRAM size: %d bytes", esp_spiram_get_size());

    // Initialize NVS
    nvs_init();

    // Create mutex and queues
    g_state_mutex = xSemaphoreCreateMutex();
    g_audio_record_queue = xQueueCreate(8, sizeof(int16_t *));
    g_audio_playback_queue = xQueueCreate(8, sizeof(int16_t *));
    g_compliance_queue = xQueueCreate(8, sizeof(compliance_request_t));

    if (!g_state_mutex || !g_audio_record_queue || !g_audio_playback_queue || !g_compliance_queue) {
        ESP_LOGE(TAG, "Failed to create synchronization primitives");
        return;
    }

    // Initialize hardware
    ESP_ERROR_CHECK(ui_indicators_init());
    ESP_ERROR_CHECK(sd_logger_init());
    
    // Initialize NVS and load config
    device_config_t config = {0};
    nvs_handle_t nvs_handle;
    if (nvs_open("config", NVS_READONLY, &nvs_handle) == ESP_OK) {
        size_t len;
        nvs_get_str(nvs_handle, "sangam_key", g_device_config.sangam_api_key, &(size_t){sizeof(g_device_config.sangam_api_key)});
        nvs_get_str(nvs_handle, "sarvam_key", g_device_config.sarvam_api_key, &(size_t){sizeof(g_device_config.sarvam_api_key)});
        nvs_get_str(nvs_handle, "device_id", g_device_config.device_id, &(size_t){sizeof(g_device_config.device_id)});
        nvs_get_str(nvs_handle, "device_token", g_device_config.device_token, &(size_t){sizeof(g_device_config.device_token)});
        nvs_close(nvs_handle);
    }

    // Initialize subsystems
    ESP_ERROR_CHECK(audio_pipeline_init());
    ESP_ERROR_CHECK(sangam_client_init());
    ESP_ERROR_CHECK(sarvam_client_init());
    ESP_ERROR_CHECK(compliance_actions_init());
    ESP_ERROR_CHECK(wifi_provisioning_init());
    ESP_ERROR_CHECK(sd_logger_init());
    ESP_ERROR_CHECK(ui_indicators_init());
    
    device_state_set(DEVICE_STATE_WIFI_CONNECTING);
    wifi_init_sta();

    // Wait for WiFi connection
    EventBits_t bits = xEventGroupWaitBits(g_wifi_event_group,
                                           WIFI_CONNECTED_BIT | WIFI_FAIL_BIT,
                                           pdFALSE, pdFALSE, pdMS_TO_TICKS(30000));
    
    if (bits & WIFI_CONNECTED_BIT) {
        device_state_set(DEVICE_STATE_WIFI_CONNECTED);
        ESP_LOGI(TAG, "WiFi connected");
        
        // Initialize Sangam client with token
        sangam_client_set_token(g_device_config.device_token);
        
        // Initialize Sarvam client
        sarvam_client_init();
        
        device_state_set(DEVICE_STATE_AUTHENTICATED);
        
        // Start audio pipeline
        audio_pipeline_start();
        
        // Start tasks
        xTaskCreate(audio_record_task, "audio_record", 8192, NULL, 5, NULL);
        xTaskCreate(audio_playback_task, "audio_playback", 8192, NULL, 5, NULL);
        xTaskCreate(websocket_task, "websocket", 8192, NULL, 5, NULL);
        xTaskCreate(compliance_task, "compliance", 8192, NULL, 4, NULL);
        xTaskCreate(status_led_task, "status_led", 2048, NULL, 2, NULL);
        xTaskCreate(button_task, "button", 2048, NULL, 3, NULL);
        
        device_state_set(DEVICE_STATE_IDLE);
        ESP_LOGI(TAG, "Sangam Voice Agent started successfully");
        
        // Print device info
        ESP_LOGI(TAG, "Device ID: %s", g_device_config.device_id);
        ESP_LOGI(TAG, "Free heap: %lu bytes", esp_get_free_heap_size());
        ESP_LOGI(TAG, "PSRAM free: %d bytes", heap_caps_get_free_size(MALLOC_CAP_SPIRAM));
    } else {
        ESP_LOGE(TAG, "WiFi connection failed, starting provisioning mode");
        device_state_set(DEVICE_STATE_ERROR);
        wifi_provisioning_start();
    }

    // Main loop
    while (1) {
        vTaskDelay(pdMS_TO_TICKS(10000));
        ESP_LOGI(TAG, "Free heap: %lu, PSRAM: %d", esp_get_free_heap_size(), heap_caps_get_free_size(MALLOC_CAP_SPIRAM));
    }
}