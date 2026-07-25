idf_component_register(SRCS "main.c"
                       "audio_pipeline.c"
                       "sangam_client.c"
                       "sarvam_client.c"
                       "compliance_actions.c"
                       "wifi_provisioning.c"
                       "sd_logger.c"
                       "ui_indicators.c"
                    INCLUDE_DIRS "."
                    REQUIRES esp_wifi esp_netif esp_http_client esp_https_ota
                             mqtt esp_https_ota mbedtls json cjson
                             driver esp_timer esp_event esp_wifi esp_netif
                             nvs_flash esp_http_client esp_https_ota
                             mqtt protocomm protocomm_console protocomm_httpd
                             mdns esp_local_ctrl esp_local_ctrl_internal
                             esp_serial_slave_link esp_serial_flash
                             fatfs sdmmc sdspi_host sdmmc_host
                             i2s esp_adc_cal esp_adc_cal_interface
                             esp_timer esp_event esp_wifi esp_netif
                             nvs_flash esp_http_client esp_https_ota
                             mqtt protocomm protocomm_console protocomm_httpd
                             mdns esp_local_ctrl esp_local_ctrl_internal
                             esp_serial_slave_link esp_serial_flash
                             fatfs sdmmc sdspi_host sdmmc_host
                             i2s esp_adc_cal esp_adc_cal_interface)