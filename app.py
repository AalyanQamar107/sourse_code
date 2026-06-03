"""
Flask web application for Forensic Assistant.
Auto-browser launch with server-ready polling.
"""
from flask import Flask, render_template, request, jsonify, send_file, redirect
import os
import platform
import sys
import ctypes
import webbrowser
import threading
import time
import urllib.request
import import_export as ie
from paths import get_reports_dir



def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)



app = Flask(__name__,
            template_folder=resource_path('templates'),
            static_folder=resource_path('static'))

analyzer   = None
rag        = None
report_gen = None


def is_admin():
    if platform.system().lower() == 'windows':
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False
    else:
        try:
            return os.geteuid() == 0
        except Exception:
            return False


def init_components():
    global analyzer, rag, report_gen
    if analyzer is None:
        try:
            from forensic import ForensicAnalyzer
            from rag      import HybridRAG
            from report   import ReportGenerator
            from database import init_db

            init_db()
            os.makedirs('uploads', exist_ok=True)
         

            analyzer   = ForensicAnalyzer()
            rag        = HybridRAG()
            report_gen = ReportGenerator()
            print("Components initialized successfully.")
        except Exception as e:
            print(f"Error initializing components: {e}")
            import traceback
            traceback.print_exc()


def open_browser():
    for _ in range(40):         
        try:
            urllib.request.urlopen('http://127.0.0.1:5000', timeout=1)
            webbrowser.open('http://127.0.0.1:5000')
            return
        except Exception:
            time.sleep(0.5)
    webbrowser.open('http://127.0.0.1:5000')



@app.route('/')
def index():
    os_type = platform.system().lower()
    template = 'index_linux.html' if os_type == 'linux' else 'index_windows.html'
    return render_template(template, system_info={
        'os':       platform.system(),
        'hostname': platform.node(),
        'is_admin': is_admin(),
    })


@app.route('/assistant')
def assistant():
    return redirect('/')


@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        init_components()
        result = analyzer.collect_all()
        return jsonify({'success': True, 'collected': result['collected']})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/chat', methods=['POST'])
def chat():
    try:
        init_components()
        query = request.json.get('query', '').strip()
        if not query:
            return jsonify({'success': False, 'response': 'Please enter a query.'})
        result = rag.query(query)
        return jsonify(result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'response': f'Error: {str(e)}'}), 500


@app.route('/report', methods=['POST'])
def report():
    try:
        init_components()
        req           = request.json or {}
        query_data    = req.get('query_data', {})
        filtered_data = req.get('filtered_data', [])
        filename, _   = report_gen.generate(query_data, filtered_data)
        return jsonify({
            'success':      True,
            'filename':     filename,
            'download_url': f'/download/{filename}',
            'items_count':  len(filtered_data),
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500


from flask import send_file, after_this_request

@app.route('/download/<filename>')
def download(filename):
    reports_dir = get_reports_dir()
    filepath = os.path.join(reports_dir, filename)
    if not os.path.exists(filepath):
        return jsonify({'error': f'File not found: {filename}'}), 404
    
    # Force download for HTML reports
    if filename.endswith('.html'):
        return send_file(
            filepath,
            as_attachment=True,
            download_name=filename,
            mimetype='application/octet-stream'   # forces download dialog
        )
    return send_file(filepath, as_attachment=True)

@app.route('/full-report')
def full_report():
    try:
        init_components()
        filename, filepath = report_gen.generate_full()
        return send_file(filepath, as_attachment=True)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/export/json', methods=['GET'])
def export_json():
    try:
        filepath = ie.export_to_json()
        return send_file(filepath, as_attachment=True)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/import', methods=['POST'])
def import_json():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Empty filename'}), 400
    if not file.filename.endswith('.json'):
        return jsonify({'error': 'Only JSON files accepted'}), 400

    os.makedirs('uploads', exist_ok=True)
    temp_path = os.path.join('uploads', file.filename)
    file.save(temp_path)

    try:
        clear_existing = request.args.get('clear', 'false').lower() == 'true'
        ie.import_from_json(temp_path, clear_existing=clear_existing)
        os.remove(temp_path)
        return jsonify({'success': True, 'message': 'Import completed'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500



if __name__ == '__main__':
    print(f"\n{'='*50}")
    print("🔍 FORENSIC ASSISTANT")
    print(f"{'='*50}")
    print(f"OS: {platform.system()} | Admin: {'Yes' if is_admin() else 'No'}")
    print(f"Reports dir: {get_reports_dir()}")
    print(f"{'='*50}")
    print("🌐 Starting server at: http://127.0.0.1:5000")
    print("🚀 Opening browser automatically...")
    print("=" * 50)

    init_components()

    threading.Thread(target=open_browser, daemon=True).start()

    try:
        app.run(debug=False, host='127.0.0.1', port=5000, threaded=True)
    except Exception as e:
        print(f"Server error: {e}")
        input("Press Enter to exit...")