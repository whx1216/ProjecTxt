import os
import sys
import mimetypes
import time
import re
from pathlib import Path
import pygments
from pygments import lexers
from pygments.formatters import HtmlFormatter
import json

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QLabel, QLineEdit, QPushButton, QTreeView, QTreeWidget, QTreeWidgetItem,
                               QTextEdit, QTextBrowser, QFileDialog, QSplitter, QFrame,
                               QStatusBar, QScrollArea, QToolBar, QComboBox,
                               QCheckBox, QProgressBar, QMenu, QMessageBox,
                               QTabWidget, QDialog, QListWidget, QToolButton,
                               QHeaderView, QGroupBox, QStyle, QSizePolicy)
from PySide6.QtCore import Qt, QSize, Signal, QThread, QSettings, QTimer, QUrl, QModelIndex
from PySide6.QtGui import QFont, QColor, QIcon, QPixmap, QAction, QDesktopServices, QStandardItemModel, QStandardItem, \
    QBrush


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


class WorkerThread(QThread):
    """后台处理文件的线程"""

    progress_signal = Signal(int, int)  # 当前处理的文件数，总文件数
    file_signal = Signal(FileInfo)  # 每处理完一个文件发送信号
    finished_signal = Signal(list)  # 文件结构列表
    error_signal = Signal(str)  # 错误消息

    def __init__(self, folder_path):
        super().__init__()
        self.folder_path = folder_path
        self.files_list = []
        self.stop_flag = False

    def run(self):
        try:
            # 先计算总文件数
            total_files = 0
            for root, _, files in os.walk(self.folder_path):
                total_files += len(files)
                if self.stop_flag:
                    return

            # 设置文件类型
            self._set_mime_types()

            # 获取结构和文件内容
            self._process_directory(self.folder_path, "", total_files)

            # 检查是否停止线程
            if self.stop_flag:
                return

            # 发送完成信号
            self.finished_signal.emit(self.files_list)
        except Exception as e:
            self.error_signal.emit(str(e))

    def stop(self):
        """停止线程处理"""
        self.stop_flag = True

    def _set_mime_types(self):
        """初始化MIME类型"""
        mimetypes.init()
        # 添加一些常见的文本文件扩展名
        self.text_extensions = {
            '.py', '.js', '.html', '.css', '.php', '.json', '.xml', '.txt', '.md',
            '.csv', '.java', '.kt', '.c', '.cpp', '.h', '.hpp', '.ts', '.jsx',
            '.tsx', '.yml', '.yaml', '.toml', '.ini', '.cfg', '.conf', '.sh',
            '.bat', '.ps1', '.sql', '.go', '.rb', '.rs', '.dart', '.swift'
        }

    def _process_directory(self, full_path, rel_path, total_files):
        """处理目录及其文件"""
        current_count = 0

        try:
            items = os.listdir(full_path)
        except PermissionError:
            return current_count

        # 检查是否停止线程
        if self.stop_flag:
            return current_count

        # 先处理目录
        dirs = sorted([item for item in items if os.path.isdir(os.path.join(full_path, item))])
        for dir_name in dirs:
            if dir_name.startswith('.'):  # 跳过隐藏目录
                continue

            # 检查是否停止线程
            if self.stop_flag:
                return current_count

            dir_path = os.path.join(full_path, dir_name)
            dir_rel_path = os.path.join(rel_path, dir_name).replace('\\', '/')

            # 创建目录信息对象
            dir_info = FileInfo(dir_rel_path, dir_path, is_dir=True)
            self.files_list.append(dir_info)

            # 递归处理子目录
            current_count += self._process_directory(dir_path, dir_rel_path, total_files)

        # 再处理文件
        files = sorted([item for item in items if os.path.isfile(os.path.join(full_path, item))])
        for file_name in files:
            if file_name.startswith('.'):  # 跳过隐藏文件
                continue

            # 检查是否停止线程
            if self.stop_flag:
                return current_count

            file_path = os.path.join(full_path, file_name)
            file_rel_path = os.path.join(rel_path, file_name).replace('\\', '/')

            # 处理文件
            current_count += self._process_file(file_path, file_rel_path, current_count, total_files)

        return current_count

    def _process_file(self, file_path, file_rel_path, current_count, total_files):
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

        # 发送文件信号
        self.file_signal.emit(file_info)

        # 更新进度
        current_count += 1
        self.progress_signal.emit(current_count, total_files)

        return 1  # 返回处理的文件数


class FileTreeWidget(QTreeWidget):
    """自定义的文件树组件，支持文件选择和颜色标记"""

    selection_changed = Signal()  # 选择变更信号
    file_clicked = Signal(FileInfo)  # 文件点击信号，用于预览

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderLabels(["名称", "类型", "大小", "行数", "字符数"])

        # 设置表头对齐方式 - 将后面几列设为靠右对齐
        for i in range(1, 5):
            self.headerItem().setTextAlignment(i, Qt.AlignRight)

        # 名称列尽可能占用更多空间
        self.header().setSectionResizeMode(0, QHeaderView.Stretch)

        # 其他列根据内容调整宽度
        for i in range(1, 5):
            self.header().setSectionResizeMode(i, QHeaderView.ResizeToContents)

        self.header().setStretchLastSection(False)
        self.setSelectionMode(QTreeWidget.ExtendedSelection)
        self.setAlternatingRowColors(True)
        self.setStyleSheet("""
            QTreeWidget {
                background-color: #2b2b2b;
                alternate-background-color: #2f2f2f;
                color: #a9b7c6;
                border: 1px solid #323232;
            }
            QTreeWidget::item {
                padding: 4px 0;
                border-bottom: 1px solid #333;
            }
            QTreeWidget::item:selected {
                background-color: #365880;  /* 使用更暗的蓝色 */
                color: white;  /* 确保文字在选中状态下清晰可见 */
            }
            QTreeWidget::item:hover {

                background-color: #2f496a;
            }
        """)

        # 右键菜单
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

        # 文件图标
        self.file_icons = {}

        # 连接信号
        self.itemClicked.connect(self.on_item_clicked)
        self.itemDoubleClicked.connect(self.on_item_double_clicked)

    def on_item_clicked(self, item, column):
        """处理项目点击事件"""
        file_info = item.data(0, Qt.UserRole)
        if not file_info:
            return

        if column == 0:  # 只在点击名称列时处理
            if file_info.is_dir:
                # 如果是目录，则不做选择标记处理
                pass
            else:
                # 如果是文件，则切换选择状态
                file_info.selected = not file_info.selected
                self.update_item_color(item, file_info)
                self.selection_changed.emit()

                # 添加状态栏反馈
                main_window = self.window()
                if hasattr(main_window, 'status_bar'):
                    if file_info.selected:
                        main_window.status_bar.showMessage(f"已选择: {file_info.path}", 2000)
                    else:
                        main_window.status_bar.showMessage(f"已取消选择: {file_info.path}", 2000)

            # 发送文件点击信号，用于预览
            if not file_info.is_dir:
                self.file_clicked.emit(file_info)

    def on_item_double_clicked(self, item, column):
        """处理项目双击事件"""
        file_info = item.data(0, Qt.UserRole)
        if file_info and file_info.is_dir:
            # 双击目录时切换展开/折叠状态
            item.setExpanded(not item.isExpanded())

    def update_item_color(self, item, file_info):
        """根据文件状态更新项目颜色和图标"""
        # 确保选中状态清晰可见
        if file_info.selected:
            # 使用绿色背景并添加选中标记
            item.setBackground(0, QBrush(QColor("#0F3D14")))
            item.setText(0, "✓ " + item.text(0).replace("✓ ", ""))

            # 确保其他列也应用相同的背景色
            for i in range(1, 5):
                item.setBackground(i, QBrush(QColor("#0F3D14")))
        else:
            # 根据文件类型设置颜色
            item.setText(0, item.text(0).replace("✓ ", ""))
            item.setBackground(0, QBrush(Qt.transparent))

            # 清除其他列的背景
            for i in range(1, 5):
                item.setBackground(i, QBrush(Qt.transparent))

            if file_info.is_cdn:
                item.setForeground(0, QBrush(QColor("#7b68ee")))  # 紫色表示CDN
            elif file_info.is_minified:
                item.setForeground(0, QBrush(QColor("#ff6b6b")))  # 红色表示压缩文件
            elif file_info.is_database:
                item.setForeground(0, QBrush(QColor("#FFA500")))  # 橙色表示数据库文件
            else:
                item.setForeground(0, QBrush(QColor("#a9b7c6")))  # 默认颜色

    def get_file_icon(self, file_type):
        """获取文件类型对应的图标"""
        if file_type in self.file_icons:
            return self.file_icons[file_type]

        # 根据文件类型设置颜色
        file_type_colors = {
            'py': "#FFDD33",  # 黄色
            'js': "#F7DF1E",  # 黄色
            'html': "#E34C26",  # 红色
            'css': "#563D7C",  # 紫色
            'php': "#777BB3",  # 紫色
            'java': "#B07219",  # 棕色
            'c': "#555555",  # 深灰色
            'cpp': "#F34B7D",  # 红色
            'go': "#00ADD8",  # 青色
            'rb': "#CC342D",  # 红色
            'rs': "#DEA584",  # 橙色
            'ts': "#2B7489",  # 青色
            'sql': "#e38c00",  # 橙色
            'json': "#40a9ff",  # 蓝色
            'xml': "#e67e22",  # 橙色
            'md': "#2980b9",  # 蓝色
        }

        color = file_type_colors.get(file_type, "#6897BB")  # 默认蓝色

        # 使用内联SVG作为图标
        svg = f"""
        <svg width="16" height="16" viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg">
            <rect x="1" y="1" width="14" height="14" rx="2" fill="#3c3f41" stroke="{color}" stroke-width="1"/>
            <text x="8" y="12" text-anchor="middle" font-size="10" font-family="Arial" fill="{color}">{file_type[:1].upper()}</text>
        </svg>
        """

        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.transparent)

        # 简单起见，这里返回一个空的图标
        icon = QIcon(pixmap)
        self.file_icons[file_type] = icon
        return icon

    def show_context_menu(self, position):
        """显示智能右键菜单"""
        items = self.selectedItems()
        if not items:
            return

        # 创建基本菜单
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #3c3f41;
                color: #a9b7c6;
                border: 1px solid #555555;
                padding: 5px;
            }
            QMenu::item {
                padding: 6px 25px 6px 25px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #365880;
                color: white;
            }
            QMenu::separator {
                height: 1px;
                background-color: #555555;
                margin: 5px 0px;
            }
        """)

        # 检查选中项类型
        has_dir = any(item.data(0, Qt.UserRole) and item.data(0, Qt.UserRole).is_dir for item in items)
        has_file = any(item.data(0, Qt.UserRole) and not item.data(0, Qt.UserRole).is_dir for item in items)
        has_selected = any(item.data(0, Qt.UserRole) and not item.data(0, Qt.UserRole).is_dir and
                           item.data(0, Qt.UserRole).selected for item in items)
        has_unselected = any(item.data(0, Qt.UserRole) and not item.data(0, Qt.UserRole).is_dir and
                             not item.data(0, Qt.UserRole).selected for item in items)

        # 智能添加菜单项
        # 1. 文件选择相关操作 - 只对普通文件显示
        if has_file:
            if has_unselected:
                select_action = menu.addAction("选择用于复制")
                select_action.setIcon(self.style().standardIcon(QStyle.SP_DialogApplyButton))

            if has_selected:
                deselect_action = menu.addAction("取消选择")
                deselect_action.setIcon(self.style().standardIcon(QStyle.SP_DialogCancelButton))

        # 2. 目录特定操作 - 只对目录显示
        if has_dir:
            if menu.actions():
                menu.addSeparator()

            folder_menu = QMenu("文件夹操作", menu)
            folder_menu.setStyleSheet(menu.styleSheet())

            select_folder_action = folder_menu.addAction("选择此文件夹下所有文件")
            deselect_folder_action = folder_menu.addAction("取消选择此文件夹下所有文件")
            folder_menu.addSeparator()

            expand_folder_action = folder_menu.addAction("展开此文件夹")
            collapse_folder_action = folder_menu.addAction("折叠此文件夹")

            menu.addMenu(folder_menu)

        # 3. 特殊文件操作 - 根据文件类型添加
        special_types = []
        if any(item.data(0, Qt.UserRole) and not item.data(0, Qt.UserRole).is_dir
               and item.data(0, Qt.UserRole).is_cdn for item in items):
            special_types.append(("CDN 文件", "#7b68ee"))

        if any(item.data(0, Qt.UserRole) and not item.data(0, Qt.UserRole).is_dir
               and item.data(0, Qt.UserRole).is_minified for item in items):
            special_types.append(("压缩文件", "#ff6b6b"))

        if any(item.data(0, Qt.UserRole) and not item.data(0, Qt.UserRole).is_dir
               and item.data(0, Qt.UserRole).is_database for item in items):
            special_types.append(("数据库文件", "#FFA500"))

        if special_types:
            if menu.actions():
                menu.addSeparator()

            special_menu = QMenu("特殊文件操作", menu)
            special_menu.setStyleSheet(menu.styleSheet())

            for type_name, color in special_types:
                select_action = special_menu.addAction(f"选择所有{type_name}")
                # 设置图标颜色提示
                pixmap = QPixmap(16, 16)
                pixmap.fill(QColor(color))
                select_action.setIcon(QIcon(pixmap))

                special_menu.addSeparator()

            menu.addMenu(special_menu)

        # 4. 展开/折叠操作 - 只在有目录时或多个选择时显示
        if has_dir or len(items) > 1:
            if menu.actions():
                menu.addSeparator()

            if has_dir:
                expand_action = menu.addAction("展开选中项")
                expand_action.setIcon(self.style().standardIcon(QStyle.SP_FileDialogDetailedView))

                collapse_action = menu.addAction("折叠选中项")
                collapse_action.setIcon(self.style().standardIcon(QStyle.SP_FileDialogListView))

        # 显示菜单并处理选择
        action = menu.exec(self.viewport().mapToGlobal(position))

        # 根据用户选择执行相应操作
        if not action:
            return

        # 处理文件选择操作
        if has_file and has_unselected and action == select_action:
            self.select_items(items, True)
        elif has_file and has_selected and action == deselect_action:
            self.select_items(items, False)

        # 处理目录操作
        elif has_dir and action == select_folder_action:
            self.select_folder_items(items, True)
        elif has_dir and action == deselect_folder_action:
            self.select_folder_items(items, False)
        elif has_dir and action == expand_folder_action:
            for item in items:
                if item.data(0, Qt.UserRole) and item.data(0, Qt.UserRole).is_dir:
                    item.setExpanded(True)
        elif has_dir and action == collapse_folder_action:
            for item in items:
                if item.data(0, Qt.UserRole) and item.data(0, Qt.UserRole).is_dir:
                    item.setExpanded(False)

        # 处理展开/折叠操作
        elif has_dir and action == expand_action:
            for item in items:
                item.setExpanded(True)
        elif has_dir and action == collapse_action:
            for item in items:
                item.setExpanded(False)

        # 处理特殊文件操作
        elif special_types and action.parent() and action.parent().title() == "特殊文件操作":
            action_text = action.text()
            if "选择所有CDN 文件" in action_text:
                self.select_by_condition(lambda file_info: file_info.is_cdn)
            elif "选择所有压缩文件" in action_text:
                self.select_by_condition(lambda file_info: file_info.is_minified)
            elif "选择所有数据库文件" in action_text:
                self.select_by_condition(lambda file_info: file_info.is_database)

    def select_folder_items(self, items, selected=True):
        """选择或取消选择文件夹下的所有文件"""
        count = 0
        for item in items:
            file_info = item.data(0, Qt.UserRole)
            if file_info and file_info.is_dir:
                # 处理文件夹，递归选择所有子文件
                count += self._select_children_recursive(item, selected)
            elif file_info:
                # 单个文件的处理，复用现有逻辑
                file_info.selected = selected
                self.update_item_color(item, file_info)
                count += 1

        # 添加操作反馈
        main_window = self.window()
        if hasattr(main_window, 'status_bar'):
            if selected:
                main_window.status_bar.showMessage(f"已选择 {count} 个文件", 2000)
            else:
                main_window.status_bar.showMessage(f"已取消选择 {count} 个文件", 2000)

        self.selection_changed.emit()

    def _select_children_recursive(self, item, selected=True):
        """递归选择文件夹下的所有子文件"""
        count = 0
        for i in range(item.childCount()):
            child = item.child(i)
            file_info = child.data(0, Qt.UserRole)

            if file_info:
                if file_info.is_dir:
                    # 递归处理子文件夹
                    count += self._select_children_recursive(child, selected)
                else:
                    # 处理文件
                    file_info.selected = selected
                    self.update_item_color(child, file_info)
                    count += 1

        return count

    def select_items(self, items, selected=True):
        """选择或取消选择项目"""
        count = 0
        for item in items:
            file_info = item.data(0, Qt.UserRole)
            if file_info and not file_info.is_dir:
                file_info.selected = selected
                self.update_item_color(item, file_info)
                count += 1

        # 添加操作反馈
        main_window = self.window()
        if hasattr(main_window, 'status_bar'):
            if selected:
                main_window.status_bar.showMessage(f"已选择 {count} 个文件", 2000)
            else:
                main_window.status_bar.showMessage(f"已取消选择 {count} 个文件", 2000)

        self.selection_changed.emit()

    def get_selected_files(self):
        """获取所有选定的文件"""
        selected_files = []

        root = self.invisibleRootItem()
        self._get_selected_recursive(root, selected_files)

        return selected_files

    def _get_selected_recursive(self, item, selected_files):
        """递归获取所有选定的文件"""
        for i in range(item.childCount()):
            child = item.child(i)
            file_info = child.data(0, Qt.UserRole)

            if file_info:
                if not file_info.is_dir and file_info.selected:
                    selected_files.append(file_info)

            self._get_selected_recursive(child, selected_files)

    def select_by_condition(self, condition_func):
        """根据条件选择文件"""
        root = self.invisibleRootItem()
        count = self._select_by_condition_recursive(root, condition_func)

        # 添加操作反馈
        if count > 0:
            main_window = self.window()
            if hasattr(main_window, 'status_bar'):
                main_window.status_bar.showMessage(f"已选择 {count} 个文件", 2000)

        self.selection_changed.emit()
        return count

    def _select_by_condition_recursive(self, item, condition_func):
        """递归根据条件选择文件"""
        count = 0

        for i in range(item.childCount()):
            child = item.child(i)
            file_info = child.data(0, Qt.UserRole)

            if file_info and not file_info.is_dir:
                if condition_func(file_info):
                    file_info.selected = True
                    self.update_item_color(child, file_info)
                    count += 1

            count += self._select_by_condition_recursive(child, condition_func)

        return count


class CodeDisplayWidget(QWidget):
    """用于显示带有行号的代码文件的自定义组件"""

    def __init__(self, file_info, parent=None):
        super().__init__(parent)
        self.file_info = file_info
        self.setup_ui()
        self.highlight_code()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 文件标题区域
        header_container = QWidget()
        header_layout = QHBoxLayout(header_container)
        header_layout.setContentsMargins(8, 8, 8, 8)
        header_layout.setSpacing(8)

        # 文件图标（基于文件类型）
        self.file_icon = QLabel()
        self.file_icon.setFixedSize(16, 16)

        # 文件标题
        self.header = QLabel(self.file_info.path)
        self.header.setStyleSheet("""
                    font-weight: bold;
                    color: #ffc66d;
                """)

        # 文件信息标签
        info_label = QLabel(f"({self.file_info.line_count}行, {self.file_info.char_count}字符)")
        info_label.setStyleSheet("color: #888888; font-size: 12px;")

        # 添加CDN或压缩标识
        self.file_tags = QWidget()
        file_tags_layout = QHBoxLayout(self.file_tags)
        file_tags_layout.setContentsMargins(0, 0, 0, 0)
        file_tags_layout.setSpacing(5)

        if self.file_info.is_cdn:
            cdn_tag = QLabel("CDN")
            cdn_tag.setStyleSheet("""
                                background-color: #7b68ee;
                                color: white;
                                border-radius: 3px;
                                padding: 2px 4px;
                                font-size: 10px;
                            """)
            file_tags_layout.addWidget(cdn_tag)

        if self.file_info.is_minified:
            min_tag = QLabel("压缩")
            min_tag.setStyleSheet("""
                                background-color: #ff6b6b;
                                color: white;
                                border-radius: 3px;
                                padding: 2px 4px;
                                font-size: 10px;
                            """)
            file_tags_layout.addWidget(min_tag)

        if self.file_info.is_database:
            db_tag = QLabel("数据库")
            db_tag.setStyleSheet("""
                                background-color: #FFA500;
                                color: white;
                                border-radius: 3px;
                                padding: 2px 4px;
                                font-size: 10px;
                            """)
            file_tags_layout.addWidget(db_tag)

        # 复制按钮
        self.copy_btn = QPushButton("复制")
        self.copy_btn.setFixedWidth(50)
        self.copy_btn.setStyleSheet("""
                            QPushButton {
                                background-color: transparent;
                                color: #a9b7c6;
                                border: 1px solid #555555;
                                border-radius: 2px;
                                padding: 2px;
                                font-size: 11px;
                            }
                            QPushButton:hover {
                                background-color: #3c4043;
                            }
                        """)

        header_layout.addWidget(self.file_icon)
        header_layout.addWidget(self.header, 1)
        header_layout.addWidget(info_label)
        header_layout.addWidget(self.file_tags)
        header_layout.addWidget(self.copy_btn)

        header_container.setStyleSheet("""
                            background-color: #313335;
                            border-top-left-radius: 4px;
                            border-top-right-radius: 4px;
                        """)

        # 代码显示区域
        self.code_container = QWidget()
        code_layout = QVBoxLayout(self.code_container)
        code_layout.setContentsMargins(0, 0, 0, 0)
        code_layout.setSpacing(0)

        self.code_browser = QTextBrowser()
        self.code_browser.setOpenExternalLinks(False)
        self.code_browser.setStyleSheet("""
                            QTextBrowser {
                                border: 1px solid #323232;
                                border-top: none;
                                border-bottom-left-radius: 4px;
                                border-bottom-right-radius: 4px;
                                background-color: #2b2b2b;
                                color: #a9b7c6;
                                selection-background-color: #214283;
                                padding: 2px;
                            }
                        """)

        # 设置等宽字体以确保缩进正确
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.Monospace)
        self.code_browser.setFont(font)

        code_layout.addWidget(self.code_browser)

        layout.addWidget(header_container)
        layout.addWidget(self.code_container)

        # 连接信号
        self.copy_btn.clicked.connect(self.copy_content)

    def highlight_code(self):
        """高亮显示代码"""
        try:
            # 尝试根据文件扩展名获取合适的词法分析器
            lexer = lexers.get_lexer_for_filename(self.file_info.path, stripall=False)
        except pygments.util.ClassNotFound:
            # 如果找不到匹配的词法分析器，尝试根据文件类型获取
            try:
                if self.file_info.file_type and self.file_info.file_type != 'txt':
                    lexer = lexers.get_lexer_by_name(self.file_info.file_type, stripall=False)
                else:
                    lexer = lexers.get_lexer_by_name('text', stripall=False)
            except pygments.util.ClassNotFound:
                lexer = lexers.get_lexer_by_name('text', stripall=False)

        # 使用IDE风格的格式化器，并设置行号
        formatter = HtmlFormatter(
            style='monokai',
            linenos='table',  # 表格样式的行号
            linenostart=1,
            linespans='line',
            cssclass='code-highlight',
            full=False
        )

        # 生成高亮代码
        highlighted_code = pygments.highlight(self.file_info.content, lexer, formatter)

        # 添加CSS样式表
        css = """
                        <style>
                            .code-highlight { font-size: 12px; font-family: Consolas, Monaco, 'Courier New', monospace; }
                            .code-highlight .linenos { 
                                color: #606366; 
                                background-color: #313335; 
                                padding: 0 8px; 
                                border-right: 1px solid #3c3f41;
                                user-select: none;
                                -webkit-user-select: none;
                                text-align: right;
                            }
                            .code-highlight .lineno { 
                                user-select: none;
                                -webkit-user-select: none;
                            }
                            .code-highlight pre { margin: 0; line-height: 140%; }
                            .code-highlight td.code { padding-left: 10px; width: 100%; }
                            .code-highlight { width: 100%; }

                            /* 语法高亮样式增强 */
                            .code-highlight .hll { background-color: #49483e }
                            .code-highlight .c { color: #75715e } /* 注释 */
                            .code-highlight .err { color: #960050; background-color: #1e0010 } /* 错误 */
                            .code-highlight .k { color: #66d9ef } /* 关键字 */
                            .code-highlight .l { color: #ae81ff } /* 字面量 */
                            .code-highlight .n { color: #f8f8f2 } /* 名称 */
                            .code-highlight .o { color: #f92672 } /* 运算符 */
                            .code-highlight .p { color: #f8f8f2 } /* 标点符号 */
                            .code-highlight .cm { color: #75715e } /* 多行注释 */
                            .code-highlight .cp { color: #75715e } /* 预处理器 */
                            .code-highlight .c1 { color: #75715e } /* 单行注释 */
                            .code-highlight .cs { color: #75715e } /* 特殊注释 */
                            .code-highlight .gd { color: #f92672 } /* 常规删除 */
                            .code-highlight .ge { font-style: italic } /* 常规强调 */
                            .code-highlight .gi { color: #a6e22e } /* 常规插入 */
                            .code-highlight .gs { font-weight: bold } /* 常规强调 */
                            .code-highlight .kc { color: #66d9ef } /* 关键字常量 */
                            .code-highlight .kd { color: #66d9ef } /* 关键字声明 */
                            .code-highlight .kn { color: #f92672 } /* 关键字命名空间 */
                            .code-highlight .kp { color: #66d9ef } /* 关键字伪 */
                            .code-highlight .kr { color: #66d9ef } /* 关键字保留字 */
                            .code-highlight .kt { color: #66d9ef } /* 关键字类型 */
                            .code-highlight .ld { color: #e6db74 } /* 字面量日期 */
                            .code-highlight .m { color: #ae81ff } /* 字面量数字 */
                            .code-highlight .s { color: #e6db74 } /* 字面量字符串 */
                            .code-highlight .na { color: #a6e22e } /* 名称属性 */
                            .code-highlight .nb { color: #f8f8f2 } /* 名称内建 */
                            .code-highlight .nc { color: #a6e22e } /* 名称类 */
                            .code-highlight .nd { color: #a6e22e } /* 名称装饰器 */
                            .code-highlight .ni { color: #f8f8f2 } /* 名称实体 */
                            .code-highlight .ne { color: #a6e22e } /* 名称异常 */
                            .code-highlight .nf { color: #a6e22e } /* 名称函数 */
                            .code-highlight .nl { color: #f8f8f2 } /* 名称标签 */
                            .code-highlight .nn { color: #f8f8f2 } /* 名称命名空间 */
                            .code-highlight .nx { color: #a6e22e } /* 名称其他 */
                            .code-highlight .py { color: #f8f8f2 } /* 名称属性 */
                            .code-highlight .nt { color: #f92672 } /* 名称标签 */
                            .code-highlight .nv { color: #f8f8f2 } /* 名称变量 */
                            .code-highlight .ow { color: #f92672 } /* 运算符词 */
                            .code-highlight .w { color: #f8f8f2 } /* 文本空白 */
                            .code-highlight .mf { color: #ae81ff } /* 字面量数字浮点 */
                            .code-highlight .mh { color: #ae81ff } /* 字面量数字十六进制 */
                            .code-highlight .mi { color: #ae81ff } /* 字面量数字整数 */
                            .code-highlight .mo { color: #ae81ff } /* 字面量数字八进制 */
                            .code-highlight .sb { color: #e6db74 } /* 字面量字符串反引号 */
                            .code-highlight .sc { color: #e6db74 } /* 字面量字符串字符 */
                            .code-highlight .sd { color: #e6db74 } /* 字面量字符串文档 */
                            .code-highlight .s2 { color: #e6db74 } /* 字面量字符串双引号 */
                            .code-highlight .se { color: #ae81ff } /* 字面量字符串转义 */
                            .code-highlight .sh { color: #e6db74 } /* 字面量字符串引用符 */
                            .code-highlight .si { color: #e6db74 } /* 字面量字符串插值 */
                            .code-highlight .sx { color: #e6db74 } /* 字面量字符串其他 */
                            .code-highlight .sr { color: #e6db74 } /* 字面量字符串正则表达式 */
                            .code-highlight .s1 { color: #e6db74 } /* 字面量字符串单引号 */
                            .code-highlight .ss { color: #e6db74 } /* 字面量字符串符号 */
                            .code-highlight .bp { color: #f8f8f2 } /* 名称内建伪 */
                            .code-highlight .vc { color: #f8f8f2 } /* 名称变量类 */
                            .code-highlight .vg { color: #f8f8f2 } /* 名称变量全局 */
                            .code-highlight .vi { color: #f8f8f2 } /* 名称变量实例 */
                            .code-highlight .il { color: #ae81ff } /* 字面量数字整数长 */
                        </style>
                        """

        # 设置HTML内容
        self.code_browser.setHtml(css + highlighted_code)

    def copy_content(self):
        """复制当前文件内容到剪贴板"""
        QApplication.clipboard().setText(self.file_info.content)

        # 添加操作反馈
        main_window = self.window()
        if hasattr(main_window, 'status_bar'):
            main_window.status_bar.showMessage(f"已复制 {self.file_info.path} 的内容到剪贴板", 2000)


class FileContentDisplay(QScrollArea):
    """用于显示文件内容的滚动区域"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)

        # 创建一个容器来放置所有文件内容组件
        self.container = QWidget()
        self.main_layout = QVBoxLayout(self.container)
        self.main_layout.setSpacing(10)
        self.main_layout.setContentsMargins(10, 10, 10, 10)

        # 文件内容预览区域
        self.preview_container = QGroupBox("文件内容预览")
        self.preview_container.setStyleSheet("""
                    QGroupBox {
                        border: 1px solid #323232;
                        border-radius: 5px;
                        margin-top: 10px;
                        font-weight: bold;
                    }
                    QGroupBox::title {
                        subcontrol-origin: margin;
                        left: 10px;
                        padding: 0 5px;
                    }
                """)

        preview_layout = QVBoxLayout(self.preview_container)
        preview_layout.setContentsMargins(10, 20, 10, 10)

        # 添加提示标签
        self.preview_no_selection = QLabel("请在左侧文件树中选择一个文件进行预览...")
        self.preview_no_selection.setAlignment(Qt.AlignCenter)
        self.preview_no_selection.setStyleSheet("color: #888; padding: 20px;")

        # 创建预览代码组件但初始不可见
        self.preview_code = CodeDisplayWidget(FileInfo("无选择文件", "", False))
        self.preview_code.setVisible(False)  # 初始时不可见

        preview_layout.addWidget(self.preview_no_selection)
        preview_layout.addWidget(self.preview_code)

        # 添加到主布局
        self.main_layout.addWidget(self.preview_container, 1)  # 添加拉伸因子

        self.setWidget(self.container)
        self.file_widgets = {}  # 存储文件路径到组件的映射

    def clear_contents(self):
        """清除所有内容显示"""
        self.file_widgets.clear()

        # 隐藏预览，显示提示
        if hasattr(self, 'preview_code'):
            self.preview_code.setVisible(False)
        if hasattr(self, 'preview_no_selection'):
            self.preview_no_selection.setVisible(True)

    def preview_file(self, file_info):
        """预览文件内容"""
        if not file_info or not file_info.content:
            self.preview_code.setVisible(False)
            self.preview_no_selection.setVisible(True)
            return

        # 隐藏提示文本，显示预览内容
        self.preview_no_selection.setVisible(False)

        # 更新预览内容
        self.preview_code.file_info = file_info
        self.preview_code.header.setText(file_info.path)
        self.preview_code.highlight_code()
        self.preview_code.setVisible(True)

    def select_all_files(self):
        """选择所有文件"""
        main_window = self.window()
        if hasattr(main_window, 'file_tree'):
            count = main_window.file_tree.select_by_condition(lambda file_info: True)
            if count > 0:
                if hasattr(main_window, 'status_bar'):
                    main_window.status_bar.showMessage(f"已选择所有文件 ({count}个)", 2000)
            else:
                QMessageBox.information(self, "批量选择", "没有可选择的文件")

    def deselect_all_files(self):
        """取消选择所有文件"""
        main_window = self.window()
        if hasattr(main_window, 'deselect_all_files'):
            main_window.deselect_all_files()

    def select_cdn_files(self):
        """选择所有CDN文件"""
        main_window = self.window()
        if hasattr(main_window, 'file_tree'):
            count = main_window.file_tree.select_by_condition(lambda file_info: file_info.is_cdn)
            if count > 0:
                if hasattr(main_window, 'status_bar'):
                    main_window.status_bar.showMessage(f"已选择 {count} 个CDN文件", 2000)
            else:
                QMessageBox.information(self, "批量选择", "没有可选择的CDN文件")

    def select_minified_files(self):
        """选择所有压缩文件"""
        main_window = self.window()
        if hasattr(main_window, 'file_tree'):
            count = main_window.file_tree.select_by_condition(lambda file_info: file_info.is_minified)
            if count > 0:
                if hasattr(main_window, 'status_bar'):
                    main_window.status_bar.showMessage(f"已选择 {count} 个压缩文件", 2000)
            else:
                QMessageBox.information(self, "批量选择", "没有可选择的压缩文件")


class FileStructureGenerator(QMainWindow):
    """主应用窗口类"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ProjecTxt")
        self.resize(1200, 800)

        # 初始化mimetype
        mimetypes.init()

        # 初始化设置
        self.settings = QSettings("FileStructureGenerator", "Settings")

        # 创建界面元素
        self.create_widgets()

        # 应用样式
        self.apply_modern_style()

        # 加载历史记录
        self.load_history()

        # 当前工作线程
        self.worker = None

        # 文件信息列表
        self.files_list = []

        # 添加分割器性能优化相关变量
        self.splitter_moving = False
        self.splitter_timer = QTimer()
        self.splitter_timer.setSingleShot(True)
        self.splitter_timer.timeout.connect(self.after_splitter_moved)

    def apply_modern_style(self):
        """应用现代化的UI样式"""
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #2b2b2b;
                color: #a9b7c6;
            }
            QLineEdit, QComboBox {
                background-color: #3c3f41;
                color: #a9b7c6;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 5px;
                selection-background-color: #214283;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                width: 14px;
                height: 14px;
            }
            QPushButton {
                background-color: #365880;
                color: #bbbbbb;
                border: none;
                border-radius: 4px;
                padding: 5px 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4e729d;
            }
            QPushButton:pressed {
                background-color: #2d4a63;
            }
            QSplitter::handle {
                background-color: #3c3f41;
            }
            QStatusBar {
                background-color: #3c3f41;
                color: #a9b7c6;
            }
            QLabel {
                color: #a9b7c6;
            }
            QTextEdit, QTextBrowser {
                background-color: #2b2b2b;
                color: #a9b7c6;
                border: 1px solid #323232;
                border-radius: 4px;
                selection-background-color: #214283;
            }
            QScrollBar:vertical {
                border: none;
                background: #2b2b2b;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #3c3f41;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #4e5254;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar:horizontal {
                border: none;
                background: #2b2b2b;
                height: 10px;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background: #3c3f41;
                border-radius: 5px;
                min-width: 20px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #4e5254;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
            QProgressBar {
                border: 1px solid #555555;
                border-radius: 3px;
                background-color: #3c3f41;
                color: #a9b7c6;
                padding: 1px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #4d99e5;
                width: 10px;
                margin: 0.5px;
            }
            QToolBar {
                background-color: #3c3f41;
                spacing: 3px;
                border: none;
            }
            QToolButton {
                background-color: transparent;
                border: none;
                padding: 5px;
                border-radius: 3px;
            }
            QToolButton:hover {
                background-color: #4d5052;
            }
            QToolButton:pressed {
                background-color: #353739;
            }
            QMenu {
                background-color: #3c3f41;
                color: #a9b7c6;
                border: 1px solid #555555;
            }
            QMenu::item {
                padding: 6px 25px 6px 25px;
            }
            QMenu::item:selected {
                background-color: #2d5f91;
            }
            QCheckBox {
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 15px;
                height: 15px;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #323232;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            """)

    def create_widgets(self):
        """创建界面组件"""
        # 创建中央窗口部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 创建工具栏
        self.create_toolbar()

        # 顶部框架 - 包含文件夹选择
        top_frame = QWidget()
        top_layout = QHBoxLayout(top_frame)
        top_layout.setContentsMargins(10, 10, 10, 10)

        folder_label = QLabel("选择文件夹:")
        folder_label.setMinimumWidth(80)

        self.path_edit = QComboBox()
        self.path_edit.setMinimumWidth(300)
        self.path_edit.setEditable(True)
        self.path_edit.setInsertPolicy(QComboBox.InsertPolicy.InsertAtTop)
        self.path_edit.lineEdit().setPlaceholderText("选择要分析的文件夹路径...")

        browse_btn = QPushButton("浏览")
        browse_btn.setStyleSheet("""
                background-color: #2196F3;
                color: white;
            """)

        # 添加刷新按钮
        refresh_btn = QPushButton("刷新")
        refresh_btn.setStyleSheet("""
                background-color: #4CAF50;
                color: white;
            """)

        # 添加停止按钮
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setStyleSheet("""
                background-color: #F44336;
                color: white;
            """)
        self.stop_btn.setVisible(False)
        self.stop_btn.clicked.connect(self.stop_processing)

        top_layout.addWidget(folder_label)
        top_layout.addWidget(self.path_edit, 1)
        top_layout.addWidget(browse_btn)
        top_layout.addWidget(refresh_btn)
        top_layout.addWidget(self.stop_btn)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setVisible(False)

        progress_layout = QVBoxLayout()
        progress_layout.setContentsMargins(10, 0, 10, 10)
        progress_layout.addWidget(self.progress_bar)

        # 分割线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("background-color: #323232;")

        # 创建分割器用于结构和内容显示
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.splitterMoved.connect(self.on_splitter_moved)

        # 文件结构显示
        structure_container = QWidget()
        structure_layout = QVBoxLayout(structure_container)
        structure_layout.setContentsMargins(0, 0, 0, 0)

        # 创建文件结构控制面板
        structure_control = QGroupBox("文件结构控制")
        structure_control.setStyleSheet("""
                QGroupBox {
                    border: 1px solid #323232;
                    border-radius: 5px;
                    margin-top: 10px;
                    font-weight: bold;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                }
            """)

        structure_control_layout = QVBoxLayout(structure_control)
        structure_control_layout.setContentsMargins(10, 20, 10, 10)

        # 搜索控制布局
        search_layout = QHBoxLayout()
        search_layout.setSpacing(8)

        search_label = QLabel("搜索:")
        self.structure_search = QLineEdit()
        self.structure_search.setPlaceholderText("搜索文件名...")
        self.structure_search.setClearButtonEnabled(True)

        search_layout.addWidget(search_label)
        search_layout.addWidget(self.structure_search)

        # 操作按钮布局 - 两行布局
        operations_layout = QVBoxLayout()
        operations_layout.setSpacing(8)

        # 第一行按钮
        top_buttons_layout = QHBoxLayout()
        top_buttons_layout.setSpacing(8)

        expand_all_btn = QPushButton("全部展开")
        expand_all_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        expand_all_btn.setStyleSheet("font-size: 11px; padding: 3px 8px;")

        collapse_all_btn = QPushButton("全部折叠")
        collapse_all_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        collapse_all_btn.setStyleSheet("font-size: 11px; padding: 3px 8px;")

        top_buttons_layout.addWidget(expand_all_btn)
        top_buttons_layout.addWidget(collapse_all_btn)

        # 第二行按钮
        bottom_buttons_layout = QHBoxLayout()
        bottom_buttons_layout.setSpacing(8)

        select_all_btn = QPushButton("全选")
        select_all_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        select_all_btn.setStyleSheet("font-size: 11px; padding: 3px 8px; background-color: #2E7D32;")

        deselect_all_btn = QPushButton("取消全选")
        deselect_all_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        deselect_all_btn.setStyleSheet("font-size: 11px; padding: 3px 8px; background-color: #C62828;")

        invert_select_btn = QPushButton("反选")  # 新增反选按钮
        invert_select_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        invert_select_btn.setStyleSheet("font-size: 11px; padding: 3px 8px; background-color: #0277BD;")

        bottom_buttons_layout.addWidget(select_all_btn)
        bottom_buttons_layout.addWidget(deselect_all_btn)
        bottom_buttons_layout.addWidget(invert_select_btn)  # 添加反选按钮

        operations_layout.addLayout(top_buttons_layout)
        operations_layout.addLayout(bottom_buttons_layout)

        # 添加类型选择下拉菜单
        file_types_layout = QHBoxLayout()
        file_types_layout.setSpacing(8)

        file_types_label = QLabel("选择类型:")
        self.file_types_combo = QComboBox()
        # 初始只添加默认选项，之后会动态更新
        self.file_types_combo.addItem("选择文件类型...", "")

        # 添加选择/取消选择模式切换
        self.type_select_mode = QCheckBox("取消选择模式")
        self.type_select_mode.setToolTip("勾选后，将取消选择指定类型的文件，而非选择它们")

        file_types_layout.addWidget(file_types_label)
        file_types_layout.addWidget(self.file_types_combo)
        file_types_layout.addWidget(self.type_select_mode)

        # 添加到控制面板布局
        structure_control_layout.addLayout(search_layout)
        structure_control_layout.addLayout(file_types_layout)  # 添加类型选择
        structure_control_layout.addLayout(operations_layout)

        # 创建文件树控件
        self.file_tree = FileTreeWidget()

        structure_layout.addWidget(structure_control)
        structure_layout.addWidget(self.file_tree, 1)

        # 文件内容显示 - 使用优化的预览模式
        self.content_display = FileContentDisplay()

        # 添加到分割器
        self.splitter.addWidget(structure_container)
        self.splitter.addWidget(self.content_display)
        self.splitter.setSizes([400, 800])  # 设置初始大小比例

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # 添加文件统计标签
        self.stats_label = QLabel()
        self.status_bar.addPermanentWidget(self.stats_label)

        # 添加所有部件到主布局
        main_layout.addWidget(top_frame)
        main_layout.addLayout(progress_layout)
        main_layout.addWidget(line)
        main_layout.addWidget(self.splitter, 1)

        # 连接信号和槽
        invert_select_btn.clicked.connect(self.invert_selection)  # 连接反选按钮
        browse_btn.clicked.connect(self.browse_folder)
        refresh_btn.clicked.connect(self.generate_structure)  # 连接刷新按钮
        self.path_edit.lineEdit().returnPressed.connect(self.generate_structure)
        self.path_edit.activated.connect(self.path_selected)
        self.structure_search.textChanged.connect(self.filter_structure)
        expand_all_btn.clicked.connect(self.expand_all_structure)
        collapse_all_btn.clicked.connect(self.collapse_all_structure)
        select_all_btn.clicked.connect(self.select_all_files)
        deselect_all_btn.clicked.connect(self.deselect_all_files)
        self.file_tree.selection_changed.connect(self.update_stats)
        self.file_tree.file_clicked.connect(self.content_display.preview_file)  # 连接文件点击信号到预览功能

    def create_toolbar(self):
        """创建工具栏"""
        toolbar = QToolBar("主工具栏")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(toolbar)

        # 新建按钮
        new_action = QAction("新建", self)
        new_action.setToolTip("清除当前内容")
        new_action.triggered.connect(self.clear_all)

        # 复制按钮
        copy_action = QAction("复制所选文件", self)
        copy_action.setToolTip("将所选文件复制到剪贴板")
        copy_action.triggered.connect(self.copy_to_clipboard)

        # 复制结构按钮
        copy_structure_action = QAction("复制结构", self)
        copy_structure_action.setToolTip("仅复制文件结构到剪贴板")
        copy_structure_action.triggered.connect(self.copy_structure_to_clipboard)

        # 添加排序控件到工具栏
        self.sort_combo = QComboBox()
        self.sort_combo.setFixedWidth(160)
        self.sort_combo.addItem("默认排序", "folder_first")
        self.sort_combo.addItem("按名称排序", "name")
        self.sort_combo.addItem("按类型排序", "type")
        self.sort_combo.addItem("按大小排序", "size")
        self.sort_combo.addItem("按行数排序", "lines")
        self.sort_combo.setStyleSheet("""
            QComboBox {
                background-color: #3c3f41;
                color: #a9b7c6;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 2px 5px;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
        """)
        self.sort_combo.currentIndexChanged.connect(self.sort_structure)

        # 历史按钮
        history_action = QAction("历史记录", self)
        history_action.setToolTip("查看历史记录")
        history_action.triggered.connect(self.show_history)

        # 关于按钮
        about_action = QAction("关于", self)
        about_action.setToolTip("关于ProjecTxt")
        about_action.triggered.connect(self.show_about)

        # 添加到工具栏
        toolbar.addAction(new_action)
        toolbar.addSeparator()
        toolbar.addAction(copy_action)
        toolbar.addSeparator()
        toolbar.addAction(copy_structure_action)
        toolbar.addSeparator()
        # 添加排序控件
        toolbar.addAction(history_action)
        toolbar.addSeparator()
        toolbar.addWidget(self.sort_combo)
        toolbar.addSeparator()
        toolbar.addAction(about_action)


    def stop_processing(self):
        """停止当前处理流程"""
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(1000)  # 等待线程最多1秒钟
            if self.worker.isRunning():
                self.worker.terminate()

            self.progress_bar.setVisible(False)
            self.stop_btn.setVisible(False)
            self.status_bar.showMessage("已停止处理", 3000)

    def show_about(self):
        """显示关于对话框"""
        QMessageBox.about(
            self,
            "关于ProjecTxt",
            "<h3>ProjecTxt</h3>"
            "<p>一个用于生成文件夹结构和显示文件内容的工具</p>"
            "<p>可以将整个项目转换为单一文本，便于向AI提供代码</p>"
            "<p>特性:</p>"
            "<ul>"
            "<li>树形结构显示，支持选择文件</li>"
            "<li>文件统计信息（行数、字符数）</li>"
            "<li>代码语法高亮</li>"
            "<li>自动识别CDN、压缩JS和数据库文件</li>"
            "<li>智能过滤和搜索功能</li>"
            "<li>批量操作功能</li>"
            "<li>文件内容预览</li>"
            "</ul>"
            "<p>版本: 3.0</p>"
        )

    def load_history(self):
        """加载历史记录"""
        history = self.settings.value("history", [])
        if history:
            self.path_edit.addItems(history)

    def save_to_history(self, path):
        """保存路径到历史记录"""
        if not path:
            return

        # 获取现有历史记录
        history = self.settings.value("history", [])
        if not isinstance(history, list):
            history = []

        # 如果路径已经存在，删除它（将会重新添加到顶部）
        if path in history:
            history.remove(path)

        # 添加到顶部
        history.insert(0, path)

        # 限制历史记录数量
        history = history[:10]

        # 保存
        self.settings.setValue("history", history)

        # 更新下拉框
        self.path_edit.clear()
        self.path_edit.addItems(history)

    def show_history(self):
        """显示历史记录对话框"""
        history = self.settings.value("history", [])
        if not history:
            QMessageBox.information(self, "历史记录", "没有历史记录")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("历史记录")
        dialog.setMinimumWidth(500)
        dialog.setMinimumHeight(300)
        dialog.setStyleSheet(self.styleSheet())  # 应用相同的主题

        layout = QVBoxLayout(dialog)

        list_widget = QListWidget()
        list_widget.addItems(history)

        button_layout = QHBoxLayout()
        load_btn = QPushButton("加载所选")
        clear_btn = QPushButton("清除历史")
        cancel_btn = QPushButton("取消")

        button_layout.addWidget(clear_btn)
        button_layout.addStretch()
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(load_btn)

        layout.addWidget(QLabel("双击选择或点击'加载所选'按钮:"))
        layout.addWidget(list_widget)
        layout.addLayout(button_layout)

        # 连接信号
        list_widget.itemDoubleClicked.connect(
            lambda item: self.load_history_item(item.text(), dialog)
        )
        load_btn.clicked.connect(
            lambda: self.load_history_item(
                list_widget.currentItem().text() if list_widget.currentItem() else "",
                dialog
            )
        )
        clear_btn.clicked.connect(self.clear_history)
        cancel_btn.clicked.connect(dialog.reject)

        dialog.exec()

    def load_history_item(self, path, dialog):
        """加载历史记录项目"""
        if path and os.path.isdir(path):
            self.path_edit.setCurrentText(path)
            self.generate_structure()
            dialog.accept()
        else:
            QMessageBox.warning(dialog, "错误", "所选路径不存在或不是有效的目录")

    def clear_history(self):
        """清除历史记录"""
        reply = QMessageBox.question(
            self,
            "确认",
            "确定要清除所有历史记录吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.settings.remove("history")
            self.path_edit.clear()
            QMessageBox.information(self, "已清除", "历史记录已清除")

    def clear_all(self):
        """清除当前所有内容"""
        # 如果有线程正在运行，停止它
        if self.worker and self.worker.isRunning():
            self.stop_processing()

        self.file_tree.clear()
        self.content_display.clear_contents()
        self.stats_label.clear()
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self.stop_btn.setVisible(False)
        self.files_list = []

    def path_selected(self, index):
        """当从下拉列表选择路径时自动生成结构"""
        path = self.path_edit.itemText(index)
        if path and os.path.isdir(path):
            self.generate_structure()

    def browse_folder(self):
        """浏览并选择文件夹"""
        folder_path = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if folder_path:
            self.path_edit.setCurrentText(folder_path)
            # 自动触发生成
            self.generate_structure()

    def filter_structure(self, text):
        """根据搜索文本过滤文件结构"""
        # 在树中搜索匹配的项目
        if not text:
            # 如果搜索文本为空，显示所有项目
            self._reset_all_items_visibility()
            # 添加操作反馈
            self.status_bar.showMessage("已清除过滤", 1000)
            return

        # 搜索并只显示匹配的项目
        text = text.lower()
        match_count = 0
        for i in range(self.file_tree.topLevelItemCount()):
            top_item = self.file_tree.topLevelItem(i)
            if self._search_tree_item(top_item, text):
                match_count += 1

        # 添加操作反馈
        self.status_bar.showMessage(f"找到 {match_count} 个匹配项", 2000)

    def _reset_all_items_visibility(self):
        """重置所有项目的可见性，确保所有项目都可见"""

        def reset_visibility_recursive(item):
            item.setHidden(False)
            for i in range(item.childCount()):
                reset_visibility_recursive(item.child(i))

        # 从顶层项目开始递归重置所有项目的可见性
        root = self.file_tree.invisibleRootItem()
        for i in range(root.childCount()):
            reset_visibility_recursive(root.child(i))

    def _search_tree_item(self, item, text):
        """递归搜索树项目"""
        # 检查当前项目是否匹配
        item_text = item.text(0).lower()
        match = text in item_text

        # 检查子项是否匹配
        child_match = False
        for i in range(item.childCount()):
            if self._search_tree_item(item.child(i), text):
                child_match = True

        # 如果当前项目或任何子项匹配，则显示
        visible = match or child_match
        self._set_tree_item_visible(item, visible)

        return visible

    def _set_tree_item_visible(self, item, visible):
        """设置树项目的可见性"""
        item.setHidden(not visible)

    def expand_all_structure(self):
        """展开所有文件结构项目"""
        self.file_tree.expandAll()
        # 添加操作反馈
        self.status_bar.showMessage("已展开所有文件夹", 1000)

    def collapse_all_structure(self):
        """折叠所有文件结构项目"""
        self.file_tree.collapseAll()
        # 添加操作反馈
        self.status_bar.showMessage("已折叠所有文件夹", 1000)

    def select_all_files(self):
        """选择所有文件"""
        count = self.file_tree.select_by_condition(lambda file_info: True)
        # 添加操作反馈
        self.status_bar.showMessage(f"已选择所有文件 ({count}个)", 2000)

    def deselect_all_files(self):
        """取消选择所有文件"""
        count = 0
        root = self.file_tree.invisibleRootItem()

        # 递归处理所有项目
        def deselect_recursive(item):
            nonlocal count
            # 处理当前项目
            file_info = item.data(0, Qt.ItemDataRole.UserRole)
            if file_info and not file_info.is_dir and file_info.selected:
                file_info.selected = False
                self.file_tree.update_item_color(item, file_info)
                count += 1

            # 处理子项目
            for i in range(item.childCount()):
                deselect_recursive(item.child(i))

        # 从顶层项开始递归
        for i in range(root.childCount()):
            deselect_recursive(root.child(i))

        # 发送信号
        self.file_tree.selection_changed.emit()

        # 添加操作反馈
        self.status_bar.showMessage(f"已取消选择所有文件 ({count}个)", 2000)

    def update_stats(self):
        """更新文件统计信息"""
        # 计算文件总数
        total_files = sum(1 for f in self.files_list if not f.is_dir)

        # 计算已选择的文件数
        selected_files = sum(1 for f in self.files_list if not f.is_dir and f.selected)

        # 计算CDN、压缩和数据库文件数量
        cdn_files = sum(1 for f in self.files_list if not f.is_dir and f.is_cdn)
        minified_files = sum(1 for f in self.files_list if not f.is_dir and f.is_minified)
        database_files = sum(1 for f in self.files_list if not f.is_dir and f.is_database)

        # 计算选中文件的总行数和字符数
        total_lines = sum(f.line_count for f in self.files_list if not f.is_dir and f.selected)
        total_chars = sum(f.char_count for f in self.files_list if not f.is_dir and f.selected)

        # 更新状态栏
        self.stats_label.setText(
            f"总文件: {total_files} | 已选择: {selected_files} | "
            f"CDN: {cdn_files} | 压缩: {minified_files} | 数据库: {database_files} | "
            f"选中行数: {total_lines} | 选中字符: {total_chars}"
        )

    def generate_structure(self):
        """生成并显示文件结构和内容"""
        folder_path = self.path_edit.currentText()
        if not folder_path or not os.path.isdir(folder_path):
            QMessageBox.warning(self, "警告", "请选择有效的文件夹路径！")
            return

        # 停止任何正在运行的处理线程
        if self.worker and self.worker.isRunning():
            self.stop_processing()

        # 添加到历史记录
        self.save_to_history(folder_path)

        # 清空现有内容
        self.clear_all()

        # 显示进度条和停止按钮
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.stop_btn.setVisible(True)
        self.status_bar.showMessage("正在分析文件结构...", 0)

        # 创建工作线程
        self.worker = WorkerThread(folder_path)
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.file_signal.connect(self.process_file)
        self.worker.finished_signal.connect(self.handle_result)
        self.worker.error_signal.connect(self.handle_error)

        # 开始工作
        self.worker.start()

    def update_progress(self, current, total):
        """更新进度条"""
        if total > 0:
            progress = int((current / total) * 100)
            self.progress_bar.setValue(progress)
            self.status_bar.showMessage(f"处理文件 {current}/{total}...", 0)

    def process_file(self, file_info):
        """处理单个文件（在后台线程处理中）"""
        # 在这里可以实时处理文件信息，如果需要的话
        pass

    def handle_result(self, files_list):
        """处理生成结果"""
        # 保存文件列表
        self.files_list = files_list

        # 构建文件树
        self.build_file_tree(files_list)

        # 更新文件类型下拉列表
        self.update_file_types_combo()

        # 展开顶级目录
        self.file_tree.expandToDepth(1)

        # 隐藏进度条和停止按钮
        self.progress_bar.setVisible(False)
        self.stop_btn.setVisible(False)

        # 更新统计信息
        self.update_stats()

        # 显示结果信息
        text_files = [f for f in files_list if not f.is_dir and f.is_text]
        self.status_bar.showMessage(
            f"文件结构生成成功，共{len(text_files)}个文本文件",
            5000
        )

    def update_file_types_combo(self):
        """根据实际文件类型更新下拉列表"""
        # 保存当前选择
        current_index = self.file_types_combo.currentIndex()

        # 安全地断开信号连接，使用try-except避免报错
        try:
            # 检查是否有连接的槽函数
            if self.file_types_combo.receivers(self.file_types_combo.currentIndexChanged) > 0:
                self.file_types_combo.currentIndexChanged.disconnect(self.on_file_type_selected)
        except (TypeError, RuntimeError):
            # 信号可能尚未连接，忽略错误
            pass

        # 清空下拉列表
        self.file_types_combo.clear()
        self.file_types_combo.addItem("选择文件类型...", "")

        # 预定义的特殊类型
        special_types = [
            ("CDN文件", "cdn"),
            ("压缩文件", "minified"),
            ("数据库文件", "database"),
            ("大文件(>100KB)", "large")
        ]

        # 记录找到的文件类型
        found_types = set()
        types_count = {}

        # 统计文件类型
        for file_info in self.files_list:
            if not file_info.is_dir and file_info.file_type:
                file_type = file_info.file_type.lower()
                found_types.add(file_type)
                types_count[file_type] = types_count.get(file_type, 0) + 1

        # 添加特殊类型
        special_type_exists = False
        for name, value in special_types:
            count = 0
            if value == "cdn":
                count = sum(1 for f in self.files_list if not f.is_dir and f.is_cdn)
            elif value == "minified":
                count = sum(1 for f in self.files_list if not f.is_dir and f.is_minified)
            elif value == "database":
                count = sum(1 for f in self.files_list if not f.is_dir and f.is_database)
            elif value == "large":
                count = sum(1 for f in self.files_list if not f.is_dir and f.size > 102400)

            if count > 0:
                self.file_types_combo.addItem(f"{name} ({count})", value)
                special_type_exists = True

        # 添加常见编程语言文件类型
        common_extensions = {
            "py": "Python文件(.py)",
            "js": "JavaScript文件(.js)",
            "html": "HTML文件(.html)",
            "css": "CSS文件(.css)",
            "json": "JSON文件(.json)",
            "php": "PHP文件(.php)",
            "java": "Java文件(.java)",
            "c": "C文件(.c)",
            "cpp": "C++文件(.cpp)",
            "h": "Header文件(.h)",
            "rb": "Ruby文件(.rb)",
            "cs": "C#文件(.cs)",
            "go": "Go文件(.go)",
            "swift": "Swift文件(.swift)",
            "ts": "TypeScript文件(.ts)",
            "jsx": "React JSX文件(.jsx)",
            "tsx": "React TSX文件(.tsx)",
            "xml": "XML文件(.xml)",
            "yml": "YAML文件(.yml)",
            "yaml": "YAML文件(.yaml)",
            "md": "Markdown文件(.md)",
            "sql": "SQL文件(.sql)",
            "sh": "Shell脚本(.sh)",
            "bat": "批处理文件(.bat)",
            "txt": "文本文件(.txt)",
            "conf": "配置文件(.conf)",
            "ini": "INI配置文件(.ini)",
            "gradle": "Gradle文件(.gradle)",
            "dart": "Dart文件(.dart)",
            "vue": "Vue文件(.vue)"
        }

        # 添加已找到的常见类型
        sorted_types = sorted(found_types)
        for file_type in sorted_types:
            count = types_count.get(file_type, 0)
            if count > 0:
                # 使用预定义名称或生成通用名称
                type_name = common_extensions.get(file_type, f"{file_type.upper()}文件(.{file_type})")
                self.file_types_combo.addItem(f"{type_name} ({count})", file_type)

        # 尝试恢复之前的选择
        if current_index > 0 and current_index < self.file_types_combo.count():
            self.file_types_combo.setCurrentIndex(current_index)
        else:
            self.file_types_combo.setCurrentIndex(0)

        # 重新连接信号
        self.file_types_combo.currentIndexChanged.connect(self.on_file_type_selected)

    def sort_structure(self, index):
        """根据选择的方式排序文件结构"""
        sort_key = self.sort_combo.currentData()

        # 如果没有文件列表，则不执行排序
        if not self.files_list:
            return

        # 重新构建文件树
        self.build_file_tree(self.files_list, sort_key)

        # 展开到之前的深度
        self.file_tree.expandToDepth(1)

        # 添加操作反馈
        self.status_bar.showMessage(f"已按{self.sort_combo.currentText()}排序", 2000)

    def build_file_tree(self, files_list, sort_key="folder_first"):
        """构建文件树结构"""
        # 清空树
        self.file_tree.clear()

        # 创建目录映射表，用于快速查找父目录项
        dir_items = {}

        # 按照排序方式对文件列表进行排序
        if sort_key == "folder_first":
            # 先按是否为目录排序（目录在前），再按路径排序
            sorted_files = sorted(files_list, key=lambda f: (not f.is_dir, f.path.lower()))
        elif sort_key == "name":
            # 纯按名称排序
            sorted_files = sorted(files_list, key=lambda f: os.path.basename(f.path).lower())
        elif sort_key == "type":
            # 按文件类型排序
            sorted_files = sorted(files_list,
                                  key=lambda f: (f.file_type.lower() if not f.is_dir else "", f.path.lower()))
        elif sort_key == "size":
            # 按文件大小排序（从大到小）
            sorted_files = sorted(files_list, key=lambda f: (-f.size if not f.is_dir else 0, f.path.lower()))
        elif sort_key == "lines":
            # 按行数排序（从多到少）
            sorted_files = sorted(files_list, key=lambda f: (-f.line_count if not f.is_dir else 0, f.path.lower()))
        else:
            # 默认排序方式
            sorted_files = sorted(files_list, key=lambda f: (not f.is_dir, f.path.lower()))

        for file_info in sorted_files:
            if file_info.is_dir:
                # 处理目录
                parts = file_info.path.split('/')
                dir_name = parts[-1]
                parent_path = '/'.join(parts[:-1]) if len(parts) > 1 else ""

                # 创建目录项
                item = QTreeWidgetItem([dir_name, "目录", "", "", ""])
                item.setData(0, Qt.ItemDataRole.UserRole, file_info)

                # 右对齐后面的列
                for i in range(1, 5):
                    item.setTextAlignment(i, Qt.AlignRight)

                # 设置目录图标
                item.setIcon(0, self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))

                # 添加到父目录或树的顶层
                if parent_path and parent_path in dir_items:
                    dir_items[parent_path].addChild(item)
                else:
                    self.file_tree.addTopLevelItem(item)

                # 保存目录项引用
                dir_items[file_info.path] = item
            else:
                # 处理文件
                parts = file_info.path.split('/')
                file_name = parts[-1]
                parent_path = '/'.join(parts[:-1]) if len(parts) > 1 else ""

                # 创建文件项
                size_str = self.format_size(file_info.size)
                item = QTreeWidgetItem([
                    file_name,
                    file_info.file_type,
                    size_str,
                    str(file_info.line_count),
                    str(file_info.char_count)
                ])
                item.setData(0, Qt.ItemDataRole.UserRole, file_info)

                # 右对齐后面的列
                for i in range(1, 5):
                    item.setTextAlignment(i, Qt.AlignRight)

                # 设置文件图标
                item.setIcon(0, self.file_tree.get_file_icon(file_info.file_type))

                # 添加到父目录或树的顶层
                if parent_path and parent_path in dir_items:
                    dir_items[parent_path].addChild(item)
                else:
                    self.file_tree.addTopLevelItem(item)

                # 根据文件类型设置颜色
                self.file_tree.update_item_color(item, file_info)

    def format_size(self, size_bytes):
        """格式化文件大小显示"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"

    def handle_error(self, error_msg):
        """处理生成错误"""
        QMessageBox.critical(self, "错误", f"生成过程中出现错误: {error_msg}")
        self.progress_bar.setVisible(False)
        self.stop_btn.setVisible(False)
        self.status_bar.showMessage(f"错误: {error_msg}", 5000)

    def copy_to_clipboard(self):
        """复制所选文件内容到剪贴板"""
        selected_files = self.file_tree.get_selected_files()

        if not selected_files:
            QMessageBox.warning(self, "警告", "请先选择要复制的文件（在文件树中点击文件名选择）")
            return

        # 获取文件结构
        structure_text = self.get_structure_text()
        clipboard_text = f"文件结构:\n\n{structure_text}\n\n文件内容:\n\n"

        # 添加文件内容到剪贴板文本
        for file_info in selected_files:
            clipboard_text += f"--- {file_info.path} ({file_info.line_count}行) ---\n{file_info.content}\n\n"

        # 复制到剪贴板
        clipboard = QApplication.clipboard()
        clipboard.setText(clipboard_text)

        # 显示复制成功的消息
        QMessageBox.information(
            self,
            "复制成功",
            f"已将{len(selected_files)}个文件的内容复制到剪贴板！\n"
            f"总计 {sum(f.line_count for f in selected_files)} 行代码, "
            f"{sum(f.char_count for f in selected_files)} 个字符。"
        )

    def copy_structure_to_clipboard(self):
        """只复制文件结构到剪贴板"""
        if not self.files_list:
            QMessageBox.warning(self, "警告", "没有文件结构可复制")
            return

        # 获取文件结构
        structure_text = self.get_structure_text()

        # 复制到剪贴板
        clipboard = QApplication.clipboard()
        clipboard.setText(structure_text)

        # 显示复制成功的消息
        self.status_bar.showMessage("已复制文件结构到剪贴板！", 3000)

    def get_structure_text(self):
        """获取文件结构文本表示"""
        structure_text = ""

        # 添加顶层文件夹
        folder_path = self.path_edit.currentText()
        if folder_path:
            folder_name = os.path.basename(folder_path)
            structure_text += f"{folder_name}/\n"
            base_indent = ""
        else:
            base_indent = ""

        def traverse_tree(item, indent=base_indent, is_last=False, is_root=True):
            nonlocal structure_text
            file_info = item.data(0, Qt.ItemDataRole.UserRole)

            # 根节点特殊处理
            if is_root:
                child_count = item.childCount()
                for i in range(child_count):
                    child = item.child(i)
                    is_child_last = (i == child_count - 1)
                    traverse_tree(child, indent, is_child_last, False)
                return

            # 确定前缀符号
            if is_last:
                prefix = "└── "
                next_indent = indent + "    "
            else:
                prefix = "├── "
                next_indent = indent + "│   "

            if file_info.is_dir:
                # 目录项
                structure_text += f"{indent}{prefix}{item.text(0)}/\n"

                # 处理子项
                child_count = item.childCount()
                for i in range(child_count):
                    child = item.child(i)
                    is_child_last = (i == child_count - 1)
                    traverse_tree(child, next_indent, is_child_last, False)
            else:
                # 文件项
                # 只添加行数信息
                info_str = ""
                if file_info.line_count > 0:
                    info_str += f" ({file_info.line_count}行)"

                structure_text += f"{indent}{prefix}{item.text(0)}{info_str}\n"

        # 从顶层项开始遍历
        root = self.file_tree.invisibleRootItem()
        traverse_tree(root, base_indent, True, True)

        return structure_text

    def on_splitter_moved(self, pos, index):
        """处理分割器移动事件"""
        self.splitter_moving = True

        # 如果预览内容正在显示，临时隐藏以提高性能
        if hasattr(self, 'content_display') and hasattr(self.content_display, 'preview_code'):
            if self.content_display.preview_code.isVisible():
                self.content_display.preview_code.code_browser.setVisible(False)

        # 重新启动定时器
        self.splitter_timer.start(300)  # 300毫秒后触发

    def after_splitter_moved(self):
        """分割器移动结束后的处理"""
        self.splitter_moving = False

        # 恢复预览内容显示
        if hasattr(self, 'content_display') and hasattr(self.content_display, 'preview_code'):
            if self.content_display.preview_code.isVisible():
                self.content_display.preview_code.code_browser.setVisible(True)

    def invert_selection(self):
        """反转当前选择状态"""
        main_window = self.window()
        if hasattr(main_window, 'file_tree'):
            count = 0
            root = main_window.file_tree.invisibleRootItem()

            def invert_recursive(item):
                nonlocal count
                file_info = item.data(0, Qt.ItemDataRole.UserRole)
                if file_info and not file_info.is_dir:
                    file_info.selected = not file_info.selected
                    main_window.file_tree.update_item_color(item, file_info)
                    count += 1

                for i in range(item.childCount()):
                    invert_recursive(item.child(i))

            # 从顶层项开始递归
            for i in range(root.childCount()):
                invert_recursive(root.child(i))

            # 发送选择变更信号
            main_window.file_tree.selection_changed.emit()

            # 添加操作反馈
            if hasattr(main_window, 'status_bar'):
                main_window.status_bar.showMessage(f"已反转 {count} 个文件的选择状态", 2000)

    def invert_selection(self):
        """反转当前选择状态"""
        count = 0
        root = self.file_tree.invisibleRootItem()

        def invert_recursive(item):
            nonlocal count
            file_info = item.data(0, Qt.UserRole)
            if file_info and not file_info.is_dir:
                file_info.selected = not file_info.selected
                self.file_tree.update_item_color(item, file_info)
                count += 1

            for i in range(item.childCount()):
                invert_recursive(item.child(i))

        # 从顶层项开始递归
        for i in range(root.childCount()):
            invert_recursive(root.child(i))

        # 发送选择变更信号
        self.file_tree.selection_changed.emit()

        # 添加操作反馈
        self.status_bar.showMessage(f"已反转 {count} 个文件的选择状态", 2000)

    def on_file_type_selected(self, index):
        """根据选择的文件类型选择或取消选择文件"""
        if index == 0:  # "选择文件类型..." 选项
            return

        file_type = self.file_types_combo.currentData()
        deselect_mode = self.type_select_mode.isChecked()
        count = 0

        # 根据文件类型创建过滤条件
        condition = None
        if file_type == "cdn":
            condition = lambda file_info: file_info.is_cdn
        elif file_type == "minified":
            condition = lambda file_info: file_info.is_minified
        elif file_type == "database":
            condition = lambda file_info: file_info.is_database
        elif file_type == "large":
            condition = lambda file_info: file_info.size > 102400  # 大于100KB
        else:
            # 按文件扩展名选择
            condition = lambda file_info: file_info.file_type.lower() == file_type

        # 选择或取消选择文件
        if deselect_mode:
            # 取消选择指定类型的文件
            count = self.deselect_by_condition(condition)
            operation = f"已取消选择 {count} 个{self.file_types_combo.currentText().split(' (')[0]}"
            no_match_msg = f"没有找到已选择的{self.file_types_combo.currentText().split(' (')[0]}"
        else:
            # 选择指定类型的文件
            count = self.file_tree.select_by_condition(condition)
            operation = f"已选择 {count} 个{self.file_types_combo.currentText().split(' (')[0]}"
            no_match_msg = f"没有找到{self.file_types_combo.currentText().split(' (')[0]}"

        if count > 0:
            self.status_bar.showMessage(operation, 2000)
        else:
            QMessageBox.information(self, "批量操作", no_match_msg)

        # 重置下拉框到默认选项
        self.file_types_combo.setCurrentIndex(0)

    def deselect_by_condition(self, condition_func):
        """根据条件取消选择文件"""
        root = self.file_tree.invisibleRootItem()
        count = self._deselect_by_condition_recursive(root, condition_func)

        # 添加操作反馈
        if count > 0:
            self.file_tree.selection_changed.emit()

        return count

    def _deselect_by_condition_recursive(self, item, condition_func):
        """递归根据条件取消选择文件"""
        count = 0

        for i in range(item.childCount()):
            child = item.child(i)
            file_info = child.data(0, Qt.UserRole)

            if file_info and not file_info.is_dir:
                if condition_func(file_info) and file_info.selected:
                    file_info.selected = False
                    self.file_tree.update_item_color(child, file_info)
                    count += 1

            count += self._deselect_by_condition_recursive(child, condition_func)

        return count


    def select_cdn_files(self):
        """选择所有CDN文件"""
        main_window = self.window()
        if hasattr(main_window, 'file_tree'):
            count = main_window.file_tree.select_by_condition(lambda file_info: file_info.is_cdn)
            if count > 0:
                if hasattr(main_window, 'status_bar'):
                    main_window.status_bar.showMessage(f"已选择 {count} 个CDN文件", 2000)
            else:
                QMessageBox.information(self, "批量选择", "没有可选择的CDN文件")

    def select_minified_files(self):
        """选择所有压缩文件"""
        main_window = self.window()
        if hasattr(main_window, 'file_tree'):
            count = main_window.file_tree.select_by_condition(lambda file_info: file_info.is_minified)
            if count > 0:
                if hasattr(main_window, 'status_bar'):
                    main_window.status_bar.showMessage(f"已选择 {count} 个压缩文件", 2000)
            else:
                QMessageBox.information(self, "批量选择", "没有可选择的压缩文件")


if __name__ == "__main__":
    # 确保Qt使用高DPI缩放
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    # 启用高DPI缩放
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"

    app = QApplication(sys.argv)

    # 设置应用程序字体
    font = QFont("Segoe UI", 9)
    app.setFont(font)

    window = FileStructureGenerator()
    window.show()

    sys.exit(app.exec())