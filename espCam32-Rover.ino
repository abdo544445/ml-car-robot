#include "esp32-hal.h"
#include "esp32-hal-ledc.h"
#include <Arduino.h>
#include <WiFi.h>
#include "esp_camera.h"
#include "esp_wifi.h"
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"
#include "driver/ledc.h"
#include "globals.h"

const char* ssid = "atrash";
const char* password = "12345678";

#define CAMERA_MODEL_AI_THINKER

#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

void startCameraServer();

// Motor control pins
const int MotPin0 = 12;  // Left motor forward
const int MotPin1 = 13;  // Left motor backward
const int MotPin2 = 14;  // Right motor forward
const int MotPin3 = 15;  // Right motor backward

// LED control pin
const int LED_PIN = 4;  // Flash LED pin

void initMotors() {
    // Configure timer for motor control
    ledc_timer_config_t motor_timer = {
        .speed_mode = LEDC_HIGH_SPEED_MODE,
        .duty_resolution = LEDC_TIMER_8_BIT,
        .timer_num = LEDC_TIMER_0,
        .freq_hz = 5000,  // 5KHz frequency
        .clk_cfg = LEDC_AUTO_CLK
    };
    ledc_timer_config(&motor_timer);

    // Configure channels for each motor pin
    ledc_channel_config_t motor_channels[4] = {
        {   // Channel 0 - Left motor backward
            .gpio_num = MotPin0,
            .speed_mode = LEDC_HIGH_SPEED_MODE,
            .channel = LEDC_CHANNEL_0,
            .timer_sel = LEDC_TIMER_0,
            .duty = 0,
            .hpoint = 0
        },
        {   // Channel 1 - Left motor forward
            .gpio_num = MotPin1,
            .speed_mode = LEDC_HIGH_SPEED_MODE,
            .channel = LEDC_CHANNEL_1,
            .timer_sel = LEDC_TIMER_0,
            .duty = 0,
            .hpoint = 0
        },
        {   // Channel 2 - Right motor forward
            .gpio_num = MotPin2,
            .speed_mode = LEDC_HIGH_SPEED_MODE,
            .channel = LEDC_CHANNEL_2,
            .timer_sel = LEDC_TIMER_0,
            .duty = 0,
            .hpoint = 0
        },
        {   // Channel 3 - Right motor backward
            .gpio_num = MotPin3,
            .speed_mode = LEDC_HIGH_SPEED_MODE,
            .channel = LEDC_CHANNEL_3,
            .timer_sel = LEDC_TIMER_0,
            .duty = 0,
            .hpoint = 0
        }
    };

    // Initialize all motor channels
    for (int i = 0; i < 4; i++) {
        ledc_channel_config(&motor_channels[i]);
    }

    // Configure LED control
    ledc_timer_config_t led_timer = {
        .speed_mode = LEDC_HIGH_SPEED_MODE,
        .duty_resolution = LEDC_TIMER_8_BIT,
        .timer_num = LEDC_TIMER_2,
        .freq_hz = 5000,
        .clk_cfg = LEDC_AUTO_CLK
    };
    ledc_timer_config(&led_timer);

    ledc_channel_config_t led_channel = {
        .gpio_num = LED_PIN,
        .speed_mode = LEDC_HIGH_SPEED_MODE,
        .channel = LEDC_CHANNEL_7,
        .timer_sel = LEDC_TIMER_2,
        .duty = 0,
        .hpoint = 0
    };
    ledc_channel_config(&led_channel);
}

void stopMotors() {
    // Stop all motors
    for(int channel = 0; channel < 4; channel++) {
        ledc_set_duty(LEDC_HIGH_SPEED_MODE, (ledc_channel_t)channel, 0);
        ledc_update_duty(LEDC_HIGH_SPEED_MODE, (ledc_channel_t)channel);
    }
}

void setup(){
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0); // prevent brownouts by silencing them

  Serial.begin(115200);
  Serial.setDebugOutput(true);
  Serial.println();

  // Camera configuration
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  
  // Lower resolution for better streaming
  config.frame_size = FRAMESIZE_VGA;
  config.jpeg_quality = 12;
  config.fb_count = 2;
  
  // Initialize camera
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x", err);
    delay(1000);
    ESP.restart();
  }
  
  // Optimize camera settings for lower power
  sensor_t * s = esp_camera_sensor_get();
  s->set_framesize(s, FRAMESIZE_VGA);
  s->set_quality(s, 12);
  s->set_brightness(s, 0);
  s->set_contrast(s, 1);
  s->set_saturation(s, 0);
  s->set_special_effect(s, 0);
  s->set_whitebal(s, 1);
  s->set_awb_gain(s, 1);
  s->set_wb_mode(s, 0);
  s->set_exposure_ctrl(s, 1);
  s->set_aec2(s, 0);
  s->set_gain_ctrl(s, 1);
  s->set_agc_gain(s, 0);
  
  // Initialize motors
  initMotors();
  stopMotors();

  // Start WiFi
  WiFi.softAP(ssid, password);
  Serial.printf("Ready! Stream: http://%s:81/stream\n", WiFi.softAPIP().toString().c_str());
  
  startCameraServer();
}

void loop() {
  // Handle serial commands (for debugging)
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    handleCommand(command);
  }

  // Print WiFi status every second
  static unsigned long lastStatus = 0;
  if (millis() - lastStatus > 1000) {
    Serial.printf("WiFi Status - RSSI: %ld dBm\n", WiFi.RSSI());
    lastStatus = millis();
  }
}

void handleCommand(String command) {
    Serial.print("Received command: ");
    Serial.println(command);

    // Stop all motors first
    stopMotors();

    if (command == "1") {  // Forward
        Serial.println("Moving Forward");
        ledc_set_duty(LEDC_HIGH_SPEED_MODE, LEDC_CHANNEL_1, speed);
        ledc_update_duty(LEDC_HIGH_SPEED_MODE, LEDC_CHANNEL_1);
        ledc_set_duty(LEDC_HIGH_SPEED_MODE, LEDC_CHANNEL_2, speed);
        ledc_update_duty(LEDC_HIGH_SPEED_MODE, LEDC_CHANNEL_2);
    } 
    else if (command == "2") {  // Left
        Serial.println("Turning Left");
        ledc_set_duty(LEDC_HIGH_SPEED_MODE, LEDC_CHANNEL_0, speed);
        ledc_update_duty(LEDC_HIGH_SPEED_MODE, LEDC_CHANNEL_0);
        ledc_set_duty(LEDC_HIGH_SPEED_MODE, LEDC_CHANNEL_2, speed);
        ledc_update_duty(LEDC_HIGH_SPEED_MODE, LEDC_CHANNEL_2);
    } 
    else if (command == "3") {  // Stop
        Serial.println("Stopping");
        stopMotors();
    } 
    else if (command == "4") {  // Right
        Serial.println("Turning Right");
        ledc_set_duty(LEDC_HIGH_SPEED_MODE, LEDC_CHANNEL_1, speed);
        ledc_update_duty(LEDC_HIGH_SPEED_MODE, LEDC_CHANNEL_1);
        ledc_set_duty(LEDC_HIGH_SPEED_MODE, LEDC_CHANNEL_3, speed);
        ledc_update_duty(LEDC_HIGH_SPEED_MODE, LEDC_CHANNEL_3);
    } 
    else if (command == "5") {  // Backward
        Serial.println("Moving Backward");
        ledc_set_duty(LEDC_HIGH_SPEED_MODE, LEDC_CHANNEL_0, speed);
        ledc_update_duty(LEDC_HIGH_SPEED_MODE, LEDC_CHANNEL_0);
        ledc_set_duty(LEDC_HIGH_SPEED_MODE, LEDC_CHANNEL_3, speed);
        ledc_update_duty(LEDC_HIGH_SPEED_MODE, LEDC_CHANNEL_3);
    }
}
