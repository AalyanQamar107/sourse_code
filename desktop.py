# desktop.py
import sys
import os
import time
import threading
import webbrowser
import subprocess
from multiprocessing import Process, freeze_support

# ------------------------------------------------------------------
# No more logging to file – all output goes to console if available
# ------------------------------------------------------------------
def log_info(msg):
    """Print info message to console (works even with --noconsole on Windows? no, but no file is created)."""
    try:
        print(msg)
    except:
        pass

def log_error(msg):
    try:
        print(f"ERROR: {msg}")
    except:
        pass

# ------------------------------------------------------------------
# Fix paths for frozen executable
# ------------------------------------------------------------------
def get_base_path():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    else:
        return os.path.abspath(".")

BASE_PATH = get_base_path()

# ------------------------------------------------------------------
# Flask server starter (runs in a separate process)
# ------------------------------------------------------------------
def start_flask():
    """Start the Flask app. This runs in a separate process."""
    # Set environment variables so Flask finds templates/static
    os.environ['FLASK_TEMPLATES_FOLDER'] = os.path.join(BASE_PATH, 'templates')
    os.environ['FLASK_STATIC_FOLDER'] = os.path.join(BASE_PATH, 'static')
    
    # Now import and run Flask
    import sys
    sys.path.insert(0, BASE_PATH)  # ensure local imports work
    from app import app
    
    # Run without reloader and without debug
    app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)

# ------------------------------------------------------------------
# Wait for Flask to be ready
# ------------------------------------------------------------------
def wait_for_flask(timeout=10):
    """Wait until Flask responds on http://127.0.0.1:5000"""
    import urllib.request
    import urllib.error
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            urllib.request.urlopen('http://127.0.0.1:5000', timeout=1)
            log_info("Flask server is ready.")
            return True
        except:
            time.sleep(0.5)
    log_error("Flask server did not start in time.")
    return False

# ------------------------------------------------------------------
# Main entry point
# ------------------------------------------------------------------
def main():
    log_info("Starting ForensiChat Desktop App")
    log_info(f"Base path: {BASE_PATH}")
    
    # Start Flask in a separate process (not thread, to avoid GIL issues)
    flask_process = Process(target=start_flask, daemon=True)
    flask_process.start()
    log_info("Flask process started, waiting for server...")
    
    # Wait for server to be ready
    if not wait_for_flask():
        log_error("Could not connect to Flask server. Exiting.")
        flask_process.terminate()
        return
    
    # Now open the pywebview window
    try:
        import webview
        log_info("Opening pywebview window...")
        webview.create_window(
            title='ForensiChat',
            url='http://127.0.0.1:5000',
            width=1400,
            height=900,
            resizable=True,
            min_size=(800, 600),
            fullscreen=False
        )
        webview.start()
    except Exception as e:
        log_error(f"Failed to start pywebview: {e}")
    finally:
        log_info("Window closed, terminating Flask process.")
        flask_process.terminate()
        flask_process.join()
        log_info("Clean exit.")

if __name__ == '__main__':
    freeze_support()   # Required for multiprocessing on Windows when frozen
    main()