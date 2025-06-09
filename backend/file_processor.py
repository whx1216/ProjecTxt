import os
import mimetypes
import re
import time
import threading
from pathlib import Path
import pygments
from pygments import lexers
from pygments.formatters import HtmlFormatter


class FileInfo:
    """文件信息类，存储文件的基本信息"""

    def __init__(self, path, full_path, is_dir=False):
        self.path = path  # 相对路径
        self.full_path = full_path  # 完整路径
        self.is_dir = is_dir  # 是否是目录
        self.selected = False  # 是否被选择复制到剪贴板
        self.size = 0  # 文件大小
        self.line_count = 0  # 行数
        self.char_count = 0  # 字符数
        self.file_type = ''  # 文件类型
        self.is_cdn = False  # 是否是CDN文件
        self.is_minified = False  # 是否是压缩文件
        self.is_database = False  # 是否是数据库文件
        self.content = ''  # 文件内容
        self.is_text = False  # 是否是文本文件

    def to_dict(self):
        """将对象转换为字典，方便JSON序列化"""
        return {
            'path': self.path,
            'full_path': self.full_path,
            'is_dir': self.is_dir,
            'selected': self.selected,
            'size': self.size,
            'line_count': self.line_count,
            'char_count': self.char_count,
            'file_type': self.file_type,
            'is_cdn': self.is_cdn,
            'is_minified': self.is_minified,
            'is_database': self.is_database,
            'content': self.content if len(self.content) < 100000 else self.content[:100000] + '... (内容过长已截断)',
            'is_text': self.is_text
        }


class FileProcessor:
    """处理文件结构的主要类"""

    def __init__(self):
        self.stop_flag = False
        self.files_list = []
        self.current_count = 0
        self.total_files = 0
        mimetypes.init()
        self.text_extensions = {
            '.py', '.js', '.html', '.css', '.php', '.json', '.xml', '.txt', '.md',
            '.csv', '.java', '.kt', '.c', '.cpp', '.h', '.hpp', '.ts', '.jsx',
            '.tsx', '.yml', '.yaml', '.toml', '.ini', '.cfg', '.conf', '.sh',
            '.bat', '.ps1', '.sql', '.go', '.rb', '.rs', '.dart', '.swift', '.wxss', '.wxml'
        }

    def process_directory(self, folder_path, callback=None):
        """
        处理目录
        folder_path: 要处理的文件夹路径
        callback: 回调函数，用于更新进度
        """
        self.stop_flag = False
        self.files_list = []
        self.current_count = 0

        # 创建线程处理文件
        thread = threading.Thread(target=self._process_directory_thread,
                                  args=(folder_path, callback))
        thread.daemon = True
        thread.start()
        return thread

    def stop_processing(self):
        """停止处理"""
        self.stop_flag = True

    def _process_directory_thread(self, folder_path, callback):
        """线程函数，处理目录"""
        try:
            # 先计算总文件数
            self.total_files = 0
            for root, _, files in os.walk(folder_path):
                self.total_files += len(files)
                if self.stop_flag:
                    if callback:
                        callback('stopped', 0, 0, None)
                    return

            # 获取结构和文件内容
            self._process_directory(folder_path, "", callback)

            # 检查是否停止线程
            if self.stop_flag:
                if callback:
                    callback('stopped', 0, 0, None)
                return

            # 返回结果
            if callback:
                result_list = [file_info.to_dict() for file_info in self.files_list]
                callback('finished', self.current_count, self.total_files, result_list)

        except Exception as e:
            if callback:
                callback('error', 0, 0, str(e))

    def _process_directory(self, full_path, rel_path, callback):
        """处理目录及其文件"""
        try:
            items = os.listdir(full_path)
        except PermissionError:
            return

        # 检查是否停止线程
        if self.stop_flag:
            return

        # 先处理目录
        dirs = sorted([item for item in items if os.path.isdir(os.path.join(full_path, item))])
        for dir_name in dirs:
            if dir_name.startswith('.'):  # 跳过隐藏目录
                continue

            # 检查是否停止线程
            if self.stop_flag:
                return

            dir_path = os.path.join(full_path, dir_name)
            dir_rel_path = os.path.join(rel_path, dir_name).replace('\\', '/')

            # 创建目录信息对象
            dir_info = FileInfo(dir_rel_path, dir_path, is_dir=True)
            self.files_list.append(dir_info)

            # 递归处理子目录
            self._process_directory(dir_path, dir_rel_path, callback)

        # 再处理文件
        files = sorted([item for item in items if os.path.isfile(os.path.join(full_path, item))])
        for file_name in files:
            if file_name.startswith('.'):  # 跳过隐藏文件
                continue

            # 检查是否停止线程
            if self.stop_flag:
                return

            file_path = os.path.join(full_path, file_name)
            file_rel_path = os.path.join(rel_path, file_name).replace('\\', '/')

            # 处理文件
            self._process_file(file_path, file_rel_path, callback)

    def _process_file(self, file_path, file_rel_path, callback):
        """处理单个文件"""
        # 创建文件信息对象
        file_info = FileInfo(file_rel_path, file_path)
        file_info.size = os.path.getsize(file_path)
        file_info.file_type = os.path.splitext(file_path)[1][1:] if os.path.splitext(file_path)[1] else 'txt'

        # 检查是否为文本文件
        mime_type, _ = mimetypes.guess_type(file_path)
        is_text = (mime_type and mime_type.startswith('text')) or file_path.lower().endswith(
            tuple(self.text_extensions))
        file_info.is_text = is_text

        if is_text:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    file_info.content = content
                    file_info.line_count = content.count('\n') + 1
                    file_info.char_count = len(content)

                    # 检查是否是CDN或压缩JS文件
                    file_info.is_cdn = bool(re.search(r'(cdn|unpkg|jsdelivr|cloudflare)', file_rel_path.lower()))
                    file_info.is_minified = file_path.lower().endswith('.min.js') or (
                            len(content) > 1000 and '.' in file_path and
                            content.count('\n') < content.count(';') / 10
                    )

                    # 检查是否是数据库文件 (JSON等大文件)
                    file_info.is_database = (
                                                    file_path.lower().endswith('.json') and len(content) > 50000
                                            ) or file_path.lower().endswith(('.db', '.sqlite', '.sqlite3'))
            except Exception as e:
                file_info.content = f"无法读取文件内容: {str(e)}"
                file_info.is_text = False

        # 将文件信息添加到列表
        self.files_list.append(file_info)

        # 更新进度
        self.current_count += 1
        if callback:
            callback('progress', self.current_count, self.total_files, file_info.to_dict())

    def highlight_code(self, content, filename):
        """高亮显示代码"""
        try:
            # 获取文件扩展名
            file_ext = os.path.splitext(filename)[1].lower()

            # 处理WXML和WXSS文件的特殊情况
            if file_ext == '.wxml':
                # WXML类似于HTML，使用HTML词法分析器
                lexer = lexers.get_lexer_by_name('html', stripall=False)
            elif file_ext == '.wxss':
                # WXSS类似于CSS，使用CSS词法分析器
                lexer = lexers.get_lexer_by_name('css', stripall=False)
            else:
                # 其他文件类型，尝试根据文件扩展名获取合适的词法分析器
                try:
                    lexer = lexers.get_lexer_for_filename(filename, stripall=False)
                except pygments.util.ClassNotFound:
                    # 如果找不到匹配的词法分析器，尝试根据文件类型获取
                    try:
                        file_type = file_ext[1:] if file_ext else 'txt'
                        if file_type and file_type != 'txt':
                            lexer = lexers.get_lexer_by_name(file_type, stripall=False)
                        else:
                            lexer = lexers.get_lexer_by_name('text', stripall=False)
                    except pygments.util.ClassNotFound:
                        lexer = lexers.get_lexer_by_name('text', stripall=False)

        except pygments.util.ClassNotFound:
            # 如果所有尝试都失败，使用文本词法分析器
            lexer = lexers.get_lexer_by_name('text', stripall=False)

        # 使用IDE风格的格式化器，并设置行号
        formatter = HtmlFormatter(
            style='monokai',
            linenos='table',
            linenostart=1,
            linespans='line',
            cssclass='code-highlight',
            full=False
        )

        # 生成高亮代码
        highlighted_code = pygments.highlight(content, lexer, formatter)

        # CSS样式
        css = formatter.get_style_defs('.code-highlight')

        return {
            'highlighted_code': highlighted_code,
            'css': css
        }

    def restore_project_from_text(self, text_content, target_folder, callback=None):
        """
        从文本内容还原项目结构
        text_content: 文本内容(包含结构和可能的文件内容)
        target_folder: 目标文件夹
        callback: 回调函数，用于更新进度
        """
        # 解析文本内容，分离结构信息和文件内容
        files_data = self._parse_project_text(text_content)

        # 统计要处理的项目数
        total_items = len(files_data)
        if total_items == 0:
            return {
                'status': 'error',
                'message': '无法从文本内容中解析项目结构'
            }

        processed = 0
        missing_content = []

        # 确定项目根目录名称
        project_root = None
        for file_info in files_data:
            if file_info['is_dir']:
                parts = file_info['path'].split('/')
                if len(parts) == 1:  # 只有一级，可能是根目录
                    project_root = parts[0]
                    break

        if not project_root:
            # 如果没找到根目录，使用默认名
            project_root = "restored_project"

        # 创建项目根目录
        project_folder = os.path.join(target_folder, project_root)
        if not os.path.exists(project_folder):
            os.makedirs(project_folder)

        # 处理所有文件和目录
        for file_info in files_data:
            path = file_info['path']
            is_dir = file_info['is_dir']

            # 计算相对于项目根目录的路径
            rel_path = path
            if path.startswith(project_root + '/'):
                rel_path = path[len(project_root) + 1:]
            elif path == project_root:
                rel_path = ""

            file_path = os.path.join(project_folder, rel_path)

            # 处理目录
            if is_dir:
                if not os.path.exists(file_path) and rel_path:  # 跳过根目录(已创建)
                    os.makedirs(file_path)
            # 处理文件
            else:
                # 检查文件是否已存在
                if os.path.exists(file_path):
                    missing_content.append(f"跳过已存在的文件: {path}")
                else:
                    # 确保父目录存在
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)

                    # 检查是否有内容
                    content = file_info.get('content', '')
                    if not content:
                        missing_content.append(path)
                        # 创建空文件
                        with open(file_path, 'w', encoding='utf-8') as f:
                            pass
                    else:
                        # 写入内容到文件
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(content)

            processed += 1
            if callback:
                progress = int((processed / total_items) * 100)
                callback('progress', processed, total_items, progress, None)

        # 处理完成
        return {
            'status': 'success',
            'total': total_items,
            'processed': processed,
            'missing_content': missing_content
        }

    def _parse_project_text(self, text_content):
        """
        解析项目文本，提取结构和文件内容
        text_content: 项目文本
        返回: 文件数据列表
        """
        files_data = []
        lines = text_content.split('\n')

        # 检查是否包含文件结构和文件内容
        structure_section = True
        file_content_section = False
        current_file = None
        current_content = []

        # 用于解析文件夹和文件
        folder_path_stack = []
        base_folder = None
        project_name = None

        # 处理每一行
        for line in lines:
            # 空行处理
            if not line.strip():
                if file_content_section and current_file:
                    current_content.append('')  # 保留空行
                continue

            # 检测文件内容部分
            if line.startswith('文件内容:'):
                structure_section = False
                file_content_section = True
                continue

            # 处理结构部分
            if structure_section:
                # 跳过标题行
                if line.startswith('文件结构:'):
                    continue

                # 处理根目录行 - 从路径中提取项目名称
                if not any(c in line for c in ['├', '└', '│', '─']) and ('/' in line or '\\' in line):
                    # 提取项目名称 (最后一个斜杠前的部分)
                    path = line.strip()

                    if path.endswith('/') or path.endswith('\\'):
                        path = path[:-1]

                    # 从路径中提取项目名称
                    if '/' in path:
                        project_name = path.split('/')[-1]
                    elif '\\' in path:
                        project_name = path.split('\\')[-1]
                    else:
                        project_name = path

                    # 设置基础文件夹
                    base_folder = project_name
                    folder_path_stack = [base_folder]

                    # 添加根目录到文件列表
                    files_data.append({
                        'path': base_folder,
                        'is_dir': True,
                        'content': ''
                    })
                    continue

                # 处理树形结构行
                if '├──' in line or '└──' in line:
                    indent = line.find('├') if '├' in line else line.find('└')
                    name = line.split('──')[-1].strip()
                    is_dir = name.endswith('/')

                    # 清除行数信息 (xx行)
                    if not is_dir and '(' in name and ')' in name:
                        parts = name.split('(')
                        if parts[-1].endswith(')'):
                            name = parts[0].strip()

                    if is_dir:
                        name = name.rstrip('/')

                    # 计算当前级别 (基于缩进)
                    level = indent // 4 + 1  # +1 因为根级别已经有项目名称

                    # 调整路径栈以匹配当前级别
                    if level < len(folder_path_stack):
                        folder_path_stack = folder_path_stack[:level]

                    # 构建路径
                    if is_dir:
                        folder_path_stack = folder_path_stack[:level]
                        folder_path_stack.append(name)
                        current_path = '/'.join(folder_path_stack)
                    else:
                        parent_path = '/'.join(folder_path_stack)
                        current_path = f"{parent_path}/{name}"

                    # 添加到文件数据
                    path_to_add = current_path
                    files_data.append({
                        'path': path_to_add,
                        'is_dir': is_dir,
                        'content': ''
                    })

                continue

            # 处理文件内容部分
            if file_content_section:
                # 检测文件内容的开始
                if line.startswith('---') and (line.endswith('---') or ' ---' in line):
                    # 保存之前文件的内容
                    if current_file:
                        file_path_parts = current_file.split('/')
                        if file_path_parts[0] != base_folder and base_folder:
                            file_path = f"{base_folder}/{current_file}"
                        else:
                            file_path = current_file

                        existing_file = next((f for f in files_data if
                                              not f['is_dir'] and f['path'].endswith('/' + file_path.split('/')[-1])),
                                             None)
                        if existing_file:
                            existing_file['content'] = '\n'.join(current_content)

                    # 提取新文件的路径
                    file_header = line.strip('-').strip()
                    path_part = file_header.split('(')[0].strip() if '(' in file_header else file_header
                    current_file = path_part
                    current_content = []
                elif current_file:
                    current_content.append(line)

        # 保存最后一个文件的内容
        if current_file and file_content_section:
            file_path_parts = current_file.split('/')
            if file_path_parts[0] != base_folder and base_folder:
                file_path = f"{base_folder}/{current_file}"
            else:
                file_path = current_file

            existing_file = next(
                (f for f in files_data if not f['is_dir'] and f['path'].endswith('/' + file_path.split('/')[-1])), None)
            if existing_file:
                existing_file['content'] = '\n'.join(current_content)

        return files_data