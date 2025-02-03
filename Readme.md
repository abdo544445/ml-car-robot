
# ESP32-CAM ML Robot , Object detection and hand following logic

## Team member 
abd alatrash


## 1. Project Overview
A WiFi-controlled robot using ESP32-CAM that provides:
- Live video streaming
- Motor control
- Flash LED control
- Object detection capabilities
- Hand logic following 
- Web interface and Python GUI control options

## 2. Hardware Components
- **Main Controller**: ESP32-CAM module
- **Motors**: 2 DC motors (1 per side)
- **Steering wheel** 
- **LED**: Built-in flash LED (GPIO 4)
- **Motor Control Pins**:
  - Left Forward: GPIO 12
  - Left Backward: GPIO 13
  - Right Forward: GPIO 14
  - Right Backward: GPIO 15
## 3. Software Architecture

### 3.1 ESP32-CAM Firmware
- **Main Components**:
  - `espCam32-Rover.ino`: Main program
  - `app_httpd.cpp`: Web server and stream handling
  - `globals.h`: Shared variables
  - `commands.h`: Command handling declarations

#### Key Features:
- WiFi Access Point mode (SSID: "atrash", Passowrd:"12345678")
- Dual server setup:
  the main internet protocol link is 192.168.4.1{port for streaming or control }
  - Port 80: Web interface and control commands
  - Port 81: Video streaming
- PWM motor control
- LED brightness control
- Camera configuration optimization

### 3.2 Python Applications
- **Flask Server** (`flask_server.py`):
  - Video stream relay
  - Command forwarding
  - Status monitoring

- **App GUI** (`app.py`):
  - Object detection using YOLO
  - hand following logic using pipline
  - Manual control interface
  - Camera settings adjustment
  - Stream visualization

## 4. Control Systems

### 4.1 Movement Control
```
Commands:
"1": Forward
"2": Left
"3": Stop
"4": Right
"5": Backward
```

### 4.2 Camera Settings
- Resolution options from QCIF to UXGA
- Quality adjustment (10-63)
- Brightness control (-2 to 2)
- Contrast control (-2 to 2)
- Flash LED intensity (0-255)

## 5. Network Architecture
```
WiFi AP Mode:
SSID: "atrash"
Password: "12345678"
IP: 192.168.4.1
```

### Endpoints:
- `/stream`: Video stream (Port 81)
- `/control`: Command interface (Port 80)
- `/capture`: Photo capture
- `/`: Web interface

## 6. Performance Optimizations
- Camera frame size: VGA (640x480)
- JPEG quality: 12 (balanced quality/speed)
- Stream buffer size: 2 frames
- PWM frequency: 5KHz for motors
- Optimized memory management
- Brownout detection disabled

## 7. User Interfaces

### 7.1 Web Interface
- Live video feed
- Direction controls
- Speed slider
- Camera settings
- Flash control
- Keyboard controls

### 7.2 Python GUI
- Object detection display
- Manual controls
- Stream source selection
- Performance monitoring
- Status indicators

## 8. Safety Features
- Motor stop on connection loss
- Command validation
- Error handling
- Status monitoring
- Automatic reconnection

## 9. Future Improvements
1. Battery monitoring
2. Multiple camera support
3. Enhanced autonomous features
4. Improved error recovery
5. Speed optimization
6. Better stream quality

## 10. Known Limitations
1. WiFi range dependent
2. Processing delay in video stream
3. Battery life constraints
4. Memory limitations
5. Processing power constraints

## 11. Usage Instructions
1. Power up ESP32-CAM
2. Connect to "atrash" WiFi network
3. Access web interface or run Python GUI
4. Control via buttons or keyboard
5. Monitor status and performance


## 12. Advanced Control Features

### 12.1 Hand Following Mode
- MediaPipe hand detection
- Real-time hand tracking
- Gesture-based control zones
- Visual feedback with landmarks
- Automatic robot response to hand position

### 12.2 Multi-Source Camera Support
- Local Webcam (default)
- ESP32-CAM Stream
- Custom Stream URLs
- Dynamic source switching

### 12.3 Object Detection System
- YOLO v3 implementation
- Multiple object class detection
- Confidence thresholds
- Non-maximum suppression
- Target object tracking
- Performance optimizations:
  - Frame skip (process every N frames)
  - Reduced detection size (320x320)
  - Configurable confidence threshold

## 13. GUI Enhancements

### 13.1 Advanced Interface Layout
- Split-panel design
- Scrollable control panel
- Video canvas (800x600)
- Status indicators
- Real-time FPS counter

### 13.2 Control Panels
- Manual Control
- Auto Follow
- Hand Following
- Camera Settings
- Motor Speed
- Flash Control
- Stream Selection

### 13.3 Visual Feedback
- Bounding box visualization
- Confidence scores
- Object labels
- Hand landmarks
- Control zone indicators
- Status messages

## 14. Autonomous Modes

### 14.1 Object Following
- Target object selection
- Position-based control
- Automatic speed adjustment
- Center frame tracking
- Configurable margins

### 14.2 Hand Following Logic
- Vertical threshold for forward/backward
- Horizontal margins for left/right
- Center zone for forward movement
- Visual zone indicators
- Automatic speed control

## 15. Error Handling and Recovery

### 15.1 Connection Management
- Automatic reconnection
- Source switching
- Connection status monitoring
- Error reporting
- Graceful fallback

### 15.2 Command Safety
- Command validation
- Timeout handling
- Error logging
- Status feedback
- Automatic stop on errors

## 16. Performance Optimizations

### 16.1 Video Processing
- Frame skipping
- Reduced detection size
- Efficient memory usage
- Separate processing threads
- Dynamic quality adjustment

### 16.2 Interface Responsiveness
- Asynchronous command handling
- Buffered video display
- Efficient GUI updates
- Resource cleanup
- Memory management

## 17. User Experience Features

### 17.1 Control Options
- GUI buttons
- Keyboard shortcuts
- Hand gestures
- Autonomous tracking
- Custom stream input

### 17.2 Configuration Options
- Camera resolution
- Stream quality
- Motor speed
- Flash intensity
- Detection confidence
- Processing frequency



## 18. Application Layout Description

### 18.1 Left Panel: Video Display
The primary display area occupies approximately 70% of the application window and consists of:
- A large video feed window with fixed dimensions (800x600 pixels)
- Black background for optimal visibility
- Real-time overlay information including:
  * FPS counter
  * Detection status
  * Visual indicators (hand tracking landmarks, object detection boxes)
- Centered video feed with maintained aspect ratio

### 18.2 Right Panel: Control Interface
The control panel occupies the remaining 30% of the window width and contains multiple functional sections arranged vertically:

#### 18.2.1 Manual Control
- Directional control pad with five buttons arranged in a cross pattern:
  * Forward (↑)
  * Left (←)
  * Stop (•)
  * Right (→)
  * Backward (↓)
- Speed adjustment slider
- Flash control slider with "Toggle Flash" button

#### 18.2.2 Camera Controls
- Resolution selector dropdown menu (default: VGA 640x480)
- Quality adjustment slider (range: 10-63)
- Secondary flash control with:
  * Intensity slider
  * Toggle button

#### 18.2.3 Motor Speed
- Dedicated horizontal slider for fine-tuning motor speed

#### 18.2.4 Auto Follow
- Single toggle button for enabling/disabling autonomous following mode

#### 18.2.5 Camera Source Selection
- Two input options via radio buttons:
  * Webcam (default)
  * Custom Stream
- Stream URL input field
- "Connect to Stream" action button
- "Reconnect Camera" failsafe button

#### 18.2.6 Hand Following
- Toggle button for hand tracking mode
- Status indicator for current tracking state

#### 18.2.7 Application Control
- "Close Application" button for proper program termination

### 18.3 Interface Design Principles
The interface implements several key design principles:
- Logical grouping of related controls
- Clear visual hierarchy through labeled frames
- Consistent spacing and alignment
- Persistent control visibility
- Real-time feedback for user actions
- Fail-safe controls for critical functions

This layout ensures efficient access to all robot control functions while maintaining clear visibility of the video feed, making it suitable for both manual control and autonomous operation modes.
Here's a comprehensive breakdown of the Python libraries and data used in the application:

## 19. Application Dependencies and Data

### 19.1 Core Python Libraries
1. **OpenCV (cv2)**
   - Purpose: Computer vision and image processing
   - Key functionalities:
     * Video capture and streaming
     * Image manipulation and processing
     * YOLO model integration
     * Drawing shapes and text overlays

2. **Tkinter (tk)**
   - Purpose: GUI framework
   - Components used:
     * ttk: Themed widgets
     * Canvas: Video display
     * Buttons, sliders, and frames
     * Event handling

3. **NumPy (np)**
   - Purpose: Numerical computations
   - Usage:
     * Array operations
     * Image data manipulation
     * Mathematical calculations

4. **PIL (Python Imaging Library)**
   - Purpose: Image processing
   - Modules used:
     * Image: Image object handling
     * ImageTk: Tkinter-compatible image objects

5. **Mediapipe (mp)**
   - Purpose: Hand tracking and gesture recognition
   - Features used:
     * Hand landmark detection
     * Real-time tracking
     * Drawing utilities

6. **Requests**
   - Purpose: HTTP communications
   - Usage:
     * ESP32 camera stream connection
     * Control commands transmission
     * Camera settings adjustment

### 19.2 Data Files and Models
1. **YOLO Model Files**
   ```
   - yolov3.weights: Pre-trained model weights
   - yolov3.cfg: Model configuration file
   - coco.names: Object class labels
   ```

2. **Configuration Data**
   ```python
   CAMERA_SOURCES = {
       "Webcam": {
           "source": 0,
           "type": "webcam",
           "enabled": True
       },
       "Custom Stream": {
           "source": "",
           "type": "stream",
           "enabled": True
       }
   }
   ```

### 19.3 Network Configuration
```python
ESP32_IP = "192.168.4.1"
ESP32_STREAM_PORT = "81"
ESP32_CONTROL_PORT = "80"
STREAM_URL = f"http://{ESP32_IP}:{ESP32_STREAM_PORT}/stream"
CONTROL_URL = f"http://{ESP32_IP}:{ESP32_CONTROL_PORT}/control"
```

### 19.4 Performance Settings
```python
# Detection Parameters
CONFIDENCE_THRESHOLD = 0.5
DETECTION_SIZE = (320, 320)
DISPLAY_SIZE = (640, 480)

# Processing Optimization
PROCESS_EVERY_N_FRAMES = 2
FRAME_COUNT = 0

# MediaPipe Configuration
HAND_DETECTION_CONFIDENCE = 0.5
HAND_TRACKING_CONFIDENCE = 0.3
MODEL_COMPLEXITY = 0
```

### 19.5 Camera Settings
1. **Resolution Options**
   ```
   - UXGA (1600x1200)
   - SXGA (1280x1024)
   - HD (1280x720)
   - XGA (1024x768)
   - SVGA (800x600)
   - VGA (640x480)
   - CIF (400x296)
   - QVGA (320x240)
   - QCIF (176x144)
   ```

2. **Quality Settings**
   - Range: 10-63
   - Default: 12

3. **Flash Control**
   - Range: 0-255
   - Default: 0

This comprehensive set of libraries and data configurations enables:
- Real-time video processing
- Object detection and tracking
- Hand gesture recognition
- Remote robot control
- User interface interaction
- Network communication
- Performance optimization

The application is designed to be modular, allowing for easy updates to configurations and addition of new features while maintaining stable performance.

# Appendix
![[Screenshot from 2024-12-12 07-34-45.png]]
![[Screenshot from 2024-12-12 07-37-54.png]]![[Screenshot from 2024-12-12 07-37-34.png]]![[Screenshot from 2024-12-12 07-38-48.png]]![[Screenshot from 2024-12-12 07-36-37.png]]
## The car 
![[Pasted image 20241212074647.png]]
![[Pasted image 20241212074719.png]]
## The circuit connection 
![[Diagrama conexion.png]]
## The link for the full project code 
