import asyncio
import websockets
import json
import tkinter as tk
from PIL import ImageGrab, Image
import io
import base64
import threading
import time
import socket
import http.server
import socketserver
import os
import sys
import webbrowser
import subprocess
import urllib.request
import urllib.error
import traceback
import platform
from tkinter import ttk

# Detect the current operating system once so we can branch on it where needed.
IS_WINDOWS = platform.system() == "Windows"
IS_MAC = platform.system() == "Darwin"

class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, directory=None, ws_port=None, **kwargs):
        self.ws_port = ws_port
        # Set the directory to the folder containing the mirrorindex.html
        if directory is None:
            directory = os.path.dirname(os.path.abspath(__file__))
        super().__init__(*args, directory=directory, **kwargs)
    
    def log_message(self, format, *args):
        # Silence HTTP logs to avoid cluttering the console
        pass
        
    def do_GET(self):
        # Handle request to get the WebSocket port
        if self.path == '/get_ws_port':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')  # Enable CORS
            self.send_header('Cache-Control', 'no-cache, no-store')  # Prevent caching
            self.end_headers()
            response = json.dumps({'ws_port': self.ws_port})
            print(f"Client requested WebSocket port. Sending: {self.ws_port}")
            self.wfile.write(response.encode('utf-8'))
            return
        
        # Serve the index page for root requests
        if self.path == '/' or self.path == '/index.html':
            self.path = '/mirrorindex.html'
        
        # Otherwise serve files as usual
        return super().do_GET()

class MirrorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Screen Mirror Server")
        self.root.geometry("440x560")  # Room for rotation, crop, grayscale + buttons
        
        # Create a frame for controls
        control_frame = tk.Frame(root, padx=10, pady=10)
        control_frame.pack(fill=tk.X)
        
        # Add rotation control
        rotation_frame = tk.Frame(control_frame)
        rotation_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(rotation_frame, text="Rotation:").pack(side=tk.LEFT)
        
        # Rotation variable and radio buttons
        self.rotation_var = tk.IntVar(value=0)
        rotations = [
            ("0°", 0),
            ("90°", 90),
            ("180°", 180),
            ("270°", 270)
        ]
        
        # Create radio buttons for each rotation option
        rotation_buttons_frame = tk.Frame(rotation_frame)
        rotation_buttons_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        for text, value in rotations:
            tk.Radiobutton(
                rotation_buttons_frame,
                text=text,
                variable=self.rotation_var,
                value=value
            ).pack(side=tk.LEFT, padx=10)
        
        # Quality slider
        quality_frame = tk.Frame(control_frame)
        quality_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(quality_frame, text="Image Quality:").pack(side=tk.LEFT)
        # Higher default: sharper text on a high-DPI (300 ppi) Kindle.
        self.quality_var = tk.IntVar(value=80)
        quality_slider = ttk.Scale(quality_frame, from_=10, to=95, 
                                   variable=self.quality_var, orient=tk.HORIZONTAL)
        quality_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        tk.Label(quality_frame, textvariable=self.quality_var).pack(side=tk.LEFT, padx=5)
        
        # Resolution scaling slider
        scale_frame = tk.Frame(control_frame)
        scale_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(scale_frame, text="Resolution Scale:").pack(side=tk.LEFT)
        self.scale_var = tk.DoubleVar(value=1.0)
        scale_slider = ttk.Scale(scale_frame, from_=0.1, to=1.0, 
                                variable=self.scale_var, orient=tk.HORIZONTAL)
        scale_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Display the scale value with 1 decimal place
        self.scale_label = tk.Label(scale_frame, text="1.0")
        self.scale_label.pack(side=tk.LEFT, padx=5)
        
        # Update label when scale changes
        self.scale_var.trace_add("write", self.update_scale_label)
        
        # FPS control
        fps_frame = tk.Frame(control_frame)
        fps_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(fps_frame, text="FPS:").pack(side=tk.LEFT)
        self.fps_var = tk.IntVar(value=10)
        fps_slider = ttk.Scale(fps_frame, from_=1, to=30, 
                              variable=self.fps_var, orient=tk.HORIZONTAL)
        fps_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        tk.Label(fps_frame, textvariable=self.fps_var).pack(side=tk.LEFT, padx=5)
        
        # E-ink clarity: a Kindle's screen is grayscale, so sending colour makes
        # it dither (which blurs text). Sending grayscale looks sharper on a
        # 300 ppi e-ink display and uses less bandwidth.
        eink_frame = tk.Frame(control_frame)
        eink_frame.pack(fill=tk.X, pady=5)
        self.grayscale_var = tk.BooleanVar(value=False)
        tk.Checkbutton(eink_frame, text="Grayscale (sharper on e-ink Kindle)",
                       variable=self.grayscale_var).pack(side=tk.LEFT)

        # Capture-region controls: let a wide screen be cropped to the
        # Kindle's shape so it fills the display instead of being letterboxed.
        crop_frame = tk.Frame(control_frame)
        crop_frame.pack(fill=tk.X, pady=5)

        self.crop_enabled = tk.BooleanVar(value=False)
        self.crop_region = None  # (fx0, fy0, fx1, fy1) fractions of the screen
        tk.Checkbutton(crop_frame, text="Crop to region",
                       variable=self.crop_enabled).pack(side=tk.LEFT)

        tk.Label(crop_frame, text="Shape:").pack(side=tk.LEFT, padx=(8, 2))
        # Aspect ratios are width:height. Portrait options are for a Kindle
        # held upright; landscape for one turned on its side.
        self.aspect_choices = {
            "Free": None,
            "Kindle portrait 3:4": 3 / 4,
            "Kindle landscape 4:3": 4 / 3,
            "16:9": 16 / 9,
            "9:16": 9 / 16,
        }
        self.aspect_var = tk.StringVar(value="Kindle portrait 3:4")
        ttk.OptionMenu(crop_frame, self.aspect_var, self.aspect_var.get(),
                       *self.aspect_choices.keys()).pack(side=tk.LEFT)

        region_btn_frame = tk.Frame(control_frame)
        region_btn_frame.pack(fill=tk.X, pady=(0, 5))
        self._accent_button(region_btn_frame, "Select Region…",
                            self.select_region, "#4CAF50").pack(side=tk.LEFT, padx=5)
        tk.Button(region_btn_frame, text="Reset to Full Screen",
                  command=self.reset_region).pack(side=tk.LEFT, padx=5)
        self.region_label = tk.Label(region_btn_frame, text="Region: full screen",
                                     font=("Arial", 9))
        self.region_label.pack(side=tk.LEFT, padx=5)

        # "Open viewer" gets its own row so it's prominent and uncrowded.
        open_frame = tk.Frame(control_frame)
        open_frame.pack(fill=tk.X, pady=5)
        self.open_btn = self._accent_button(open_frame, "Open Viewer in Browser",
                                            self.open_viewer, "#9C27B0")
        self.open_btn.pack(fill=tk.X, padx=5)

        # Add a test connection button
        test_frame = tk.Frame(control_frame)
        test_frame.pack(fill=tk.X, pady=5)

        self.test_btn = self._accent_button(test_frame, "Test Connection",
                                            self.test_connection, "#2196F3")
        self.test_btn.pack(side=tk.LEFT, padx=5)

        self.restart_btn = self._accent_button(test_frame, "Restart Servers",
                                               self.restart_servers, "#FF9800")
        self.restart_btn.pack(side=tk.LEFT, padx=5)
        
        # Status label to show server state
        self.status_label = tk.Label(root, text="Starting servers...", font=("Arial", 12))
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X, pady=10)
        
        # Connection info
        self.conn_label = tk.Label(root, text="", font=("Arial", 10))
        self.conn_label.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Get local IP using improved method
        self.local_ip = self.get_local_ip()
        
        # This variable will hold the latest captured screen image as a base64 string.
        self.latest_image = None
        
        # Flag to control the screen capture loop.
        self.capturing = True
        
        # Server ports - find available ports for both
        self.http_port = self.find_available_port(8000)
        self.ws_port = self.find_available_port(8765)
        
        if self.http_port is None or self.ws_port is None:
            error_msg = "Error: Could not find available ports"
            print(error_msg)
            self.status_label.config(text=error_msg)
            return
        
        # Start HTTP server in a separate thread
        self.http_server_thread = threading.Thread(target=self.start_http_server)
        self.http_server_thread.daemon = True
        self.http_server_thread.start()
        
        # Start WebSocket server in a separate thread
        self.server_thread = threading.Thread(target=self.start_server)
        self.server_thread.daemon = True
        self.server_thread.start()
        
        # Start screen capture loop in a separate thread
        self.capture_thread = threading.Thread(target=self.capture_loop)
        self.capture_thread.daemon = True
        self.capture_thread.start()
        
        # Open the viewer automatically on Windows only. On macOS the Mac
        # browser isn't the target (the Kindle is), so don't steal focus with a
        # new window every launch — use the "Open Viewer in Browser" button.
        if not IS_MAC:
            self.open_browser_thread = threading.Thread(target=self.open_browser)
            self.open_browser_thread.daemon = True
            self.open_browser_thread.start()
        
        # Update connection info
        self.update_connection_info()
    
    def update_scale_label(self, *args):
        self.scale_label.config(text=f"{self.scale_var.get():.1f}")

    def _accent_button(self, parent, text, command, color):
        """Create a colored action button that stays readable on every OS.

        On macOS tk.Button ignores the bg colour but still applies fg, so the
        original "white text on a coloured button" rendered as white-on-white
        (invisible). Use a plain native button there; keep colours on Windows.
        """
        if IS_MAC:
            return tk.Button(parent, text=text, command=command)
        return tk.Button(parent, text=text, command=command, bg=color, fg="white")

    def reset_region(self):
        """Clear the crop region so the whole screen is mirrored again."""
        self.crop_region = None
        self.crop_enabled.set(False)
        self.region_label.config(text="Region: full screen")

    def select_region(self):
        """Drag a rectangle over the screen to choose the capture region.

        Opens a dimmed full-screen overlay; the user drags to draw a box. If a
        fixed aspect ratio is chosen, the box is constrained to it so the result
        fills the Kindle without letterbox bars. Coordinates are stored as
        fractions of the screen so they survive Retina/resolution differences.
        """
        ratio = self.aspect_choices.get(self.aspect_var.get())  # width/height or None

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()

        overlay = tk.Toplevel(self.root)
        # Use a borderless window sized to the screen rather than the native
        # "-fullscreen" attribute. On macOS -fullscreen opens a *separate Space*
        # and the desktop flips away to it; overrideredirect keeps the overlay
        # on the CURRENT desktop, where the user is actually selecting.
        overlay.overrideredirect(True)
        overlay.geometry(f"{sw}x{sh}+0+0")
        overlay.attributes("-alpha", 0.3)
        overlay.attributes("-topmost", True)
        overlay.configure(bg="black")
        canvas = tk.Canvas(overlay, cursor="cross", bg="gray15", highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        overlay.update_idletasks()
        overlay.lift()
        overlay.focus_force()
        canvas.focus_set()
        canvas.create_text(sw // 2, 40, fill="white", font=("Arial", 16),
                           text="Drag to select the area to mirror  •  Esc to cancel")

        state = {"x0": 0, "y0": 0, "rect": None}

        def on_press(event):
            state["x0"], state["y0"] = event.x, event.y
            if state["rect"]:
                canvas.delete(state["rect"])
            state["rect"] = canvas.create_rectangle(event.x, event.y, event.x, event.y,
                                                    outline="#00E5FF", width=3)

        def on_drag(event):
            x, y = event.x, event.y
            if ratio:
                # Constrain to the chosen aspect ratio (width/height).
                dx, dy = x - state["x0"], y - state["y0"]
                sx = 1 if dx >= 0 else -1
                sy = 1 if dy >= 0 else -1
                if abs(dx) / ratio >= abs(dy):
                    dy = sy * abs(dx) / ratio
                else:
                    dx = sx * abs(dy) * ratio
                x, y = state["x0"] + dx, state["y0"] + dy
            canvas.coords(state["rect"], state["x0"], state["y0"], x, y)

        def on_release(event):
            x0, y0, x1, y1 = canvas.coords(state["rect"])
            overlay.destroy()
            left, right = sorted((x0, x1))
            top, bottom = sorted((y0, y1))
            if right - left < 5 or bottom - top < 5:
                return  # too small, treat as a misclick
            self.crop_region = (left / sw, top / sh, right / sw, bottom / sh)
            self.crop_enabled.set(True)
            self.region_label.config(
                text=f"Region: {int(right - left)}x{int(bottom - top)} px")

        canvas.bind("<ButtonPress-1>", on_press)
        canvas.bind("<B1-Motion>", on_drag)
        canvas.bind("<ButtonRelease-1>", on_release)
        # Bind Escape on both the overlay and the canvas (which holds focus) so
        # cancelling works regardless of where key events are routed.
        for widget in (overlay, canvas):
            widget.bind("<Escape>", lambda e: overlay.destroy())
    
    def get_local_ip(self):
        """Get the actual local IP address that can be reached from other devices."""
        try:
            # Connect to a remote address to determine which local interface to use
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
                print(f"Detected network IP: {ip}")
                return ip
        except Exception as e:
            print(f"Failed to detect network IP: {e}")
            # Fallback to the original method
            fallback_ip = socket.gethostbyname(socket.gethostname())
            print(f"Using fallback IP: {fallback_ip}")
            return fallback_ip
    
    def run_network_diagnostics(self):
        """Run basic network diagnostics to help troubleshoot connectivity."""
        try:
            # Test if we can bind to the IP and ports
            print(f"Testing HTTP port {self.http_port}...")
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind((self.local_ip, self.http_port))
                print(f"✓ HTTP port {self.http_port} is accessible")
        except Exception as e:
            print(f"✗ HTTP port {self.http_port} test failed: {e}")
        
        try:
            print(f"Testing WebSocket port {self.ws_port}...")
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind((self.local_ip, self.ws_port))
                print(f"✓ WebSocket port {self.ws_port} is accessible")
        except Exception as e:
            print(f"✗ WebSocket port {self.ws_port} test failed: {e}")
        
        # Check for common network interfaces (command differs per OS)
        try:
            import subprocess
            if IS_WINDOWS:
                cmd = ['ipconfig']
                wifi_marker = 'Wireless LAN adapter Wi-Fi'
            else:
                # macOS / Linux: ifconfig lists interfaces; Wi-Fi is usually en0 on Mac
                cmd = ['ifconfig']
                wifi_marker = 'en0'
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if wifi_marker in result.stdout:
                print("✓ WiFi adapter detected")
            else:
                print("⚠ WiFi adapter not clearly detected")
        except Exception as e:
            print(f"Network interface check failed: {e}")
    
    def update_connection_info(self):
        # Create a message with both HTTP and WebSocket info
        info = f"Connect: http://{self.local_ip}:{self.http_port}/mirrorindex.html"
        self.conn_label.config(text=info)
        print("=" * 50)
        print("CONNECTION INFORMATION:")
        print(f"Server IP: {self.local_ip}")
        print(f"HTTP Port: {self.http_port}")
        print(f"WebSocket Port: {self.ws_port}")
        print(f"Full URL: {info}")
        print("\nNETWORK DIAGNOSTICS:")
        self.run_network_diagnostics()
        print("\nTROUBLESHOOTING TIPS:")
        print("1. Make sure both devices are on the same WiFi network")
        if IS_MAC:
            print("2. Grant Screen Recording permission: System Settings > Privacy & "
                  "Security > Screen Recording -> enable your Terminal/IDE, then "
                  "fully quit and reopen it")
            print("3. macOS firewall: System Settings > Network > Firewall "
                  "(allow incoming connections for python if prompted)")
        else:
            print("2. Check Windows Firewall settings")
            print("3. Try disabling Windows Firewall temporarily")
        print("4. Try accessing from this computer's browser first")
        print("5. Verify mirrorindex.html exists in the same folder")
        print(f"6. Test connectivity: ping {self.local_ip} from your Kindle/phone")
        print("=" * 50)
    
    def is_port_in_use(self, port):
        """Check if a port is already in use."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                # Set SO_REUSEADDR to handle TIME_WAIT state
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(('0.0.0.0', port))
                return False
            except OSError as e:
                print(f"Port {port} is in use: {e}")
                return True
    
    def find_available_port(self, start_port, max_attempts=10):
        """Find an available port starting from start_port."""
        port = start_port
        for _ in range(max_attempts):
            if not self.is_port_in_use(port):
                return port
            port += 1
        
        # If we couldn't find an available port, return None and handle it later
        print(f"Warning: Could not find an available port after {max_attempts} attempts")
        return None
    
    def open_browser(self):
        # Wait a moment for servers to start
        time.sleep(1.5)
        self.open_viewer()

    def open_viewer(self):
        """Open the mirror viewer page in the local browser (button action)."""
        url = f"http://{self.local_ip}:{self.http_port}/mirrorindex.html"
        try:
            webbrowser.open(url)
            print(f"Browser opened at {url}")
        except Exception as e:
            print(f"Failed to open browser: {e}")
    
    def update_status(self, message):
        self.root.after(0, lambda: self.status_label.config(text=message))
    
    def start_http_server(self):
        try:
            # Create a handler with access to the WebSocket port
            handler = lambda *args, **kwargs: CustomHTTPRequestHandler(
                *args, ws_port=self.ws_port, **kwargs
            )
            
            # Use SO_REUSEADDR to avoid "Address already in use" errors
            class ReuseAddrTCPServer(socketserver.TCPServer):
                allow_reuse_address = True
            
            with ReuseAddrTCPServer(("", self.http_port), handler) as httpd:
                print(f"HTTP server started at http://{self.local_ip}:{self.http_port}")
                print(f"WebSocket port is {self.ws_port}")
                self.update_status(f"HTTP: {self.local_ip}:{self.http_port}, WS: {self.ws_port}")
                self.update_connection_info()
                httpd.serve_forever()
        except Exception as e:
            error_msg = f"HTTP server error: {str(e)}"
            print(error_msg)
            self.update_status(error_msg)
    
    async def handler(self, websocket, path=None):
        client_addr = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        print(f"New client connected from: {client_addr}")
        self.update_status(f"Client connected: {client_addr}")
        try:
            while True:
                # If a new image is available, send it
                if self.latest_image:
                    message = json.dumps({
                        "type": "screen",
                        "image": self.latest_image,
                        "rotation": self.rotation_var.get()  # Send rotation info
                    })
                    await websocket.send(message)
                # Calculate sleep time based on FPS setting
                await asyncio.sleep(1 / self.fps_var.get())
        except websockets.exceptions.ConnectionClosed:
            print(f"Client {client_addr} disconnected")
            self.update_status("Client disconnected")
        except Exception as e:
            print(f"WebSocket error with client {client_addr}: {e}")
            self.update_status(f"WebSocket error: {str(e)}")
    
    def start_server(self):
        if self.ws_port is None:
            self.update_status("Error: Could not find an available WebSocket port")
            return
        
        async def run_websocket_server():
            """Async function to run the WebSocket server"""
            try:
                print(f"Starting WebSocket server on {self.local_ip}:{self.ws_port}")
                
                # Create a wrapper for the handler to make it compatible
                async def websocket_handler(websocket):
                    return await self.handler(websocket, None)
                
                server = await websockets.serve(websocket_handler, "0.0.0.0", self.ws_port)
                print(f"WebSocket server successfully started on {self.local_ip}:{self.ws_port}")
                await server.wait_closed()
            except Exception as e:
                error_msg = f"WebSocket server error: {str(e)}"
                print(error_msg)
                self.update_status(error_msg)
                traceback.print_exc()
        
        try:
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            status_msg = f"Servers running - WebSocket: {self.local_ip}:{self.ws_port}, HTTP: {self.local_ip}:{self.http_port}"
            print(status_msg)
            self.update_status(status_msg)
            
            # Run the WebSocket server
            loop.run_until_complete(run_websocket_server())
        except Exception as e:
            error_msg = f"WebSocket server error: {str(e)}"
            print(error_msg)
            self.update_status(error_msg)
            traceback.print_exc()
    
    def capture_loop(self):
        while self.capturing:
            try:
                # Capture the current screen
                screenshot = ImageGrab.grab()

                # On macOS ImageGrab.grab() returns an RGBA image, and JPEG
                # cannot store an alpha channel ("cannot write mode RGBA as
                # JPEG"). Drop alpha so the JPEG encode below works on every OS.
                if screenshot.mode != "RGB":
                    screenshot = screenshot.convert("RGB")

                # Crop to the selected region so a wide monitor fills the
                # Kindle instead of being letterboxed down to a tiny strip.
                # The region is stored as fractions (0..1) of the screen, which
                # keeps it correct regardless of Retina scaling or resolution.
                if self.crop_enabled.get() and self.crop_region is not None:
                    W, H = screenshot.size
                    fx0, fy0, fx1, fy1 = self.crop_region
                    box = (int(fx0 * W), int(fy0 * H), int(fx1 * W), int(fy1 * H))
                    # Guard against a zero-area box (would raise on save).
                    if box[2] - box[0] >= 2 and box[3] - box[1] >= 2:
                        screenshot = screenshot.crop(box)

                # Apply resolution scaling if needed (but no rotation here)
                scale_factor = self.scale_var.get()
                if scale_factor < 1.0:
                    new_width = int(screenshot.width * scale_factor)
                    new_height = int(screenshot.height * scale_factor)
                    screenshot = screenshot.resize((new_width, new_height), Image.Resampling.LANCZOS)

                # Convert to grayscale for e-ink Kindles (sharper, no colour
                # dithering). Done last so crop/scale still work in colour.
                if self.grayscale_var.get():
                    screenshot = screenshot.convert("L")

                buffer = io.BytesIO()
                # Save the screenshot as JPEG with quality setting from slider
                screenshot.save(buffer, format="JPEG", quality=self.quality_var.get())
                img_bytes = buffer.getvalue()
                # Encode the image bytes as a base64 string
                self.latest_image = base64.b64encode(img_bytes).decode('utf-8')
                
                # Calculate sleep time to match desired FPS
                time.sleep(1 / self.fps_var.get())
            except Exception as e:
                print("Error capturing screen:", e)
                if IS_MAC:
                    # screencapture fails until Screen Recording permission is granted.
                    msg = ("Screen capture blocked - grant Screen Recording "
                           "permission, then restart this app")
                    print("  -> macOS: System Settings > Privacy & Security > "
                          "Screen Recording -> enable your Terminal/IDE, then "
                          "fully quit & reopen it.")
                    self.update_status(msg)
                time.sleep(1)  # Wait a bit before retrying on error
    
    def test_connection(self):
        """Test if the server is accessible from the local network."""
        import urllib.request
        import urllib.error
        
        test_url = f"http://{self.local_ip}:{self.http_port}/get_ws_port"
        try:
            print(f"Testing connection to {test_url}...")
            response = urllib.request.urlopen(test_url, timeout=5)
            if response.getcode() == 200:
                print("✓ Server is accessible from local network")
                self.update_status("✓ Connection test successful")
            else:
                print(f"✗ Server returned status code: {response.getcode()}")
                self.update_status(f"✗ Test failed: HTTP {response.getcode()}")
        except urllib.error.URLError as e:
            print(f"✗ Connection test failed: {e}")
            self.update_status(f"✗ Connection test failed: {e}")
        except Exception as e:
            print(f"✗ Unexpected error during test: {e}")
            self.update_status(f"✗ Test error: {e}")
    
    def restart_servers(self):
        """Restart the servers (placeholder for now)."""
        print("To restart servers, please close and rerun the application.")
        self.update_status("Please restart the application to reset servers")

if __name__ == "__main__":
    root = tk.Tk()
    app = MirrorApp(root)

    def _on_close():
        # Closing the window should stop everything. Stop the capture loop and
        # tear down the GUI; the daemon server/capture threads end with the
        # process.
        app.capturing = False
        try:
            root.destroy()
        except Exception:
            pass

    root.protocol("WM_DELETE_WINDOW", _on_close)
    root.mainloop()

    # Force a clean, immediate process exit once the window is gone so the
    # launching terminal returns right away (daemon threads / the asyncio loop
    # could otherwise keep the interpreter alive on macOS).
    sys.stdout.flush()
    os._exit(0)
