#include "main.h"
#include "esp_http_client.h"
#include "esp_websocket_client.h"
#include "esp_tls.h"
#include "cJSON.h"
#include "esp_crt_bundle.h"
#include "freertos/event_groups.h"

static const char *TAG = "SANGAM_CLIENT";

static esp_websocket_client_handle_t ws_client = NULL;
static char ws_token[128] = {0};
static bool ws_connected = false;
static TaskHandle_t ws_task_handle = NULL;
static SemaphoreHandle_t ws_mutex = NULL;
static QueueHandle_t ws_msg_queue = NULL;

typedef struct {
    char type[32];
    char payload[2048];
    char request_id[64];
} ws_message_t;

static void ws_event_handler(void *arg, esp_event_base_t event_base, int32_t event_id, void *event_data) {
    esp_websocket_event_data_t *data = (esp_websocket_event_data_t *)event_data;
    
    switch (event_id) {
        case WEBSOCKET_EVENT_CONNECTED:
            ESP_LOGI(TAG, "WebSocket connected");
            ws_connected = true;
            
            // Send auth message
            cJSON *auth = cJSON_CreateObject();
            cJSON_AddStringToObject(auth, "type", "auth");
            cJSON_AddStringToObject(auth, "token", ws_token);
            char *json = cJSON_PrintUnformatted(auth);
            esp_websocket_client_send_text(ws_client, json, strlen(json), portMAX_DELAY);
            cJSON_free(json);
            cJSON_Delete(auth);
            break;
            
        case WEBSOCKET_EVENT_DISCONNECTED:
            ESP_LOGW(TAG, "WebSocket disconnected");
            ws_connected = false;
            break;
            
        case WEBSOCKET_EVENT_DATA:
            if (data->data_len > 0) {
                ws_message_t msg = {0};
                cJSON *json = cJSON_ParseWithLength((char *)data->data_ptr, data->data_len);
                if (json) {
                    cJSON *type = cJSON_GetObjectItem(json, "type");
                    cJSON *payload = cJSON_GetObjectItem(json, "payload");
                    cJSON *req_id = cJSON_GetObjectItem(json, "request_id");
                    
                    if (type) strncpy(msg.type, type->valuestring, sizeof(msg.type) - 1);
                    if (payload) {
                        char *payload_str = cJSON_PrintUnformatted(payload);
                        strncpy(msg.payload, payload_str, sizeof(msg.payload) - 1);
                        cJSON_free(payload_str);
                    }
                    if (req_id) strncpy(msg.request_id, req_id->valuestring, sizeof(msg.request_id) - 1);
                    
                    xQueueSend(g_compliance_queue, &msg, pdMS_TO_TICKS(100));
                    cJSON_free(json);
                }
            }
            break;
            
        case WEBSOCKET_EVENT_ERROR:
            ESP_LOGE(TAG, "WebSocket error: %s", (char *)data->data_ptr);
            break;
    }
}

esp_err_t sangam_client_init(void) {
    ESP_LOGI(TAG, "Initializing Sangam client");
    
    ws_mutex = xSemaphoreCreateMutex();
    ws_msg_queue = xQueueCreate(16, sizeof(ws_message_t));
    
    if (!ws_mutex || !ws_msg_queue) {
        return ESP_ERR_NO_MEM;
    }
    
    return ESP_OK;
}

void sangam_client_set_token(const char *token) {
    if (token) {
        strncpy(ws_token, token, sizeof(ws_token) - 1);
    }
}

esp_err_t sangam_client_connect(void) {
    ESP_LOGI(TAG, "Connecting to Sangam WebSocket");
    
    if (!ws_token[0]) {
        ESP_LOGE(TAG, "No token set");
        return ESP_ERR_INVALID_STATE;
    }
    
    esp_websocket_client_config_t ws_cfg = {
        .uri = SANGAM_WS_URL,
        .headers = NULL,
        .subprotocol = NULL,
        .user_agent = "SangamVoiceAgent/1.0",
        .cert_pem = NULL,
        .skip_cert_common_name_check = false,
        .transport_type = WEBSOCKET_TRANSPORT_OVER_TLS,
        .skip_auto_reconnect = false,
        .reconnect_timeout_ms = 5000,
        .network_timeout_ms = 30000,
        .buffer_size = 8192,
    };
    
    ws_client = esp_websocket_client_init(&ws_cfg);
    if (!ws_client) {
        ESP_LOGE(TAG, "Failed to create WebSocket client");
        return ESP_FAIL;
    }
    
    esp_websocket_register_events(ws_client, WEBSOCKET_EVENT_ANY, ws_event_handler, NULL);
    
    esp_err_t ret = esp_websocket_client_start(ws_client);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to start WebSocket: %s", esp_err_to_name(ret));
        return ret;
    }
    
    // Wait for connection
    int retries = 0;
    while (!ws_connected && retries < 50) {
        vTaskDelay(pdMS_TO_TICKS(100));
        retries++;
    }
    
    if (!ws_connected) {
        ESP_LOGE(TAG, "WebSocket connection timeout");
        return ESP_ERR_TIMEOUT;
    }
    
    ESP_LOGI(TAG, "WebSocket connected successfully");
    return ESP_OK;
}

void sangam_client_disconnect(void) {
    if (ws_client) {
        esp_websocket_client_stop(ws_client);
        esp_websocket_client_destroy(ws_client);
        ws_client = NULL;
        ws_connected = false;
    }
}

bool sangam_client_is_connected(void) {
    return ws_connected;
}

esp_err_t sangam_send_message(const char *type, const char *payload, const char *request_id) {
    if (!ws_connected || !ws_client) {
        return ESP_ERR_INVALID_STATE;
    }
    
    cJSON *msg = cJSON_CreateObject();
    cJSON_AddStringToObject(msg, "type", type);
    if (payload) {
        cJSON *payload_json = cJSON_Parse(payload);
        if (payload_json) {
            cJSON_AddItemToObject(msg, "payload", payload_json);
        }
    }
    if (request_id) {
        cJSON_AddStringToObject(msg, "request_id", request_id);
    }
    
    char *json = cJSON_PrintUnformatted(msg);
    cJSON_Delete(msg);
    
    if (!json) return ESP_ERR_NO_MEM;
    
    int ret = esp_websocket_client_send_text(ws_client, json, strlen(json), portMAX_DELAY);
    cJSON_free(json);
    
    return (ret > 0) ? ESP_OK : ESP_FAIL;
}

esp_err_t sangam_subscribe_workflow(const char *workflow_id) {
    char req_id[64];
    snprintf(req_id, sizeof(req_id), "sub_%lu", esp_timer_get_time() / 1000);
    
    cJSON *payload = cJSON_CreateObject();
    cJSON_AddStringToObject(payload, "workflow_id", workflow_id);
    
    char *payload_str = cJSON_PrintUnformatted(payload);
    esp_err_t ret = sangam_send_message("subscribe_workflow", payload_str, req_id);
    cJSON_free(payload_str);
    cJSON_Delete(payload);
    
    return ret;
}

esp_err_t sangam_send_voice_chunk(const uint8_t *data, size_t len, bool final) {
    if (!ws_connected || !ws_client) {
        return ESP_ERR_INVALID_STATE;
    }
    
    cJSON *msg = cJSON_CreateObject();
    cJSON_AddStringToObject(msg, "type", "voice_chunk");
    cJSON_AddStringToObject(msg, "audio", ""); // base64 encoded
    cJSON_AddBoolToObject(msg, "final", final);
    
    char *json = cJSON_PrintUnformatted(msg);
    cJSON_Delete(msg);
    
    if (!json) return ESP_ERR_NO_MEM;
    
    int ret = esp_websocket_client_send_text(ws_client, json, strlen(json), portMAX_DELAY);
    cJSON_free(json);
    
    return (ret > 0) ? ESP_OK : ESP_FAIL;
}