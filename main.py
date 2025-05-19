import os
import sys
import webview
import logging
import json
from backend.file_processor import FileProcessor

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# File processor instance
processor = FileProcessor()
current_window = None
history = []
current_folder = ""


# API Functions - these will be exposed to JavaScript
def get_history():
    """Return the history list"""
    global history
    try:
        load_history()
        return history
    except Exception as e:
        logger.error(f"Error getting history: {e}")
        return []


def load_history():
    """Load history from file"""
    global history
    try:
        if os.path.exists('history.json'):
            with open('history.json', 'r', encoding='utf-8') as f:
                history = json.load(f)
        else:
            history = []
    except Exception as e:
        logger.error(f"Failed to load history: {e}")
        history = []


def save_history():
    """Save history to file"""
    global history
    try:
        # Keep only the latest 10 records
        history = history[:10]
        with open('history.json', 'w', encoding='utf-8') as f:
            json.dump(history, f)
    except Exception as e:
        logger.error(f"Failed to save history: {e}")


def add_to_history(folder_path):
    """Add a path to history"""
    global history
    if folder_path in history:
        history.remove(folder_path)
    history.insert(0, folder_path)
    save_history()
    return True


def clear_history():
    """Clear history"""
    global history
    history = []
    save_history()
    return True


def browse_folder():
    """Browse for folder"""
    try:
        result = webview.windows[0].create_file_dialog(
            webview.FOLDER_DIALOG
        )
        if result and len(result) > 0:
            folder_path = result[0]
            add_to_history(folder_path)
            return folder_path
        return None
    except Exception as e:
        logger.error(f"Error browsing folder: {e}")
        return None


def process_folder(folder_path):
    """Process folder"""
    global current_folder, processor

    if not folder_path or not os.path.isdir(folder_path):
        return {'status': 'error', 'message': '无效的文件夹路径'}

    current_folder = folder_path
    add_to_history(folder_path)

    # Start processing
    def callback(status, current, total, data):
        """Callback function to update progress and results"""
        if status == 'progress':
            progress = int((current / total) * 100) if total > 0 else 0
            current_window.evaluate_js(f'window.app.updateProgress({current}, {total}, {progress})')
        elif status == 'finished':
            current_window.evaluate_js(f'window.app.processComplete({json.dumps(data)})')
        elif status == 'error':
            current_window.evaluate_js(f'window.app.processError("{data}")')
        elif status == 'stopped':
            current_window.evaluate_js('window.app.processStopped()')

    # Start processing
    processor.process_directory(folder_path, callback)
    return {'status': 'processing', 'folder': folder_path}


def stop_processing():
    """Stop processing"""
    global processor
    processor.stop_processing()
    return {'status': 'stopping'}


def highlight_code(content, filename):
    """Highlight code"""
    global processor
    return processor.highlight_code(content, filename)


def get_file_content(file_path):
    """Get file content"""
    global processor
    try:
        if not os.path.isfile(file_path):
            return {'status': 'error', 'message': '文件不存在'}

        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # Create file info
        file_info = {
            'path': os.path.basename(file_path),
            'full_path': file_path,
            'size': os.path.getsize(file_path),
            'content': content,
            'line_count': content.count('\n') + 1,
            'char_count': len(content),
            'is_dir': False
        }

        # Highlight code
        highlight_result = processor.highlight_code(content, file_path)

        return {
            'status': 'success',
            'file_info': file_info,
            'highlighted_code': highlight_result['highlighted_code'],
            'css': highlight_result['css']
        }
    except Exception as e:
        logger.error(f"Error getting file content: {e}")
        return {'status': 'error', 'message': str(e)}


def restore_project_from_text(text_content, target_folder):
    """Restore project from text content to target folder"""
    global processor

    if not target_folder or not os.path.isdir(target_folder):
        return {'status': 'error', 'message': '无效的目标文件夹路径'}

    # Start processing
    def callback(status, current, total, progress, data):
        """Callback function to update progress"""
        if status == 'progress':
            current_window.evaluate_js(f'window.app.updateRestoreProgress({current}, {total}, {progress})')

    # Restore project
    result = processor.restore_project_from_text(text_content, target_folder, callback)
    current_window.evaluate_js(f'window.app.restoreComplete({json.dumps(result)})')
    return {'status': 'processing', 'target': target_folder}


def main():
    global current_window

    # Get the directory of the current script to locate frontend files
    base_dir = os.path.dirname(os.path.abspath(__file__))
    frontend_dir = os.path.join(base_dir, 'frontend')

    # Set app attributes
    title = "ProjecTxt"
    width, height = 1200, 800

    # Create window with direct function references
    current_window = webview.create_window(
        title=title,
        url=os.path.join(frontend_dir, 'index.html'),
        width=width,
        height=height,
        min_size=(800, 600),
        text_select=True,
    )

    # Expose individual API functions
    current_window.expose(
        get_history,
        load_history,
        add_to_history,
        clear_history,
        browse_folder,
        process_folder,
        stop_processing,
        highlight_code,
        get_file_content,
        restore_project_from_text  # 更新API名称
    )

    # Start the application - debug=True helps with troubleshooting
    webview.start(debug=False)


if __name__ == "__main__":
    main()