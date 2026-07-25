#include "main.h"
#include "driver/i2s_std.h"
#include "driver/i2s_std_gpio.h"
#include "freertos/ringbuf.h"
#include "esp_dsp.h"
#include <string.h>

static const char *TAG = "AUDIO_PIPELINE";

static i2s_chan_handle_t rx_handle = NULL;
static i2s_chan_handle_t tx_handle = NULL;
static RingbufHandle_t rb_rx = NULL;
static RingbufHandle_t rb_tx = NULL;
static bool recording = false;
static bool playing = false;
static TaskHandle_t record_task_handle = NULL;
static TaskHandle_t playback_task_handle = NULL;

static i2s_chan_config_t rx_chan_cfg = {
    .id = I2S_NUM_0,
    .role = I2S_ROLE_MASTER,
    .dma_desc_num = 6,
    .dma_frame_num = 240,
    .auto_clear = true,
};

static i2s_chan_config_t tx_chan_cfg = {
    .id = I2S_NUM_1,
    .role = I2S_ROLE_MASTER,
    .dma_desc_num = 6,
    .dma_frame_num = 240,
    .auto_clear = true,
};

static i2s_std_config_t rx_std_cfg = {
    .clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(16000),
    .slot_cfg = I2S_STD_MSB_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO),
    .gpio_cfg = {
        .mclk = I2S_GPIO_UNUSED,
        .bclk = I2S_MIC_BCLK_PIN,
        .ws = I2S_MIC_WS_PIN,
        .dout = I2S_GPIO_UNUSED,
        .din = I2S_MIC_SD_PIN,
        .mclk_inv = false,
        .bclk_inv = false,
        .ws_inv = false,
    },
};

static i2s_std_config_t tx_std_cfg = {
    .clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(16000),
    .slot_cfg = I2S_STD_MSB_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO),
    .gpio_cfg = {
        .mclk = I2S_GPIO_UNUSED,
        .bclk = I2S_SPK_BCLK_PIN,
        .ws = I2S_SPK_LRC_PIN,
        .dout = I2S_SPK_DIN_PIN,
        .din = I2S_GPIO_UNUSED,
        .mclk_inv = false,
        .bclk_inv = false,
        .ws_inv = false,
    },
};

esp_err_t audio_pipeline_init(void) {
    ESP_LOGI(TAG, "Initializing audio pipeline");

    // Initialize I2S RX channel (MIC)
    esp_err_t ret = i2s_new_channel(&rx_chan_cfg, &rx_handle, NULL);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to create RX channel: %s", esp_err_to_name(ret));
        return ret;
    }

    ret = i2s_channel_init_std_mode(rx_handle, &rx_std_cfg);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to init RX std mode: %s", esp_err_to_name(ret));
        return ret;
    }

    // Initialize I2S TX channel (Speaker)
    ret = i2s_new_channel(&tx_chan_cfg, NULL, &tx_handle);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to create TX channel: %s", esp_err_to_name(ret));
        return ret;
    }

    ret = i2s_channel_init_std_mode(tx_handle, &tx_std_cfg);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to init TX std mode: %s", esp_err_to_name(ret));
        return ret;
    }

    // Create ring buffers
    rb_rx = xRingbufferCreate(16384, RINGBUF_TYPE_BYTEBUF);
    rb_tx = xRingbufferCreate(16384, RINGBUF_TYPE_BYTEBUF);

    if (!rb_rx || !rb_tx) {
        ESP_LOGE(TAG, "Failed to create ring buffers");
        return ESP_ERR_NO_MEM;
    }

    ESP_LOGI(TAG, "Audio pipeline initialized");
    return ESP_OK;
}

esp_err_t audio_pipeline_start(void) {
    ESP_LOGI(TAG, "Starting audio pipeline");

    if (rx_handle) {
        ESP_ERROR_CHECK(i2s_channel_enable(rx_handle));
    }
    if (tx_handle) {
        ESP_ERROR_CHECK(i2s_channel_enable(tx_handle));
    }

    return ESP_OK;
}

esp_err_t audio_pipeline_stop(void) {
    ESP_LOGI(TAG, "Stopping audio pipeline");

    if (rx_handle) {
        i2s_channel_disable(rx_handle);
    }
    if (tx_handle) {
        i2s_channel_disable(tx_handle);
    }

    return ESP_OK;
}

void audio_record_task(void *arg) {
    ESP_LOGI(AUDIO_TAG, "Audio record task started");

    size_t bytes_read = 0;
    int16_t *buffer = heap_caps_malloc(AUDIO_BUFFER_SIZE * sizeof(int16_t), MALLOC_CAP_SPIRAM);
    if (!buffer) {
        ESP_LOGE(AUDIO_TAG, "Failed to allocate record buffer");
        vTaskDelete(NULL);
        return;
    }

    while (1) {
        if (!recording) {
            vTaskDelay(pdMS_TO_TICKS(100));
            continue;
        }

        size_t bytes_read = 0;
        esp_err_t ret = i2s_channel_read(rx_handle, buffer, AUDIO_BUFFER_SIZE * sizeof(int16_t), &bytes_read, portMAX_DELAY);
        
        if (ret == ESP_OK && bytes_read > 0) {
            size_t samples = bytes_read / sizeof(int16_t);
            
            // Apply basic noise gate
            for (size_t i = 0; i < samples; i++) {
                if (abs(buffer[i]) < 100) {
                    buffer[i] = 0;
                }
            }

            // Send to WebSocket queue (raw PCM)
            if (xQueueSend(g_audio_record_queue, &buffer, pdMS_TO_TICKS(100)) != pdTRUE) {
                ESP_LOGW(AUDIO_TAG, "Record queue full, dropping frame");
            } else {
                // Allocate new buffer for next frame
                int16_t *new_buffer = heap_caps_malloc(AUDIO_BUFFER_SIZE * sizeof(int16_t), MALLOC_CAP_SPIRAM);
                if (new_buffer) {
                    buffer = new_buffer;
                }
            }
        } else if (ret != ESP_OK) {
            ESP_LOGE(AUDIO_TAG, "I2S read error: %s", esp_err_to_name(ret));
            vTaskDelay(pdMS_TO_TICKS(100));
        }
    }

    free(buffer);
    vTaskDelete(NULL);
}

void audio_playback_task(void *arg) {
    ESP_LOGI(AUDIO_TAG, "Audio playback task started");

    int16_t *buffer = heap_caps_malloc(AUDIO_BUFFER_SIZE * sizeof(int16_t), MALLOC_CAP_SPIRAM);
    if (!buffer) {
        ESP_LOGE(AUDIO_TAG, "Failed to allocate playback buffer");
        vTaskDelete(NULL);
        return;
    }

    while (1) {
        if (!playing) {
            vTaskDelay(pdMS_TO_TICKS(100));
            continue;
        }

        int16_t *data = NULL;
        size_t size = 0;
        
        if (xQueueReceive(g_audio_playback_queue, &data, pdMS_TO_TICKS(100)) == pdTRUE) {
            // Play audio data
            size_t bytes_written = 0;
            esp_err_t ret = i2s_channel_write(tx_handle, data, AUDIO_BUFFER_SIZE * sizeof(int16_t), &bytes_written, portMAX_DELAY);
            
            if (ret != ESP_OK) {
                ESP_LOGE(AUDIO_TAG, "I2S write error: %s", esp_err_to_name(ret));
            }
            
            // Free the buffer after playback
            free(data);
        } else {
            // Play silence when no data
            memset(buffer, 0, AUDIO_BUFFER_SIZE * sizeof(int16_t));
            size_t bytes_written = 0;
            i2s_channel_write(tx_handle, buffer, AUDIO_BUFFER_SIZE * sizeof(int16_t), &bytes_written, portMAX_DELAY);
        }
    }

    free(buffer);
    vTaskDelete(NULL);
}

esp_err_t audio_write_playback(int16_t *data, size_t samples) {
    int16_t *buf = malloc(samples * sizeof(int16_t));
    if (!buf) return ESP_ERR_NO_MEM;
    
    memcpy(buf, data, samples * sizeof(int16_t));
    
    if (xQueueSend(g_audio_playback_queue, &buf, pdMS_TO_TICKS(100)) != pdTRUE) {
        free(buf);
        return ESP_ERR_TIMEOUT;
    }
    return ESP_OK;
}

void recording_start(void) {
    if (!recording) {
        recording = true;
        ESP_LOGI(AUDIO_TAG, "Recording started");
    }
}

void recording_stop(void) {
    if (recording) {
        recording = false;
        ESP_LOGI(AUDIO_TAG, "Recording stopped");
    }
}

void playback_start(void) {
    if (!playing) {
        playing = true;
        ESP_LOGI(AUDIO_TAG, "Playback started");
    }
}

void playback_stop(void) {
    if (playing) {
        playing = false;
        ESP_LOGI(AUDIO_TAG, "Playback stopped");
    }
}

bool is_recording(void) {
    return recording;
}

bool is_playing(void) {
    return playing;
}

esp_err_t audio_pipeline_deinit(void) {
    recording = false;
    playing = false;
    
    if (rx_handle) {
        i2s_channel_disable(rx_handle);
        i2s_del_channel(rx_handle);
        rx_handle = NULL;
    }
    if (tx_handle) {
        i2s_channel_disable(tx_handle);
        i2s_del_channel(tx_handle);
        tx_handle = NULL;
    }
    
    if (rb_rx) {
        vRingbufferDelete(rb_rx);
        rb_rx = NULL;
    }
    if (rb_tx) {
        vRingbufferDelete(rb_tx);
        rb_tx = NULL;
    }
    
    return ESP_OK;
}