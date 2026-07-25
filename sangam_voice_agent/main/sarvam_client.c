#include "main.h"
#include "esp_http_client.h"
#include "esp_crt_bundle.h"
#include "cJSON.h"
#include "esp_timer.h"

static const char *TAG = "SARVAM_CLIENT";

#define SARVAM_BASE_URL "https://api.sarvam.ai"
#define SARVAM_STT_ENDPOINT "/speech-to-text"
#define SARVAM_TTS_ENDPOINT "/text-to-speech"
#define SARVAM_TRANSLATE_ENDPOINT "/translate"
#define SARVAM_LLM_ENDPOINT "/v1/chat/completions"
#define SARVAM_IDENTIFY_ENDPOINT "/text-lid"
#define SARVAM_TRANSLITERATE_ENDPOINT "/transliterate"

static char sarvam_api_key[128] = {0};
static SemaphoreHandle_t sarvam_mutex = NULL;

esp_err_t sarvam_client_init(void) {
    ESP_LOGI(TAG, "Initializing Sarvam AI client");
    
    sarvam_mutex = xSemaphoreCreateMutex();
    if (!sarvam_mutex) {
        return ESP_ERR_NO_MEM;
    }
    
    return ESP_OK;
}

void sarvam_client_set_api_key(const char *api_key) {
    if (api_key) {
        strncpy(sarvam_api_key, api_key, sizeof(sarvam_api_key) - 1);
    }
}

static esp_err_t sarvam_http_request(const char *endpoint, const char *payload, char **response, int *response_len) {
    if (!sarvam_api_key[0]) {
        ESP_LOGE(TAG, "Sarvam API key not set");
        return ESP_ERR_INVALID_STATE;
    }
    
    char url[256];
    snprintf(url, sizeof(url), "%s%s", SARVAM_BASE_URL, endpoint);
    
    esp_http_client_config_t config = {
        .url = url,
        .method = HTTP_METHOD_POST,
        .timeout_ms = 60000,
        .crt_bundle_attach = esp_crt_bundle_attach,
        .buffer_size = 8192,
        .buffer_size_tx = 8192,
    };
    
    esp_http_client_handle_t client = esp_http_client_init(&config);
    if (!client) {
        ESP_LOGE(TAG, "Failed to init HTTP client");
        return ESP_FAIL;
    }
    
    esp_http_client_set_header(client, "Content-Type", "application/json");
    esp_http_client_set_header(client, "api-subscription-key", sarvam_api_key);
    esp_http_client_set_post_field(client, payload, strlen(payload));
    
    esp_err_t err = esp_http_client_perform(client);
    if (err == ESP_OK) {
        int status = esp_http_client_get_status_code(client);
        if (status == 200) {
            *response_len = esp_http_client_read(client, *response, 16384);
            if (*response_len > 0) {
                (*response)[*response_len] = '\0';
            }
        } else {
            ESP_LOGE(TAG, "HTTP error: %d", status);
            err = ESP_FAIL;
        }
    } else {
        ESP_LOGE(TAG, "HTTP request failed: %s", esp_err_to_name(err));
    }
    
    esp_http_client_cleanup(client);
    return err;
}

esp_err_t sarvam_stt(const int16_t *audio_data, size_t samples, const char *language_code, char **transcript) {
    // TODO: Implement multipart form upload for audio
    ESP_LOGW(TAG, "STT not fully implemented yet");
    return ESP_ERR_NOT_SUPPORTED;
}

esp_err_t sarvam_tts(const char *text, const char *target_language_code, const char *speaker, uint8_t **audio_data, size_t *audio_len) {
    if (!text || !target_language_code || !speaker) {
        return ESP_ERR_INVALID_ARG;
    }
    
    cJSON *payload = cJSON_CreateObject();
    cJSON_AddStringToObject(payload, "text", text);
    cJSON_AddStringToObject(payload, "target_language_code", target_language_code);
    cJSON_AddStringToObject(payload, "speaker", speaker);
    cJSON_AddStringToObject(payload, "model", "bulbul:v3");
    cJSON_AddBoolToObject(payload, "enable_preprocessing", true);
    
    char *payload_str = cJSON_PrintUnformatted(payload);
    cJSON_Delete(payload);
    
    char *response = malloc(8192);
    int response_len = 0;
    
    esp_err_t err = sarvam_http_request(SARVAM_TTS_ENDPOINT, payload_str, &response, &response_len);
    free(payload_str);
    
    if (err != ESP_OK) {
        free(response);
        return err;
    }
    
    cJSON *json = cJSON_Parse(response);
    free(response);
    
    if (!json) {
        return ESP_FAIL;
    }
    
    cJSON *audios = cJSON_GetObjectItem(json, "audios");
    if (cJSON_IsArray(audios) && cJSON_GetArraySize(audios) > 0) {
        cJSON *first = cJSON_GetArrayItem(audios, 0);
        cJSON *audio_base64 = cJSON_GetObjectItem(first, "audio_base64");
        
        if (cJSON_IsString(audio_base64)) {
            // Decode base64
            size_t decode_len = 0;
            size_t encoded_len = strlen(audio_base64->valuestring);
            *audio_len = encoded_len * 3 / 4;
            *audio_data = malloc(*audio_len);
            mbedtls_base64_decode(*audio_data, *audio_len, &decode_len, 
                                 (const unsigned char *)audio_base64->valuestring, encoded_len);
            *audio_len = decode_len;
            cJSON_Delete(json);
            return ESP_OK;
        }
    }
    
    cJSON_Delete(json);
    return ESP_FAIL;
}

esp_err_t sarvam_translate(const char *text, const char *source_lang, const char *target_lang, char **translated) {
    if (!text || !target_lang) {
        return ESP_ERR_INVALID_ARG;
    }
    
    cJSON *payload = cJSON_CreateObject();
    cJSON_AddStringToObject(payload, "input", text);
    cJSON_AddStringToObject(payload, "source_language_code", source_lang ? source_lang : "auto");
    cJSON_AddStringToObject(payload, "target_language_code", target_lang);
    cJSON_AddStringToObject(payload, "model", "mayura:v1");
    cJSON_AddBoolToObject(payload, "enable_preprocessing", true);
    
    char *payload_str = cJSON_PrintUnformatted(payload);
    cJSON_Delete(payload);
    
    char *response = malloc(4096);
    int response_len = 0;
    
    esp_err_t err = sarvam_http_request(SARVAM_TRANSLATE_ENDPOINT, payload_str, &response, &response_len);
    free(payload_str);
    
    if (err != ESP_OK) {
        free(response);
        return err;
    }
    
    cJSON *json = cJSON_Parse(response);
    free(response);
    
    if (!json) return ESP_FAIL;
    
    cJSON *translated_text = cJSON_GetObjectItem(json, "translated_text");
    if (cJSON_IsString(translated_text)) {
        *translated = strdup(translated_text->valuestring);
    }
    
    cJSON_Delete(json);
    return (*translated) ? ESP_OK : ESP_FAIL;
}

esp_err_t sarvam_llm_complete(const char *system_prompt, const char *user_prompt, const char *model, char **completion) {
    if (!user_prompt) {
        return ESP_ERR_INVALID_ARG;
    }
    
    cJSON *payload = cJSON_CreateObject();
    cJSON_AddStringToObject(payload, "model", model ? model : "sarvam-30b");
    
    cJSON *messages = cJSON_CreateArray();
    
    if (system_prompt) {
        cJSON *sys_msg = cJSON_CreateObject();
        cJSON_AddStringToObject(sys_msg, "role", "system");
        cJSON_AddStringToObject(sys_msg, "content", system_prompt);
        cJSON_AddItemToArray(messages, sys_msg);
    }
    
    cJSON *user_msg = cJSON_CreateObject();
    cJSON_AddStringToObject(user_msg, "role", "user");
    cJSON_AddStringToObject(user_msg, "content", user_prompt);
    cJSON_AddItemToArray(messages, user_msg);
    
    cJSON_AddItemToObject(payload, "messages", messages);
    cJSON_AddNumberToObject(payload, "temperature", 0.3);
    cJSON_AddNumberToObject(payload, "max_tokens", 512);
    cJSON_AddNumberToObject(payload, "top_p", 0.9);
    
    char *payload_str = cJSON_PrintUnformatted(payload);
    cJSON_Delete(payload);
    
    char *response = malloc(8192);
    int response_len = 0;
    
    esp_err_t err = sarvam_http_request(SARVAM_LLM_ENDPOINT, payload_str, &response, &response_len);
    free(payload_str);
    
    if (err != ESP_OK) {
        free(response);
        return err;
    }
    
    cJSON *json = cJSON_Parse(response);
    free(response);
    
    if (!json) return ESP_FAIL;
    
    cJSON *choices = cJSON_GetObjectItem(json, "choices");
    if (cJSON_IsArray(choices) && cJSON_GetArraySize(choices) > 0) {
        cJSON *first = cJSON_GetArrayItem(choices, 0);
        cJSON *message = cJSON_GetObjectItem(first, "message");
        cJSON *content = cJSON_GetObjectItem(message, "content");
        
        if (cJSON_IsString(content)) {
            *completion = strdup(content->valuestring);
        }
    }
    
    cJSON_Delete(json);
    return (*completion) ? ESP_OK : ESP_FAIL;
}

esp_err_t sarvam_identify_language(const char *text, char **language_code, char **script_code) {
    if (!text) return ESP_ERR_INVALID_ARG;
    
    cJSON *payload = cJSON_CreateObject();
    cJSON_AddStringToObject(payload, "input", text);
    
    char *payload_str = cJSON_PrintUnformatted(payload);
    cJSON_Delete(payload);
    
    char *response = malloc(2048);
    int response_len = 0;
    
    esp_err_t err = sarvam_http_request(SARVAM_IDENTIFY_ENDPOINT, payload_str, &response, &response_len);
    free(payload_str);
    
    if (err != ESP_OK) {
        free(response);
        return err;
    }
    
    cJSON *json = cJSON_Parse(response);
    free(response);
    
    if (!json) return ESP_FAIL;
    
    cJSON *lang = cJSON_GetObjectItem(json, "language_code");
    cJSON *script = cJSON_GetObjectItem(json, "script_code");
    
    if (cJSON_IsString(lang)) *language_code = strdup(lang->valuestring);
    if (cJSON_IsString(script)) *script_code = strdup(script->valuestring);
    
    cJSON_Delete(json);
    return ESP_OK;
}

esp_err_t sarvam_transliterate(const char *text, const char *source_lang, const char *target_lang, char **transliterated) {
    if (!text || !source_lang || !target_lang) return ESP_ERR_INVALID_ARG;
    
    cJSON *payload = cJSON_CreateObject();
    cJSON_AddStringToObject(payload, "input", text);
    cJSON_AddStringToObject(payload, "source_language_code", source_lang);
    cJSON_AddStringToObject(payload, "target_language_code", target_lang);
    
    char *payload_str = cJSON_PrintUnformatted(payload);
    cJSON_Delete(payload);
    
    char *response = malloc(4096);
    int response_len = 0;
    
    esp_err_t err = sarvam_http_request(SARVAM_TRANSLITERATE_ENDPOINT, payload_str, &response, &response_len);
    free(payload_str);
    
    if (err != ESP_OK) {
        free(response);
        return err;
    }
    
    cJSON *json = cJSON_Parse(response);
    free(response);
    
    if (!json) return ESP_FAIL;
    
    cJSON *trans = cJSON_GetObjectItem(json, "transliterated_text");
    if (cJSON_IsString(trans)) {
        *transliterated = strdup(trans->valuestring);
    }
    
    cJSON_Delete(json);
    return (*transliterated) ? ESP_OK : ESP_FAIL;
}