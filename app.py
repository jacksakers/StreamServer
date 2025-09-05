import os
import shutil
import signal
import subprocess
import atexit
from flask import Flask, render_template, Response

# --- Configuration ---
# Update these RTSP URLs with the actual URLs of your security cameras.
# The dictionary key (e.g., "camera1") will be used in the URL and to create directories.
STREAMS = {
    "camera1": "rtsp://inspiration:ideasFlowFreely09@192.168.0.131/stream1",
    # "camera2": "rtsp://YOUR_CAMERA_2_IP_OR_URL",
    # Example with credentials: "rtsp://user:password@192.168.1.100:554/stream1"
}

# Directory to store the HLS stream files.
HLS_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "streams")

# --- Global Variables ---
ffmpeg_processes = {}
app = Flask(__name__)

# --- FFmpeg Stream Conversion ---

def start_stream_conversion():
    """
    Starts an ffmpeg process for each stream defined in the STREAMS configuration.
    """
    print("Starting FFmpeg stream conversion processes...")
    if os.path.exists(HLS_OUTPUT_DIR):
        shutil.rmtree(HLS_OUTPUT_DIR)
    os.makedirs(HLS_OUTPUT_DIR, exist_ok=True)

    for name, rtsp_url in STREAMS.items():
        stream_output_dir = os.path.join(HLS_OUTPUT_DIR, name)
        os.makedirs(stream_output_dir, exist_ok=True)
        
        # The ffmpeg command.
        # -c:v copy: Copies the video stream without re-encoding. This is crucial for low CPU usage.
        # -c:a aac: Re-encodes audio to AAC, which is widely compatible.
        # -f hls: Specifies the output format as HLS.
        # -hls_time 4: Sets the segment duration to 4 seconds.
        # -hls_list_size 5: Keeps the 5 most recent segments in the playlist.
        # -hls_flags delete_segments: Deletes old segments to save disk space.
        command = [
            'ffmpeg',
            '-i', rtsp_url,
            '-c:v', 'copy',
            '-c:a', 'aac',
            '-f', 'hls',
            '-hls_time', '4',
            '-hls_list_size', '5',
            '-hls_flags', 'delete_segments',
            os.path.join(stream_output_dir, 'stream.m3u8')
        ]

        print(f"Starting ffmpeg for '{name}'...")
        # Start the ffmpeg process. stdout and stderr are redirected to DEVNULL to avoid cluttering the console.
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        ffmpeg_processes[name] = process
        print(f"  - PID: {process.pid}")

# --- Cleanup Function ---

def cleanup():
    """
    Terminates all running ffmpeg processes and cleans up the HLS directory.
    This function is registered to run when the script exits.
    """
    print("\nShutting down server and cleaning up...")
    for name, process in ffmpeg_processes.items():
        print(f"Terminating ffmpeg process for '{name}' (PID: {process.pid})...")
        process.terminate()
        # Wait for the process to terminate
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print(f"Process for '{name}' did not terminate, killing.")
            process.kill()
            
    if os.path.exists(HLS_OUTPUT_DIR):
        print(f"Deleting HLS directory: {HLS_OUTPUT_DIR}")
        shutil.rmtree(HLS_OUTPUT_DIR)

# Register the cleanup function to be called on exit.
atexit.register(cleanup)
signal.signal(signal.SIGTERM, lambda signum, frame: exit())
signal.signal(signal.SIGINT, lambda signum, frame: exit())


# --- Flask Web Routes ---

@app.route('/')
def index():
    """
    Renders the main HTML page that displays the video streams.
    """
    # Convert the dict_keys object to a list so it can be JSON serialized
    return render_template('index.html', stream_names=list(STREAMS.keys()))

@app.route('/streams/<stream_name>/<filename>')
def serve_hls_files(stream_name, filename):
    """
    Serves the HLS files (.m3u8 playlist and .ts video segments).
    """
    if stream_name not in STREAMS:
        return "Stream not found", 404
        
    file_path = os.path.join(HLS_OUTPUT_DIR, stream_name, filename)
    
    if not os.path.exists(file_path):
        return "File not found", 404

    return Response(open(file_path, 'rb'), mimetype='application/vnd.apple.mpegurl' if '.m3u8' in filename else 'video/MP2T')

# --- Main Execution ---

if __name__ == '__main__':
    start_stream_conversion()
    # To run on your local network, use host='0.0.0.0'
    app.run(host='0.0.0.0', port=8080)

