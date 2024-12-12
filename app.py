import cv2
import numpy as np
import requests
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import time
import mediapipe as mp

# ESP32-CAM configuration
ESP32_IP = "192.168.4.1"
ESP32_STREAM_PORT = "81"
ESP32_CONTROL_PORT = "80"
STREAM_URL = f"http://{ESP32_IP}:{ESP32_STREAM_PORT}/stream"
CONTROL_URL = f"http://{ESP32_IP}:{ESP32_CONTROL_PORT}/control"

# Add these configurations at the top
CAMERA_SOURCES = {
    "Webcam": {
        "source": 0,  # Default webcam
        "type": "webcam",
        "enabled": True
    },
    "Custom Stream": {
        "source": "",  # Will be filled by user input
        "type": "stream",
        "enabled": True
    }
}

class ObjectDetectionGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Object Detection")
        
        # Initialize camera source
        self.current_source = "Webcam"
        self.stream_url = ""  # For custom stream URL
        
        # Initialize video capture with error checking
        self.cap = None
        if not self.connect_to_camera():
            print("Failed to connect to camera on startup")
        
        # Initialize variables
        self.is_detecting = True
        self.show_boxes = True
        self.auto_control = False  # Flag for autonomous control
        self.fps = 0
        self.last_frame_time = time.time()
        self.detected_objects_count = {}
        self.target_object = "person"  # Object to track
        
        # Load YOLO
        try:
            self.net = cv2.dnn.readNet("yolov3.weights", "yolov3.cfg")
            with open("coco.names", "r") as f:
                self.classes = [line.strip() for line in f.readlines()]
            self.layer_names = self.net.getLayerNames()
            self.output_layers = [self.layer_names[i - 1] for i in self.net.getUnconnectedOutLayers()]
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load YOLO model: {str(e)}")
            self.root.quit()
            return
        
        # Optimize performance settings
        self.process_every_n_frames = 2  # Process every 2nd frame instead of 3
        self.frame_count = 0
        self.detection_size = (320, 320)  # Keep small detection size
        self.confidence_threshold = 0.5
        self.display_size = (640, 480)  # Smaller display size for better performance
        
        # Initialize MediaPipe Hands with optimized settings
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.3,  # Lower tracking confidence for better performance
            model_complexity=0  # Use simpler model (0, 1, or 2)
        )
        self.mp_draw = mp.solutions.drawing_utils
        
        # Add hand following mode
        self.hand_following = False
        
        # Add status buffer for stable display
        self.current_status = ""
        self.status_buffer = ""
        self.status_update_time = time.time()
        self.status_update_interval = 1.0  # Update status every 1 second
        
        # Add detection buffer
        self.detection_buffer = []
        self.detection_update_time = time.time()
        self.detection_update_interval = 2.0  # Update detections every 2 seconds
        
        # Add overlay settings
        self.overlay_alpha = 0.3
        self.overlay_color = (0, 0, 0)  # Black background for text
        
        # Create GUI elements
        self.create_gui()
        
        # Start video processing
        self.process_video()
        
        # Add keyboard bindings
        self.setup_keyboard_bindings()
    
    def create_gui(self):
        # Create style configuration at the beginning of create_gui
        style = ttk.Style()
        style.configure('TLabelframe', padding=5)
        style.configure('TButton', padding=5)
        style.configure('TLabel', padding=2)
        style.configure('Vertical.TScrollbar', arrowsize=13)
        
        # Create main container with controls
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Left panel for video
        left_panel = ttk.Frame(main_container)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Video frame with fixed size and better layout
        video_frame = ttk.LabelFrame(left_panel, text="Camera Feed")
        video_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create a fixed size canvas with black background
        self.video_canvas = tk.Canvas(
            video_frame, 
            width=800, 
            height=600, 
            bg='black',
            highlightthickness=0  # Remove border
        )
        self.video_canvas.pack(padx=5, pady=5)
        
        # Create persistent label containers on the canvas
        self.fps_label = self.video_canvas.create_text(
            10, 30,  # Position in top-left
            anchor='w',
            text="FPS: 0",
            fill='white',
            font=('Arial', 12)
        )

        self.detection_label = self.video_canvas.create_text(
            10, 60,  # Position below FPS
            anchor='w',
            text="",
            fill='white',
            font=('Arial', 12)
        )

        self.status_label = self.video_canvas.create_text(
            10, 90,  # Position below detection
            anchor='w',
            text="",
            fill='white',
            font=('Arial', 12)
        )
        
        # Right panel for controls with fixed width
        right_panel = ttk.Frame(main_container, width=300)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=5)
        right_panel.pack_propagate(False)  # Prevent the panel from shrinking
        
        # Create a canvas with scrollbar for controls
        control_canvas = tk.Canvas(right_panel)
        scrollbar = ttk.Scrollbar(right_panel, orient="vertical", command=control_canvas.yview)
        scrollable_frame = ttk.Frame(control_canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: control_canvas.configure(scrollregion=control_canvas.bbox("all"))
        )
        
        control_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        control_canvas.configure(yscrollcommand=scrollbar.set)
        
        # Pack the canvas and scrollbar
        scrollbar.pack(side="right", fill="y")
        control_canvas.pack(side="left", fill="both", expand=True)

        # Control buttons
        controls_frame = ttk.LabelFrame(scrollable_frame, text="Controls")
        controls_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.auto_button = ttk.Button(
            controls_frame,
            text="Start Auto Control",
            command=self.toggle_auto_control
        )
        self.auto_button.pack(fill=tk.X, padx=5, pady=5)
        
        # Object selection
        ttk.Label(controls_frame, text="Target Object:").pack(pady=5)
        self.target_var = tk.StringVar(value=self.target_object)
        self.target_combo = ttk.Combobox(
            controls_frame,
            textvariable=self.target_var,
            values=self.classes
        )
        self.target_combo.pack(fill=tk.X, padx=5, pady=5)
        
        # Status frame
        status_frame = ttk.LabelFrame(scrollable_frame, text="Status")
        status_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.status_var = tk.StringVar(value="Detection: Off")
        ttk.Label(status_frame, textvariable=self.status_var).pack(pady=5)
        
        self.fps_var = tk.StringVar(value="FPS: 0")
        ttk.Label(status_frame, textvariable=self.fps_var).pack(pady=5)
        
        # Manual Control Panel
        manual_frame = ttk.LabelFrame(scrollable_frame, text="Manual Control")
        manual_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Create control buttons grid
        control_grid = ttk.Frame(manual_frame)
        control_grid.pack(padx=5, pady=5)
        
        # Forward button
        self.btn_forward = ttk.Button(
            control_grid, 
            text="↑",
            command=lambda: self.send_command('1')
        )
        self.btn_forward.grid(row=0, column=1)
        
        # Left button
        self.btn_left = ttk.Button(
            control_grid,
            text="←",
            command=lambda: self.send_command('2')
        )
        self.btn_left.grid(row=1, column=0)
        
        # Stop button
        self.btn_stop = ttk.Button(
            control_grid,
            text="⬤",
            command=lambda: self.send_command('3')
        )
        self.btn_stop.grid(row=1, column=1)
        
        # Right button
        self.btn_right = ttk.Button(
            control_grid,
            text="→",
            command=lambda: self.send_command('4')
        )
        self.btn_right.grid(row=1, column=2)
        
        # Backward button
        self.btn_backward = ttk.Button(
            control_grid,
            text="↓",
            command=lambda: self.send_command('5')
        )
        self.btn_backward.grid(row=2, column=1)
        
        # Speed control
        speed_frame = ttk.Frame(manual_frame)
        speed_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(speed_frame, text="Speed:").pack(side=tk.LEFT)
        self.speed_var = tk.IntVar(value=255)
        speed_scale = ttk.Scale(
            speed_frame,
            from_=0,
            to=255,
            orient=tk.HORIZONTAL,
            variable=self.speed_var,
            command=self.update_speed
        )
        speed_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Flash control
        flash_frame = ttk.Frame(manual_frame)
        flash_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(flash_frame, text="Flash:").pack(side=tk.LEFT)
        self.flash_var = tk.IntVar(value=0)
        flash_scale = ttk.Scale(
            flash_frame,
            from_=0,
            to=255,
            orient=tk.HORIZONTAL,
            variable=self.flash_var,
            command=self.update_flash
        )
        flash_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        self.flash_btn = ttk.Button(
            flash_frame,
            text="Toggle Flash",
            command=self.toggle_flash
        )
        self.flash_btn.pack(side=tk.LEFT, padx=5)
        
        # Camera Controls Frame
        camera_frame = ttk.LabelFrame(scrollable_frame, text="Camera Controls")
        camera_frame.pack(fill=tk.X, padx=5, pady=5)

        # Resolution Dropdown
        ttk.Label(camera_frame, text="Resolution:").pack(pady=2)
        resolutions = [
            "UXGA(1600x1200)", "SXGA(1280x1024)", "HD(1280x720)", 
            "XGA(1024x768)", "SVGA(800x600)", "VGA(640x480)", 
            "CIF(400x296)", "QVGA(320x240)", "QCIF(176x144)"
        ]
        self.resolution_var = tk.StringVar(value="VGA(640x480)")
        resolution_combo = ttk.Combobox(
            camera_frame, 
            textvariable=self.resolution_var,
            values=resolutions,
            state="readonly"
        )
        resolution_combo.pack(fill=tk.X, padx=5, pady=2)
        resolution_combo.bind('<<ComboboxSelected>>', self.update_resolution)

        # Quality Control
        ttk.Label(camera_frame, text="Quality (10-63):").pack(pady=2)
        self.quality_var = tk.IntVar(value=12)
        quality_scale = ttk.Scale(
            camera_frame,
            from_=10,
            to=63,
            orient=tk.HORIZONTAL,
            variable=self.quality_var,
            command=self.update_quality
        )
        quality_scale.pack(fill=tk.X, padx=5, pady=2)

        # Flash Control
        flash_frame = ttk.Frame(camera_frame)
        flash_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(flash_frame, text="Flash:").pack(side=tk.LEFT)
        self.flash_var = tk.IntVar(value=0)
        flash_scale = ttk.Scale(
            flash_frame,
            from_=0,
            to=255,
            orient=tk.HORIZONTAL,
            variable=self.flash_var,
            command=self.update_flash
        )
        flash_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        self.flash_btn = ttk.Button(
            flash_frame,
            text="Toggle Flash",
            command=self.toggle_flash
        )
        self.flash_btn.pack(side=tk.RIGHT)

        # Motor Speed Control
        speed_frame = ttk.LabelFrame(scrollable_frame, text="Motor Speed")
        speed_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.speed_var = tk.IntVar(value=255)
        speed_scale = ttk.Scale(
            speed_frame,
            from_=0,
            to=255,
            orient=tk.HORIZONTAL,
            variable=self.speed_var,
            command=self.update_speed
        )
        speed_scale.pack(fill=tk.X, padx=5, pady=5)
        
        # Auto Follow Controls
        follow_frame = ttk.LabelFrame(scrollable_frame, text="Auto Follow")
        follow_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.follow_btn = ttk.Button(
            follow_frame,
            text="Start Following",
            command=self.toggle_follow
        )
        self.follow_btn.pack(fill=tk.X, padx=5, pady=5)
        
        # Camera Source Selection
        source_frame = ttk.LabelFrame(scrollable_frame, text="Camera Source")
        source_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.source_var = tk.StringVar(value="Webcam")
        for source in CAMERA_SOURCES.keys():
            ttk.Radiobutton(
                source_frame,
                text=source,
                value=source,
                variable=self.source_var,
                command=self.switch_camera
            ).pack(anchor=tk.W, padx=5, pady=2)
        
        # Add URL entry for custom stream
        ttk.Label(source_frame, text="Stream URL:").pack(padx=5, pady=2)
        self.url_entry = ttk.Entry(source_frame)
        self.url_entry.pack(fill=tk.X, padx=5, pady=2)
        
        # Add button to apply URL
        ttk.Button(
            source_frame,
            text="Connect to Stream",
            command=self.connect_to_stream
        ).pack(fill=tk.X, padx=5, pady=2)
        
        # Add button to manually reconnect
        ttk.Button(
            source_frame,
            text="Reconnect Camera",
            command=self.reconnect_camera
        ).pack(fill=tk.X, padx=5, pady=5)
        
        # Add Hand Following Controls
        hand_frame = ttk.LabelFrame(scrollable_frame, text="Hand Following")
        hand_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.hand_btn = ttk.Button(
            hand_frame,
            text="Start Hand Following",
            command=self.toggle_hand_following
        )
        self.hand_btn.pack(fill=tk.X, padx=5, pady=5)
        
        # Add close button at the top of controls
        close_frame = ttk.Frame(scrollable_frame)
        close_frame.pack(fill=tk.X, padx=5, pady=5)

        # Configure close button style
        style.configure('Close.TButton', 
            padding=10,
            font=('Arial', 10, 'bold')
        )

        self.close_btn = ttk.Button(
            close_frame,
            text="Close Application",
            style='Close.TButton',
            command=self.close_application
        )
        self.close_btn.pack(fill=tk.X)
    
    def toggle_auto_control(self):
        self.auto_control = not self.auto_control
        self.auto_button.configure(
            text="Stop Auto Control" if self.auto_control else "Start Auto Control"
        )
    
    def send_command(self, command):
        """Send command with better error handling"""
        try:
            response = requests.get(
                f"{self.CONTROL_URL}?command={command}", 
                timeout=2
            )
            if response.status_code == 200:
                print(f"Command sent: {command}")
                return True
            else:
                print(f"Command failed with status: {response.status_code}")
                return False
        except requests.exceptions.Timeout:
            print("Command timed out")
            return False
        except requests.exceptions.ConnectionError:
            print("Connection failed")
            return False
        except Exception as e:
            print(f"Error sending command: {e}")
            return False
    
    def control_robot(self, target_x, frame_width):
        # Simple control logic based on target position
        center = frame_width // 2
        margin = frame_width // 6  # Tolerance margin
        
        if target_x < (center - margin):
            self.send_command('2')  # Turn left
        elif target_x > (center + margin):
            self.send_command('4')  # Turn right
        else:
            self.send_command('1')  # Move forward
    
    def connect_to_camera(self):
        """Attempt to connect to the selected camera source"""
        try:
            if self.cap is not None:
                self.cap.release()
                
            source = CAMERA_SOURCES[self.current_source]
            
            if source["type"] == "webcam":
                self.cap = cv2.VideoCapture(source["source"])
            elif source["type"] == "stream":
                if not self.stream_url:
                    print("No stream URL provided")
                    return False
                self.cap = cv2.VideoCapture(self.stream_url)
            
            if not self.cap.isOpened():
                print(f"Error: Could not open {self.current_source}")
                return False
                
            # Try to get a frame
            ret, frame = self.cap.read()
            if ret and frame is not None:
                print(f"Successfully connected to {self.current_source}")
                return True
                
            print("Error: Could not read frame")
            self.cap.release()
            return False
            
        except Exception as e:
            print(f"Error in connect_to_camera: {str(e)}")
            if self.cap is not None:
                self.cap.release()
            return False
    
    def process_video(self):
        try:
            if not self.cap or not self.cap.isOpened():
                if not self.connect_to_camera():
                    self.root.after(2000, self.process_video)
                    return

            ret, frame = self.cap.read()
            if not ret or frame is None:
                if not self.connect_to_camera():
                    self.root.after(2000, self.process_video)
                    return

            # Resize frame immediately for faster processing
            frame = cv2.resize(frame, self.display_size)

            # Process based on active mode
            if self.hand_following and (self.frame_count % 2 == 0):
                frame, status = self.process_hand_detection(frame)
                # Buffer the status
                if status:
                    self.status_buffer = status
            
            elif self.is_detecting and (self.frame_count % self.process_every_n_frames == 0):
                # YOLO detection code remains the same but works with smaller frame
                detection_frame = cv2.resize(frame, self.detection_size)
                
                # YOLO detection
                blob = cv2.dnn.blobFromImage(
                    detection_frame, 
                    1/255.0, 
                    self.detection_size, 
                    swapRB=True, 
                    crop=False
                )
                self.net.setInput(blob)
                outs = self.net.forward(self.output_layers)

                # Process detections
                boxes = []
                confidences = []
                class_ids = []
                height, width = frame.shape[:2]
                
                # Scale factors for original frame size
                x_scale = width / self.detection_size[0]
                y_scale = height / self.detection_size[1]

                for out in outs:
                    for detection in out:
                        scores = detection[5:]
                        class_id = np.argmax(scores)
                        confidence = scores[class_id]
                        
                        if confidence > self.confidence_threshold:
                            # Scale back to original frame size
                            center_x = int(detection[0] * self.detection_size[0] * x_scale)
                            center_y = int(detection[1] * self.detection_size[1] * y_scale)
                            w = int(detection[2] * self.detection_size[0] * x_scale)
                            h = int(detection[3] * self.detection_size[1] * y_scale)
                            x = int(center_x - w/2)
                            y = int(center_y - h/2)
                            
                            boxes.append([x, y, w, h])
                            confidences.append(float(confidence))
                            class_ids.append(class_id)

                # Non-max suppression
                indexes = cv2.dnn.NMSBoxes(boxes, confidences, 0.5, 0.4)
                
                # Create text overlay for detections
                overlay = frame.copy()
                overlay_height = 120
                cv2.rectangle(overlay, (0, 0), (frame.shape[1], overlay_height), 
                             self.overlay_color, -1)
                cv2.addWeighted(overlay, self.overlay_alpha, frame, 1 - self.overlay_alpha, 
                               0, frame)

                # Draw boxes and labels with better visibility
                font = cv2.FONT_HERSHEY_SIMPLEX
                for i in range(len(boxes)):
                    if i in indexes:
                        x, y, w, h = boxes[i]
                        label = str(self.classes[class_ids[i]])
                        confidence = confidences[i]
                        
                        # Different colors for different objects
                        color = (0, 255, 0) if label == self.target_var.get() else (255, 0, 0)
                        
                        # Draw box
                        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
                        
                        # Draw text with better visibility
                        text = f'{label} {confidence:.2f}'
                        cv2.putText(frame, text, (x, y - 5), font, 0.5, (255, 255, 255), 2)

                # After processing detections, update detection buffer
                current_detections = []
                for i in range(len(boxes)):
                    if i in indexes:
                        label = str(self.classes[class_ids[i]])
                        confidence = confidences[i]
                        current_detections.append(f"{label}: {confidence:.2f}")
                
                if current_detections:
                    self.detection_buffer = current_detections[:3]  # Keep top 3 detections

            # Update frame counter
            self.frame_count += 1

            # Convert to RGB and display (no need to resize again)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            imgtk = ImageTk.PhotoImage(image=img)
            self.video_canvas.create_image(0, 0, anchor=tk.NW, image=imgtk)
            self.video_canvas.imgtk = imgtk

            # Update FPS less frequently
            current_time = time.time()
            if current_time - self.last_frame_time > 0.5:  # Update every 0.5 seconds
                fps = 1.0 / (current_time - self.last_frame_time)
                self.video_canvas.itemconfig(
                    self.fps_label,
                    text=f"FPS: {fps:.1f}"
                )
                self.last_frame_time = current_time

            # Update status text less frequently and with smoother transitions
            if current_time - self.status_update_time > self.status_update_interval:
                if self.hand_following:
                    new_status = f"Mode: Hand Following - {self.status_buffer}"
                    if new_status != self.current_status:
                        self.current_status = new_status
                        self.video_canvas.itemconfig(
                            self.status_label,
                            text=self.current_status
                        )
                elif self.auto_control:
                    self.video_canvas.itemconfig(
                        self.status_label,
                        text="Mode: Auto Control"
                    )
                else:
                    self.video_canvas.itemconfig(
                        self.status_label,
                        text="Mode: Manual Control"
                    )
                self.status_update_time = current_time

            # Update detection text with smoother transitions
            if current_time - self.detection_update_time > self.detection_update_interval:
                if self.is_detecting and self.detection_buffer:
                    new_detection = "Detected: " + ", ".join(self.detection_buffer)
                    if new_detection != self.current_detection:
                        self.current_detection = new_detection
                        self.video_canvas.itemconfig(
                            self.detection_label,
                            text=self.current_detection
                        )
                self.detection_update_time = current_time

            # Schedule next update with longer interval
            self.root.after(30, self.process_video)  # 30ms instead of 20ms

        except Exception as e:
            print(f"Error in process_video: {e}")
            self.root.after(2000, self.process_video)
    
    def __del__(self):
        self.cleanup()
    
    # Add methods for controls
    def update_speed(self, value):
        try:
            requests.get(
                f"{CONTROL_URL}?var=speed&val={int(float(value))}",
                timeout=1
            )
            print(f"Speed updated to {value}")
        except Exception as e:
            print(f"Error updating speed: {e}")

    def update_flash(self, value):
        """Update flash with better error handling"""
        try:
            # Convert value to int and ensure it's between 0-255
            flash_value = max(0, min(255, int(float(value))))
            response = requests.get(
                f"{self.CONTROL_URL}?var=flash&val={flash_value}",
                timeout=2
            )
            if response.status_code == 200:
                print(f"Flash updated to {flash_value}")
                return True
            else:
                print(f"Flash update failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"Error updating flash: {e}")
            return False

    def toggle_flash(self):
        """Toggle flash between off and full brightness"""
        current = self.flash_var.get()
        new_value = 0 if current > 0 else 255
        self.flash_var.set(new_value)
        self.update_flash(new_value)

    # Add keyboard bindings
    def setup_keyboard_bindings(self):
        self.root.bind('<KeyPress>', self.handle_keypress)
        self.root.bind('<KeyRelease>', self.handle_keyrelease)

    def handle_keypress(self, event):
        if not self.auto_control:  # Only handle manual controls when auto is off
            if event.keysym == 'Up':
                self.send_command('1')
                self.btn_forward.state(['pressed'])
            elif event.keysym == 'Left':
                self.send_command('2')
                self.btn_left.state(['pressed'])
            elif event.keysym == 'space':
                self.send_command('3')
                self.btn_stop.state(['pressed'])
            elif event.keysym == 'Right':
                self.send_command('4')
                self.btn_right.state(['pressed'])
            elif event.keysym == 'Down':
                self.send_command('5')
                self.btn_backward.state(['pressed'])

    def handle_keyrelease(self, event):
        if not self.auto_control:
            if event.keysym in ['Up', 'Left', 'Right', 'Down', 'space']:
                self.send_command('3')  # Stop on key release
                for btn in [self.btn_forward, self.btn_left, self.btn_right, 
                          self.btn_backward, self.btn_stop]:
                    btn.state(['!pressed'])

    def update_resolution(self, event=None):
        resolution_map = {
            "UXGA(1600x1200)": 13, "SXGA(1280x1024)": 12,
            "HD(1280x720)": 11, "XGA(1024x768)": 10,
            "SVGA(800x600)": 9, "VGA(640x480)": 8,
            "CIF(400x296)": 7, "QVGA(320x240)": 6,
            "QCIF(176x144)": 5
        }
        value = resolution_map.get(self.resolution_var.get(), 8)
        try:
            requests.get(
                f"{CONTROL_URL}?var=framesize&val={value}",
                timeout=1
            )
            print(f"Resolution updated to {self.resolution_var.get()}")
        except Exception as e:
            print(f"Error updating resolution: {e}")

    def update_quality(self, value):
        try:
            requests.get(
                f"{CONTROL_URL}?var=quality&val={int(float(value))}",
                timeout=1
            )
            print(f"Quality updated to {value}")
        except Exception as e:
            print(f"Error updating quality: {e}")

    def toggle_follow(self):
        self.auto_control = not self.auto_control
        self.follow_btn.config(
            text="Stop Following" if self.auto_control else "Start Following"
        )
        
        # Disable manual controls when auto-following
        for btn in [self.btn_forward, self.btn_left, self.btn_right, 
                   self.btn_backward, self.btn_stop]:
            btn.state(['disabled'] if self.auto_control else ['!disabled'])
        
        print(f"Auto follow {'enabled' if self.auto_control else 'disabled'}")

    def switch_camera(self):
        """Switch camera source"""
        try:
            source = self.source_var.get()
            if source in CAMERA_SOURCES:
                self.current_source = source
                if source == "Custom Stream" and not self.stream_url:
                    messagebox.showinfo("Info", "Please enter a stream URL and click 'Connect to Stream'")
                    return
                
                if self.connect_to_camera():
                    print("Successfully switched camera")
                else:
                    print("Failed to connect to new camera")
                    messagebox.showerror("Error", f"Could not connect to {source}")
        except Exception as e:
            print(f"Error switching camera: {str(e)}")

    def reconnect_camera(self):
        """Manually reconnect to current camera source"""
        if hasattr(self, 'cap'):
            self.cap.release()
        self.connect_to_camera()

    def cleanup(self):
        """Cleanup resources"""
        if hasattr(self, 'cap') and self.cap is not None:
            self.cap.release()

    def toggle_hand_following(self):
        """Toggle hand following mode"""
        self.hand_following = not self.hand_following
        
        # Update button text
        self.hand_btn.config(
            text="Stop Hand Following" if self.hand_following else "Start Hand Following"
        )
        
        # Disable object detection when hand following is active
        if self.hand_following:
            self.is_detecting = False
            self.auto_control = False
            # Update status
            self.video_canvas.itemconfig(
                self.status_label,
                text="Mode: Hand Following"
            )
        else:
            # Stop the robot when disabling hand following
            self.send_command('3')
            self.video_canvas.itemconfig(
                self.status_label,
                text="Mode: Manual Control"
            )
        
        print(f"Hand following {'enabled' if self.hand_following else 'disabled'}")

    def process_hand_detection(self, frame):
        try:
            # Convert BGR to RGB without copying
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Process the frame with MediaPipe
            rgb_frame.flags.writeable = False  # Performance optimization
            results = self.hands.process(rgb_frame)
            rgb_frame.flags.writeable = True
            
            height, width = frame.shape[:2]
            center_x = width // 2
            margin = width // 6

            status = ""
            if results.multi_hand_landmarks:
                hand_landmarks = results.multi_hand_landmarks[0]
                
                # Draw minimal hand landmarks
                self.mp_draw.draw_landmarks(
                    frame,
                    hand_landmarks,
                    self.mp_hands.HAND_CONNECTIONS,
                    self.mp_draw.DrawingSpec(color=(0, 255, 0), thickness=1, circle_radius=1),
                    self.mp_draw.DrawingSpec(color=(0, 0, 255), thickness=1)
                )
                
                palm_x = int(hand_landmarks.landmark[9].x * width)
                palm_y = int(hand_landmarks.landmark[9].y * height)
                
                cv2.circle(frame, (palm_x, palm_y), 5, (0, 255, 255), -1)
                
                if palm_y > height * 0.6:
                    self.send_command('5')
                    status = "BACKWARD"
                else:
                    if palm_x < (center_x - margin):
                        self.send_command('2')
                        status = "LEFT"
                    elif palm_x > (center_x + margin):
                        self.send_command('4')
                        status = "RIGHT"
                    else:
                        self.send_command('1')
                        status = "FORWARD"
                
                # Create text overlay
                overlay = frame.copy()
                overlay_height = 120  # Height of overlay area
                cv2.rectangle(overlay, (0, 0), (frame.shape[1], overlay_height), 
                             self.overlay_color, -1)
                cv2.addWeighted(overlay, self.overlay_alpha, frame, 1 - self.overlay_alpha, 
                               0, frame)

                # Draw status on frame with better visibility
                cv2.putText(frame, status, (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            else:
                self.send_command('3')
                status = "NO HAND"
                cv2.putText(frame, status, (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            return frame, status
            
        except Exception as e:
            print(f"Error in hand detection: {e}")
            return frame, "ERROR"

    def connect_to_stream(self):
        """Connect to custom stream URL"""
        url = self.url_entry.get().strip()
        if url:
            self.stream_url = url
            self.current_source = "Custom Stream"
            self.source_var.set("Custom Stream")
            self.connect_to_camera()
        else:
            messagebox.showerror("Error", "Please enter a stream URL")

    def close_application(self):
        """Properly clean up and close the application"""
        try:
            # Stop any ongoing operations
            self.is_detecting = False
            self.auto_control = False
            self.hand_following = False
            
            # Send stop command to robot
            self.send_command('3')
            
            # Release camera
            if self.cap is not None:
                self.cap.release()
            
            # Release MediaPipe resources
            if hasattr(self, 'hands'):
                self.hands.close()
            
            # Destroy the root window
            self.root.quit()
            self.root.destroy()
            
        except Exception as e:
            print(f"Error during shutdown: {e}")
            # Force quit if clean shutdown fails
            self.root.destroy()

def main():
    try:
        root = tk.Tk()
        app = ObjectDetectionGUI(root)
        root.protocol("WM_DELETE_WINDOW", app.close_application)  # Use close_application instead of cleanup
        root.mainloop()
    except Exception as e:
        print(f"Error in main: {str(e)}")

if __name__ == "__main__":
    main()