#include "globals.h"
#include "commands.h"
#include <esp32-hal-ledc.h>
#include "esp_http_server.h"
#include "esp_timer.h"
#include "esp_camera.h"
#include "img_converters.h"
#include "Arduino.h"

// Define the variables
int speed = 255;  
int noStop = 0;

typedef struct {
        httpd_req_t *req;
        size_t len;
} jpg_chunking_t;

#define PART_BOUNDARY "123456789000000000000987654321"
static const char* _STREAM_CONTENT_TYPE = "multipart/x-mixed-replace;boundary=" PART_BOUNDARY;
static const char* _STREAM_BOUNDARY = "\r\n--" PART_BOUNDARY "\r\n";
static const char* _STREAM_PART = "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n";

httpd_handle_t stream_httpd = NULL;
httpd_handle_t camera_httpd = NULL;

// Forward declarations of handler functions
static esp_err_t index_handler(httpd_req_t *req);
static esp_err_t stream_handler(httpd_req_t *req);
static esp_err_t cmd_handler(httpd_req_t *req);
static esp_err_t capture_handler(httpd_req_t *req);

// Define URI handlers after forward declarations
httpd_uri_t index_uri = {
    .uri       = "/",
    .method    = HTTP_GET,
    .handler   = index_handler,
    .user_ctx  = NULL
};

httpd_uri_t stream_uri = {
    .uri       = "/stream",
    .method    = HTTP_GET,
    .handler   = stream_handler,
    .user_ctx  = NULL
};

httpd_uri_t cmd_uri = {
    .uri       = "/control",
    .method    = HTTP_GET,
    .handler   = cmd_handler,
    .user_ctx  = NULL
};

httpd_uri_t capture_uri = {
    .uri       = "/capture",
    .method    = HTTP_GET,
    .handler   = capture_handler,
    .user_ctx  = NULL
};

static size_t jpg_encode_stream(void * arg, size_t index, const void* data, size_t len){
    jpg_chunking_t *j = (jpg_chunking_t *)arg;
    if(!index){
        j->len = 0;
    }
    if(httpd_resp_send_chunk(j->req, (const char *)data, len) != ESP_OK){
        return 0;
    }
    j->len += len;
    return len;
}

static esp_err_t capture_handler(httpd_req_t *req){
    camera_fb_t * fb = NULL;
    esp_err_t res = ESP_OK;
    int64_t fr_start = esp_timer_get_time();

    fb = esp_camera_fb_get();
    if (!fb) {
        Serial.println("Camera capture failed");
        httpd_resp_send_500(req);
        return ESP_FAIL;
    }

    httpd_resp_set_type(req, "image/jpeg");
    httpd_resp_set_hdr(req, "Content-Disposition", "inline; filename=capture.jpg");

    size_t out_len, out_width, out_height;
    uint8_t * out_buf;
    bool s;
    {
        size_t fb_len = 0;
        if(fb->format == PIXFORMAT_JPEG){
            fb_len = fb->len;
            res = httpd_resp_send(req, (const char *)fb->buf, fb->len);
        } else {
            jpg_chunking_t jchunk = {req, 0};
            res = frame2jpg_cb(fb, 80, jpg_encode_stream, &jchunk)?ESP_OK:ESP_FAIL;
            httpd_resp_send_chunk(req, NULL, 0);
            fb_len = jchunk.len;
        }
        esp_camera_fb_return(fb);
        int64_t fr_end = esp_timer_get_time();
        Serial.printf("JPG: %uB %ums\n", (uint32_t)(fb_len), (uint32_t)((fr_end - fr_start)/1000));
        return res;
    }

    out_buf = fb->buf;
    out_len = fb->width * fb->height * 3;
    out_width = fb->width;
    out_height = fb->height;

    s = fmt2rgb888(fb->buf, fb->len, fb->format, out_buf);
    esp_camera_fb_return(fb);
    if(!s){
        Serial.println("to rgb888 failed");
        httpd_resp_send_500(req);
        return ESP_FAIL;
    }

    jpg_chunking_t jchunk = {req, 0};
    s = fmt2jpg_cb(out_buf, out_len, out_width, out_height, PIXFORMAT_RGB888, 90, jpg_encode_stream, &jchunk);
    if(!s){
        Serial.println("JPEG compression failed");
        return ESP_FAIL;
    }

    int64_t fr_end = esp_timer_get_time();
    return res;
}

static esp_err_t stream_handler(httpd_req_t *req) {
    camera_fb_t *fb = NULL;
    esp_err_t res = ESP_OK;
    size_t _jpg_buf_len = 0;
    uint8_t *_jpg_buf = NULL;
    char *part_buf[64];
    static int64_t last_frame = 0;
    
    // Debug output
    Serial.println("Stream handler started");

    // Set CORS headers
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
    httpd_resp_set_type(req, _STREAM_CONTENT_TYPE);

    // Main streaming loop
    while (true) {
        fb = esp_camera_fb_get();
        if (!fb) {
            Serial.println("Camera capture failed");
            res = ESP_FAIL;
        } else {
            // Debug frame info
            int64_t now = esp_timer_get_time();
            Serial.printf("Frame %uB %ums\n", (uint32_t)(fb->len), (uint32_t)((now - last_frame)/1000));
            last_frame = now;

            if (fb->format != PIXFORMAT_JPEG) {
                bool jpeg_converted = frame2jpg(fb, 80, &_jpg_buf, &_jpg_buf_len);
                esp_camera_fb_return(fb);
                fb = NULL;
                if (!jpeg_converted) {
                    Serial.println("JPEG compression failed");
                    res = ESP_FAIL;
                }
            } else {
                _jpg_buf_len = fb->len;
                _jpg_buf = fb->buf;
            }
        }

        if (res == ESP_OK) {
            size_t hlen = snprintf((char *)part_buf, 64, _STREAM_PART, _jpg_buf_len);
            res = httpd_resp_send_chunk(req, _STREAM_BOUNDARY, strlen(_STREAM_BOUNDARY));
            if (res == ESP_OK) {
                res = httpd_resp_send_chunk(req, (const char *)part_buf, hlen);
            }
            if (res == ESP_OK) {
                res = httpd_resp_send_chunk(req, (const char *)_jpg_buf, _jpg_buf_len);
            }
        }

        if (fb) {
            esp_camera_fb_return(fb);
            fb = NULL;
            _jpg_buf = NULL;
        } else if (_jpg_buf) {
            free(_jpg_buf);
            _jpg_buf = NULL;
        }

        if (res != ESP_OK) {
            Serial.printf("Stream error: %d\n", res);
            break;
        }
    }
    return res;
}

enum state {fwd,rev,stp};
state actstate = stp;

static esp_err_t cmd_handler(httpd_req_t *req) {
    char*  buf;
    size_t buf_len;
    char variable[32] = {0,};
    char value[32] = {0,};
    char command[32] = {0,};

    buf_len = httpd_req_get_url_query_len(req) + 1;
    if (buf_len > 1) {
        buf = (char*)malloc(buf_len);
        if(!buf){
            httpd_resp_send_500(req);
            return ESP_FAIL;
        }
        if (httpd_req_get_url_query_str(req, buf, buf_len) == ESP_OK) {
            // Check for motor commands
            if (httpd_query_key_value(buf, "command", command, sizeof(command)) == ESP_OK) {
                handleCommand(command);
            }
            // Check for camera/flash settings
            else if (httpd_query_key_value(buf, "var", variable, sizeof(variable)) == ESP_OK &&
                     httpd_query_key_value(buf, "val", value, sizeof(value)) == ESP_OK) {
                
                int val = atoi(value);
                
                if(!strcmp(variable, "flash")) {
                    ledcWrite(7, val);  // LED control
                    Serial.printf("Flash set to %d\n", val);
                }
                else if(!strcmp(variable, "speed")) {
                    speed = val;
                }
            }
        }
        free(buf);
    }
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
    return httpd_resp_send(req, NULL, 0);
}

static esp_err_t status_handler(httpd_req_t *req) {
    static char json_response[1024];
    char * p = json_response;
    *p++ = '{';
    p += sprintf(p, "\"status\":%d,", 1);
    p += sprintf(p, "\"stream_active\":%d,", (stream_httpd != NULL));
    p += sprintf(p, "\"web_active\":%d", (camera_httpd != NULL));
    *p++ = '}';
    *p++ = 0;
    httpd_resp_set_type(req, "application/json");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
    return httpd_resp_send(req, json_response, strlen(json_response));
}

static const char PROGMEM INDEX_HTML[] = R"rawliteral(
<!doctype html>
<html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width,initial-scale=1">
        <title>ESP32-CAM Rover Control</title>
        <style>
            body { 
                font-family: Arial; 
                text-align: center; 
                margin: 0px auto; 
                padding: 15px; 
                background-color: #f0f0f5;
            }
            .slider-container {
                width: 300px;
                margin: 10px auto;
                text-align: left;
            }
            .slider {
                width: 100%;
                height: 15px;
                border-radius: 5px;
                background: #d3d3d3;
                opacity: 0.7;
                transition: opacity .2s;
            }
            .slider:hover { opacity: 1; }
            .button {
                background-color: #4CAF50;
                border: none;
                color: white;
                padding: 15px 32px;
                text-align: center;
                display: inline-block;
                font-size: 16px;
                margin: 4px 2px;
                cursor: pointer;
                border-radius: 4px;
            }
            .control-panel {
                background-color: white;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 4px 8px rgba(0,0,0,0.1);
                margin: 20px auto;
                max-width: 800px;
            }
            
            /* Add styles for motor controls */
            .motor-controls {
                margin: 20px auto;
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 10px;
                max-width: 300px;
            }
            
            .control-button {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 15px;
                font-size: 20px;
                cursor: pointer;
                border-radius: 5px;
                transition: background-color 0.3s;
            }
            
            .control-button:hover {
                background-color: #1976D2;
            }
            
            .control-button:active {
                background-color: #0D47A1;
            }
            
            .speed-control {
                margin: 20px auto;
                width: 300px;
            }
            
            #speedValue {
                font-size: 18px;
                font-weight: bold;
            }
        </style>
    </head>
    <body>
        <div class="control-panel">
            <h1>ESP32-CAM Rover Control</h1>
            <img src="" id="stream" width="640" height="480">
            
            <!-- Motor Controls -->
            <div class="motor-controls">
                <button class="control-button" onclick="sendCommand('2')">&larr;</button>
                <button class="control-button" onclick="sendCommand('1')">&uarr;</button>
                <button class="control-button" onclick="sendCommand('4')">&rarr;</button>
                <div></div>
                <button class="control-button" onclick="sendCommand('5')">&darr;</button>
                <div></div>
            </div>
            
            <!-- Speed Control -->
            <div class="speed-control">
                <label>Motor Speed (0-255):</label>
                <input type="range" id="speed" class="slider" min="0" max="255" value="255">
                <span id="speedValue">255</span>
            </div>
            
            <!-- Camera Settings -->
            <div class="slider-container">
                <h3>Camera Settings</h3>
                <label>Quality (10-63):</label>
                <input type="range" id="quality" class="slider" min="10" max="63" value="12">
                <span id="qualityValue">12</span>
                
                <label>Frame Size:</label>
                <select id="framesize">
                    <option value="13">UXGA(1600x1200)</option>
                    <option value="12">SXGA(1280x1024)</option>
                    <option value="11">HD(1280x720)</option>
                    <option value="10">XGA(1024x768)</option>
                    <option value="9">SVGA(800x600)</option>
                    <option value="8" selected>VGA(640x480)</option>
                    <option value="7">CIF(400x296)</option>
                    <option value="6">QVGA(320x240)</option>
                    <option value="5">QCIF(176x144)</option>
                </select>
                
                <label>Brightness (-2,2):</label>
                <input type="range" id="brightness" class="slider" min="-2" max="2" value="0">
                <span id="brightnessValue">0</span>
                
                <label>Contrast (-2,2):</label>
                <input type="range" id="contrast" class="slider" min="-2" max="2" value="0">
                <span id="contrastValue">0</span>
                
                <!-- Add Flash Control -->
                <label>Flash LED:</label>
                <input type="range" id="flash" class="slider" min="0" max="255" value="0">
                <span id="flashValue">0</span>
                <button class="button" onclick="toggleFlash()">Toggle Flash</button>
            </div>
            
            <div class="button-container">
                <button class="button" onclick="toggleStream()">Start/Stop Stream</button>
                <button class="button" onclick="capturePhoto()">Capture Photo</button>
                <button class="button" onclick="restartCamera()">Restart Camera</button>
            </div>
        </div>
        
        <script>
            // Initialize stream
            document.getElementById('stream').src = `http://${window.location.hostname}:81/stream`;
            
            // Motor control functions
            function sendCommand(command) {
                fetch(`${window.location.href}control?command=${command}`)
                    .then(response => console.log('Command sent:', command))
                    .catch(error => console.error('Error:', error));
            }
            
            // Speed control
            document.getElementById('speed').oninput = function() {
                document.getElementById('speedValue').textContent = this.value;
                fetch(`${window.location.href}control?var=speed&val=${this.value}`)
                    .then(response => console.log('Speed updated:', this.value))
                    .catch(error => console.error('Error:', error));
            };
            
            // Keyboard controls
            document.addEventListener('keydown', function(event) {
                switch(event.key) {
                    case 'ArrowUp':
                        sendCommand('1');
                        event.preventDefault();
                        break;
                    case 'ArrowDown':
                        sendCommand('5');
                        event.preventDefault();
                        break;
                    case 'ArrowLeft':
                        sendCommand('2');
                        event.preventDefault();
                        break;
                    case 'ArrowRight':
                        sendCommand('4');
                        event.preventDefault();
                        break;
                    case ' ':  // Spacebar
                        sendCommand('3');
                        event.preventDefault();
                        break;
                }
            });
            
            // Update camera settings
            document.querySelectorAll('.slider').forEach(slider => {
                slider.oninput = function() {
                    document.getElementById(this.id + 'Value').textContent = this.value;
                    updateCamera(this.id, this.value);
                }
            });
            
            document.getElementById('framesize').onchange = function() {
                updateCamera('framesize', this.value);
            }
            
            function updateCamera(param, value) {
                fetch(`${window.location.href}control?var=${param}&val=${value}`)
                    .then(response => console.log(`${param} updated to ${value}`))
                    .catch(error => console.error('Error:', error));
            }
            
            // Flash control
            document.getElementById('flash').oninput = function() {
                document.getElementById('flashValue').textContent = this.value;
                updateCamera('flash', this.value);
            };
            
            function toggleFlash() {
                let flash = document.getElementById('flash');
                flash.value = flash.value > 0 ? 0 : 255;
                flash.dispatchEvent(new Event('input'));
            }
        </script>
    </body>
</html>
)rawliteral";

static esp_err_t index_handler(httpd_req_t *req){
    httpd_resp_set_type(req, "text/html");
    return httpd_resp_send(req, (const char *)INDEX_HTML, strlen(INDEX_HTML));
}

void startCameraServer() {
    httpd_config_t config = HTTPD_DEFAULT_CONFIG();
    
    // Increase buffer size and timeouts
    config.max_open_sockets = 4;
    config.core_id = 0;
    config.stack_size = 8192;
    config.task_priority = 5;
    config.recv_wait_timeout = 10;
    config.send_wait_timeout = 10;
    
    // Stream server on port 81
    config.server_port = 81;
    config.ctrl_port = 32123;
    
    Serial.printf("Starting stream server on port: '%d'\n", config.server_port);
    if (httpd_start(&stream_httpd, &config) == ESP_OK) {
        httpd_register_uri_handler(stream_httpd, &stream_uri);
    }

    // Web server on port 80
    config.server_port = 80;
    config.ctrl_port = 32124;
    
    Serial.printf("Starting web server on port: '%d'\n", config.server_port);
    if (httpd_start(&camera_httpd, &config) == ESP_OK) {
        httpd_register_uri_handler(camera_httpd, &index_uri);
        httpd_register_uri_handler(camera_httpd, &cmd_uri);
        httpd_register_uri_handler(camera_httpd, &capture_uri);
    }
}
