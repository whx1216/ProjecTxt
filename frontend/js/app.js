/**
 * ProjecTxt - 主应用逻辑
 */

// At the beginning of app.js:
let pywebviewReady = false;

// Add this function to the beginning of the script
function ensureAPIReady() {
    return new Promise((resolve) => {
        if (pywebviewReady) {
            resolve();
        } else {
            window.addEventListener('pywebviewready', () => {
                pywebviewReady = true;
                resolve();
            }, { once: true });

            // In case the event was already fired
            setTimeout(() => {
                if (window.pywebview) {
                    pywebviewReady = true;
                    resolve();
                }
            }, 100);
        }
    });
}

window.app = (() => {
    // 私有变量
    let filesList = [];
    let selectedFiles = [];
    let fileTree = null;
    let fileViewer = null;
    let sortKey = 'folder_first';
    let lastMessageTimeout = null;
    let targetRestoreFolder = null;

    // DOM元素引用
    const elements = {
        folderPath: document.getElementById('folderPath'),
        historyList: document.getElementById('historyList'),
        browseBtn: document.getElementById('browseBtn'),
        refreshBtn: document.getElementById('refreshBtn'),
        stopBtn: document.getElementById('stopBtn'),
        newBtn: document.getElementById('newBtn'),
        copySelectedBtn: document.getElementById('copySelectedBtn'),
        copyStructureBtn: document.getElementById('copyStructureBtn'),
        restoreBtn: document.getElementById('restoreBtn'),
        historyBtn: document.getElementById('historyBtn'),
        sortDropdown: document.getElementById('sortDropdown'),
        aboutBtn: document.getElementById('aboutBtn'),
        searchInput: document.getElementById('searchInput'),
        fileTypes: document.getElementById('fileTypes'),
        deselectMode: document.getElementById('deselectMode'),
        expandAllBtn: document.getElementById('expandAllBtn'),
        collapseAllBtn: document.getElementById('collapseAllBtn'),
        selectAllBtn: document.getElementById('selectAllBtn'),
        deselectAllBtn: document.getElementById('deselectAllBtn'),
        invertSelectionBtn: document.getElementById('invertSelectionBtn'),
        fileTreeContainer: document.getElementById('fileTree'),
        noSelection: document.getElementById('noSelection'),
        filePreview: document.getElementById('filePreview'),
        previewFileName: document.getElementById('previewFileName'),
        previewFileInfo: document.getElementById('previewFileInfo'),
        previewFileTags: document.getElementById('previewFileTags'),
        copyContentBtn: document.getElementById('copyContentBtn'),
        codeContainer: document.getElementById('codeContainer'),
        statusMessage: document.getElementById('statusMessage'),
        statsInfo: document.getElementById('statsInfo'),
        progressContainer: document.querySelector('.progress-container'),
        progressInner: document.getElementById('progressInner'),
        progressText: document.getElementById('progressText'),
        modalOverlay: document.getElementById('modalOverlay'),
        modalDialog: document.getElementById('modalDialog'),
        modalTitle: document.getElementById('modalTitle'),
        modalContent: document.getElementById('modalContent'),
        modalClose: document.getElementById('modalClose'),
        modalCancel: document.getElementById('modalCancel'),
        modalConfirm: document.getElementById('modalConfirm'),

        // 还原项目对话框元素
        restoreProjectModal: document.getElementById('restoreProjectModal'),
        restoreProjectClose: document.getElementById('restoreProjectClose'),
        restoreProjectCancel: document.getElementById('restoreProjectCancel'),
        restoreProjectConfirm: document.getElementById('restoreProjectConfirm'),
        restoreProjectText: document.getElementById('restoreProjectText'),
        pasteFromClipboardBtn: document.getElementById('pasteFromClipboardBtn'),
        selectTargetFolderBtn: document.getElementById('selectTargetFolderBtn')
    };

    // 初始化应用
    const init = () => {
        // 初始化文件树组件
        fileTree = new FileTreeComponent(elements.fileTreeContainer);

        // 初始化文件查看器
        fileViewer = new FileViewer({
            noSelection: elements.noSelection,
            filePreview: elements.filePreview,
            fileName: elements.previewFileName,
            fileInfo: elements.previewFileInfo,
            fileTags: elements.previewFileTags,
            codeContainer: elements.codeContainer,
            copyBtn: elements.copyContentBtn
        });

        // 添加事件监听器
        addEventListeners();

        // 加载历史记录
        loadHistory();

        // 更新文件类型下拉框
        updateFileTypesDropdown([]);

        // 隐藏模态窗口
        hideModal();
        hideRestoreProjectModal();
    };

    // 添加事件监听器
    const addEventListeners = () => {
        // 浏览和刷新按钮
        elements.browseBtn.addEventListener('click', browseFolder);
        elements.refreshBtn.addEventListener('click', processCurrentFolder);
        elements.stopBtn.addEventListener('click', stopProcessing);

        // 工具栏按钮
        elements.newBtn.addEventListener('click', clearAll);
        elements.copySelectedBtn.addEventListener('click', copySelectedToClipboard);
        elements.copyStructureBtn.addEventListener('click', copyStructureToClipboard);
        elements.restoreBtn.addEventListener('click', restoreProject);
        elements.historyBtn.addEventListener('click', showHistory);
        elements.aboutBtn.addEventListener('click', showAbout);
        elements.sortDropdown.addEventListener('change', sortFiles);

        // 控制面板
        elements.searchInput.addEventListener('input', filterFileTree);
        elements.fileTypes.addEventListener('change', selectFilesByType);
        elements.expandAllBtn.addEventListener('click', expandAllNodes);
        elements.collapseAllBtn.addEventListener('click', collapseAllNodes);
        elements.selectAllBtn.addEventListener('click', selectAllFiles);
        elements.deselectAllBtn.addEventListener('click', deselectAllFiles);
        elements.invertSelectionBtn.addEventListener('click', invertSelection);

        // 文件路径回车处理
        elements.folderPath.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                processCurrentFolder();
            }
        });

        // 模态框关闭
        elements.modalClose.addEventListener('click', hideModal);
        elements.modalCancel.addEventListener('click', hideModal);

        // 还原项目对话框事件
        elements.restoreProjectClose.addEventListener('click', hideRestoreProjectModal);
        elements.restoreProjectCancel.addEventListener('click', hideRestoreProjectModal);
        elements.pasteFromClipboardBtn.addEventListener('click', pasteFromClipboard);
        elements.selectTargetFolderBtn.addEventListener('click', selectRestoreTargetFolder);
        elements.restoreProjectConfirm.addEventListener('click', executeProjectRestore);

        // 文件树事件
        fileTree.onNodeSelect((file) => {
            if (!file.is_dir) {
                previewFile(file);
                // 如果文件已被选中，则更新状态
                const isSelected = selectedFiles.some(f => f.path === file.path);
                if (isSelected !== file.selected) {
                    file.selected = isSelected;
                    fileTree.updateNodeSelection(file);
                }
            }
        });

        fileTree.onSelectionChange((file, selected) => {
            // 更新选中状态
            if (selected) {
                selectedFiles.push(file);
            } else {
                selectedFiles = selectedFiles.filter(f => f.path !== file.path);
            }

            // 更新统计信息
            updateStats();

            // 显示状态消息
            if (selected) {
                showStatusMessage(`已选择: ${file.path}`, 2000);
            } else {
                showStatusMessage(`已取消选择: ${file.path}`, 2000);
            }
        });
    };

    // 浏览文件夹
    const browseFolder = async () => {
        try {
            await ensureAPIReady();
            const result = await window.pywebview.api.browse_folder();
            if (result) {
                elements.folderPath.value = result;
                processCurrentFolder();
            }
        } catch (error) {
            console.error('Failed to browse folder:', error);
            showStatusMessage('浏览文件夹失败', 3000);
        }
    };

    // 处理当前文件夹
    const processCurrentFolder = async () => {
        const folderPath = elements.folderPath.value.trim();
        if (!folderPath) {
            showModal('警告', '请选择有效的文件夹路径！', 'warning');
            return;
        }

        // 清除现有内容
        clearAll();

        // 显示进度条和停止按钮
        elements.progressContainer.style.display = 'flex';
        elements.stopBtn.style.display = 'block';
        elements.refreshBtn.style.display = 'none';
        showStatusMessage('正在分析文件结构...', 0);

        try {
            const result = await window.pywebview.api.process_folder(folderPath);
            if (result.status === 'error') {
                showModal('错误', result.message, 'error');
                resetProgressUI();
            }
        } catch (error) {
            console.error('Failed to process folder:', error);
            showModal('错误', '处理文件夹时发生错误', 'error');
            resetProgressUI();
        }
    };

    // 停止处理
    const stopProcessing = async () => {
        try {
            await window.pywebview.api.stop_processing();
            showStatusMessage('正在停止处理...', 0);
        } catch (error) {
            console.error('Failed to stop processing:', error);
        }
    };

    // 更新进度
    const updateProgress = (current, total, percentage) => {
        elements.progressInner.style.width = `${percentage}%`;
        elements.progressText.textContent = `${percentage}%`;
        showStatusMessage(`处理文件 ${current}/${total}...`, 0);
    };

    // 处理完成
    const processComplete = (filesData) => {
        // 恢复UI
        resetProgressUI();

        // 保存文件列表
        filesList = filesData;

        // 构建文件树
        buildFileTree();

        // 更新文件类型下拉框
        updateFileTypesDropdown(filesList);

        // 展开顶级目录
        fileTree.expandToDepth(1);

        // 更新统计信息
        updateStats();

        // 显示结果信息
        const textFiles = filesList.filter(f => !f.is_dir && f.is_text);
        showStatusMessage(`文件结构生成成功，共${textFiles.length}个文本文件`, 5000);
    };

    // 处理错误
    const processError = (errorMsg) => {
        showModal('错误', `生成过程中出现错误: ${errorMsg}`, 'error');
        resetProgressUI();
        showStatusMessage(`错误: ${errorMsg}`, 5000);
    };

    // 处理停止
    const processStopped = () => {
        resetProgressUI();
        showStatusMessage('已停止处理', 3000);
    };

    // 重置进度UI
    const resetProgressUI = () => {
        elements.progressContainer.style.display = 'none';
        elements.stopBtn.style.display = 'none';
        elements.refreshBtn.style.display = 'block';
        elements.progressInner.style.width = '0%';
        elements.progressText.textContent = '0%';
    };

    // 构建文件树
    const buildFileTree = () => {
        fileTree.buildTree(filesList, sortKey);
    };

    // 排序文件
    const sortFiles = () => {
        sortKey = elements.sortDropdown.value;
        if (filesList.length > 0) {
            buildFileTree();
            fileTree.expandToDepth(1);
            showStatusMessage(`已按${elements.sortDropdown.options[elements.sortDropdown.selectedIndex].text}排序`, 2000);
        }
    };

    // 过滤文件树
    const filterFileTree = () => {
        const searchText = elements.searchInput.value.trim().toLowerCase();
        fileTree.filterTree(searchText);

        if (searchText) {
            const matchCount = fileTree.getVisibleNodesCount();
            showStatusMessage(`找到 ${matchCount} 个匹配项`, 2000);
        } else {
            showStatusMessage('已清除过滤', 1000);
        }
    };

    // 按文件类型选择
    const selectFilesByType = () => {
        const fileType = elements.fileTypes.value;
        if (!fileType) return;

        const deselect = elements.deselectMode.checked;
        let conditionFn;

        // 创建过滤条件
        switch (fileType) {
            case 'cdn':
                conditionFn = file => file.is_cdn;
                break;
            case 'minified':
                conditionFn = file => file.is_minified;
                break;
            case 'database':
                conditionFn = file => file.is_database;
                break;
            case 'large':
                conditionFn = file => file.size > 102400;
                break;
            default:
                conditionFn = file => file.file_type.toLowerCase() === fileType;
        }

        const count = deselect
            ? fileTree.deselectByCondition(conditionFn)
            : fileTree.selectByCondition(conditionFn);

        const typeName = elements.fileTypes.options[elements.fileTypes.selectedIndex].text.split(' (')[0];

        if (count > 0) {
            const action = deselect ? '已取消选择' : '已选择';
            showStatusMessage(`${action} ${count} 个${typeName}`, 2000);
        } else {
            const action = deselect ? '没有找到已选择的' : '没有找到';
            showModal('批量操作', `${action}${typeName}`, 'info');
        }

        // 重置下拉框
        elements.fileTypes.selectedIndex = 0;

        // 更新选中文件列表
        updateSelectedFiles();
    };

    // 更新文件类型下拉框
    const updateFileTypesDropdown = (files) => {
        const select = elements.fileTypes;

        // 保存当前选择
        const currentValue = select.value;

        // 清空下拉列表
        select.innerHTML = '';
        select.add(new Option('选择文件类型...', ''));

        if (files.length === 0) return;

        // 预定义的特殊类型
        const specialTypes = [
            ['CDN文件', 'cdn'],
            ['压缩文件', 'minified'],
            ['数据库文件', 'database'],
            ['大文件(>100KB)', 'large']
        ];

        // 记录找到的文件类型
        const foundTypes = new Set();
        const typesCount = {};

        // 统计文件类型
        files.forEach(file => {
            if (!file.is_dir && file.file_type) {
                const fileType = file.file_type.toLowerCase();
                foundTypes.add(fileType);
                typesCount[fileType] = (typesCount[fileType] || 0) + 1;
            }
        });

        // 添加特殊类型
        specialTypes.forEach(([name, value]) => {
            let count = 0;
            if (value === 'cdn') {
                count = files.filter(f => !f.is_dir && f.is_cdn).length;
            } else if (value === 'minified') {
                count = files.filter(f => !f.is_dir && f.is_minified).length;
            } else if (value === 'database') {
                count = files.filter(f => !f.is_dir && f.is_database).length;
            } else if (value === 'large') {
                count = files.filter(f => !f.is_dir && f.size > 102400).length;
            }

            if (count > 0) {
                select.add(new Option(`${name} (${count})`, value));
            }
        });

        // 添加常见编程语言文件类型的映射
        const commonExtensions = {
            'py': 'Python文件(.py)',
            'js': 'JavaScript文件(.js)',
            'html': 'HTML文件(.html)',
            'css': 'CSS文件(.css)',
            'json': 'JSON文件(.json)',
            'php': 'PHP文件(.php)',
            'java': 'Java文件(.java)',
            'c': 'C文件(.c)',
            'cpp': 'C++文件(.cpp)',
            'h': 'Header文件(.h)',
            'rb': 'Ruby文件(.rb)',
            'cs': 'C#文件(.cs)',
            'go': 'Go文件(.go)',
            'swift': 'Swift文件(.swift)',
            'ts': 'TypeScript文件(.ts)',
            'jsx': 'React JSX文件(.jsx)',
            'tsx': 'React TSX文件(.tsx)',
            'xml': 'XML文件(.xml)',
            'yml': 'YAML文件(.yml)',
            'yaml': 'YAML文件(.yaml)',
            'md': 'Markdown文件(.md)',
            'sql': 'SQL文件(.sql)',
            'sh': 'Shell脚本(.sh)',
            'bat': '批处理文件(.bat)',
            'txt': '文本文件(.txt)',
            'conf': '配置文件(.conf)',
            'ini': 'INI配置文件(.ini)',
            'gradle': 'Gradle文件(.gradle)',
            'dart': 'Dart文件(.dart)',
            'vue': 'Vue文件(.vue)'
        };

        // 添加已找到的常见类型
        Array.from(foundTypes).sort().forEach(fileType => {
            const count = typesCount[fileType] || 0;
            if (count > 0) {
                // 使用预定义名称或生成通用名称
                const typeName = commonExtensions[fileType] || `${fileType.toUpperCase()}文件(.${fileType})`;
                select.add(new Option(`${typeName} (${count})`, fileType));
            }
        });

        // 尝试恢复之前的选择
        if (currentValue) {
            for (let i = 0; i < select.options.length; i++) {
                if (select.options[i].value === currentValue) {
                    select.selectedIndex = i;
                    break;
                }
            }
        }
    };

    // 展开所有节点
    const expandAllNodes = () => {
        fileTree.expandAll();
        showStatusMessage('已展开所有文件夹', 1000);
    };

    // 折叠所有节点
    const collapseAllNodes = () => {
        fileTree.collapseAll();
        showStatusMessage('已折叠所有文件夹', 1000);
    };

    // 选择所有文件
    const selectAllFiles = () => {
        const count = fileTree.selectByCondition(() => true);
        showStatusMessage(`已选择所有文件 (${count}个)`, 2000);
        updateSelectedFiles();
    };

    // 取消选择所有文件
    const deselectAllFiles = () => {
        const count = fileTree.deselectByCondition(() => true);
        showStatusMessage(`已取消选择所有文件 (${count}个)`, 2000);
        selectedFiles = [];
        updateStats();
    };

    // 反转选择
    const invertSelection = () => {
        const count = fileTree.invertSelection();
        showStatusMessage(`已反转 ${count} 个文件的选择状态`, 2000);
        updateSelectedFiles();
    };

    // 更新选中的文件列表
    const updateSelectedFiles = () => {
        selectedFiles = fileTree.getSelectedFiles();
        updateStats();
    };

    // 预览文件
    const previewFile = async (file) => {
        if (!file || file.is_dir) return;

        // 如果文件内容还不完整，从后端获取
        if (!file.content && file.is_text) {
            try {
                const result = await window.pywebview.api.get_file_content(file.full_path);
                if (result.status === 'success') {
                    file.content = result.file_info.content;
                    fileViewer.displayFile(file, result.highlighted_code, result.css);
                } else {
                    showStatusMessage(`获取文件内容失败: ${result.message}`, 3000);
                    fileViewer.displayFile(file);
                }
            } catch (error) {
                console.error('Failed to get file content:', error);
                fileViewer.displayFile(file);
            }
        } else {
            // 使用现有内容
            try {
                const highlight = await window.pywebview.api.highlight_code(file.content, file.path);
                fileViewer.displayFile(file, highlight.highlighted_code, highlight.css);
            } catch (error) {
                console.error('Failed to highlight code:', error);
                fileViewer.displayFile(file);
            }
        }
    };

    // 更新统计信息
    const updateStats = () => {
        if (filesList.length === 0) {
            elements.statsInfo.textContent = '';
            return;
        }

        // 计算文件总数
        const totalFiles = filesList.filter(f => !f.is_dir).length;

        // 计算已选择的文件数
        const selectedFileCount = selectedFiles.length;

        // 计算CDN、压缩和数据库文件数量
        const cdnFiles = filesList.filter(f => !f.is_dir && f.is_cdn).length;
        const minifiedFiles = filesList.filter(f => !f.is_dir && f.is_minified).length;
        const databaseFiles = filesList.filter(f => !f.is_dir && f.is_database).length;

        // 计算选中文件的总行数和字符数
        const totalLines = selectedFiles.reduce((sum, f) => sum + f.line_count, 0);
        const totalChars = selectedFiles.reduce((sum, f) => sum + f.char_count, 0);

        // 更新状态栏
        elements.statsInfo.textContent =
            `总文件: ${totalFiles} | 已选择: ${selectedFileCount} | ` +
            `CDN: ${cdnFiles} | 压缩: ${minifiedFiles} | 数据库: ${databaseFiles} | ` +
            `选中行数: ${totalLines} | 选中字符: ${totalChars}`;
    };

    // 清除所有内容
    const clearAll = () => {
        filesList = [];
        selectedFiles = [];
        fileTree.clear();
        fileViewer.clear();
        elements.statsInfo.textContent = '';
        resetProgressUI();
    };

    // 复制选中文件到剪贴板
    const copySelectedToClipboard = () => {
        if (selectedFiles.length === 0) {
            showModal('警告', '请先选择要复制的文件（在文件树中点击文件名选择）', 'warning');
            return;
        }

        // 获取文件结构
        const structureText = getStructureText();
        let clipboardText = `文件结构:\n\n${structureText}\n\n文件内容:\n\n`;

        // 添加文件内容到剪贴板文本
        selectedFiles.forEach(file => {
            clipboardText += `--- ${file.path} (${file.line_count}行) ---\n${file.content}\n\n`;
        });

        // 复制到剪贴板
        navigator.clipboard.writeText(clipboardText).then(() => {
            showModal(
                '复制成功',
                `已将${selectedFiles.length}个文件的内容复制到剪贴板！<br>` +
                `总计 ${selectedFiles.reduce((sum, f) => sum + f.line_count, 0)} 行代码, ` +
                `${selectedFiles.reduce((sum, f) => sum + f.char_count, 0)} 个字符。`,
                'success'
            );
        }).catch(err => {
            console.error('Failed to copy:', err);
            showModal('错误', '复制到剪贴板失败', 'error');
        });
    };

    // 复制结构到剪贴板
    const copyStructureToClipboard = () => {
        if (filesList.length === 0) {
            showModal('警告', '没有文件结构可复制', 'warning');
            return;
        }

        // 获取文件结构
        const structureText = getStructureText();

        // 复制到剪贴板
        navigator.clipboard.writeText(structureText).then(() => {
            showStatusMessage('已复制文件结构到剪贴板！', 3000);
        }).catch(err => {
            console.error('Failed to copy structure:', err);
            showModal('错误', '复制到剪贴板失败', 'error');
        });
    };

    // 获取文件结构文本
    const getStructureText = () => {
        return fileTree.getTreeText();
    };

    // 显示历史记录
    const showHistory = async () => {
        try {
            const history = await window.pywebview.api.get_history();
            if (!history || history.length === 0) {
                showModal('历史记录', '没有历史记录', 'info');
                return;
            }

            let historyHtml = `
                <ul class="history-list">
                    ${history.map((path, index) => `
                        <li class="history-item" data-path="${path}" data-index="${index}">${path}</li>
                    `).join('')}
                </ul>
            `;

            showModal('历史记录', historyHtml, 'history', async () => {
                try {
                    await window.pywebview.api.clear_history();
                    loadHistory();
                    hideModal();
                    showStatusMessage('历史记录已清除', 2000);
                } catch (error) {
                    console.error('Failed to clear history:', error);
                    showStatusMessage('清除历史记录失败', 2000);
                }
            }, '清除历史');

            // 添加点击事件处理
            const historyItems = document.querySelectorAll('.history-item');
            historyItems.forEach(item => {
                item.addEventListener('click', () => {
                    const path = item.dataset.path;
                    elements.folderPath.value = path;
                    processCurrentFolder();
                    hideModal();
                });

                // 双击也可以选择
                item.addEventListener('dblclick', () => {
                    const path = item.dataset.path;
                    elements.folderPath.value = path;
                    processCurrentFolder();
                    hideModal();
                });
            });
        } catch (error) {
            console.error('Failed to get history:', error);
            showStatusMessage('获取历史记录失败', 2000);
        }
    };

    // 加载历史记录
    const loadHistory = async () => {
        try {
            await ensureAPIReady();
            const history = await window.pywebview.api.get_history();
            if (history && history.length > 0) {
                // Clear existing options
                while (elements.historyList.firstChild) {
                    elements.historyList.removeChild(elements.historyList.firstChild);
                }

                // Add history records
                history.forEach(path => {
                    const option = document.createElement('option');
                    option.value = path;
                    elements.historyList.appendChild(option);
                });
            }
        } catch (error) {
            console.error('Failed to load history:', error);
        }
    };

    // 显示关于对话框
    const showAbout = () => {
        const aboutContent = `
            <h3>ProjecTxt</h3>
            <p>一个用于生成文件夹结构和显示文件内容的工具</p>
            <p>可以将整个项目转换为单一文本，便于向AI提供代码</p>
            <p>特性:</p>
            <ul style="margin-left: 30px">
                <li>树形结构显示，支持选择文件</li>
                <li>文件统计信息（行数、字符数）</li>
                <li>代码语法高亮</li>
                <li>自动识别CDN、压缩JS和数据库文件</li>
                <li>智能过滤和搜索功能</li>
                <li>批量操作功能</li>
                <li>文件内容预览</li>
                <li>从文本还原项目功能</li>
            </ul>
            <p>版本: 3.1</p>
        `;

        showModal('关于ProjecTxt', aboutContent, 'info');
    };

    // 显示模态对话框
    const showModal = (title, content, type = 'info', onConfirm = null, confirmText = '确定') => {
        elements.modalTitle.textContent = title;
        elements.modalContent.innerHTML = content;
        elements.modalOverlay.style.display = 'flex';

        // 设置确认按钮文本和回调
        elements.modalConfirm.textContent = confirmText;
        elements.modalConfirm.onclick = onConfirm || hideModal;

        // 根据类型设置样式
        switch (type) {
            case 'warning':
                elements.modalDialog.style.borderTop = '4px solid var(--warning-color)';
                break;
            case 'error':
                elements.modalDialog.style.borderTop = '4px solid var(--danger-color)';
                break;
            case 'success':
                elements.modalDialog.style.borderTop = '4px solid var(--success-color)';
                break;
            case 'history':
                elements.modalDialog.style.borderTop = '4px solid var(--primary-color)';
                break;
            default:
                elements.modalDialog.style.borderTop = '4px solid var(--primary-color)';
                break;
        }
    };

    // 隐藏模态对话框
    const hideModal = () => {
        elements.modalOverlay.style.display = 'none';
    };

    // 显示状态栏消息
    const showStatusMessage = (message, duration = 0) => {
        // 清除之前的超时
        if (lastMessageTimeout) {
            clearTimeout(lastMessageTimeout);
        }

        // 设置消息
        elements.statusMessage.textContent = message;

        // 如果持续时间大于0，设置定时器清除消息
        if (duration > 0) {
            lastMessageTimeout = setTimeout(() => {
                elements.statusMessage.textContent = '';
                lastMessageTimeout = null;
            }, duration);
        }
    };

    // 格式化文件大小
    const formatFileSize = (sizeBytes) => {
        if (sizeBytes < 1024) {
            return `${sizeBytes} B`;
        } else if (sizeBytes < 1024 * 1024) {
            return `${(sizeBytes / 1024).toFixed(1)} KB`;
        } else if (sizeBytes < 1024 * 1024 * 1024) {
            return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`;
        } else {
            return `${(sizeBytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
        }
    };

    // 还原项目对话框
    const restoreProject = () => {
        elements.restoreProjectText.value = '';
        targetRestoreFolder = null;
        elements.restoreProjectModal.style.display = 'flex';
    };

    // 隐藏还原项目对话框
    const hideRestoreProjectModal = () => {
        elements.restoreProjectModal.style.display = 'none';
    };

    // 从剪贴板粘贴
    const pasteFromClipboard = async () => {
        try {
            const text = await navigator.clipboard.readText();
            elements.restoreProjectText.value = text;
            showStatusMessage('已从剪贴板粘贴内容', 2000);
        } catch (error) {
            console.error('Failed to read clipboard:', error);
            showStatusMessage('无法读取剪贴板内容', 2000);
        }
    };

    // 选择目标文件夹
    const selectRestoreTargetFolder = async () => {
        try {
            const result = await window.pywebview.api.browse_folder();
            if (result) {
                targetRestoreFolder = result;
                showStatusMessage(`已选择目标文件夹: ${result}`, 2000);
            }
        } catch (error) {
            console.error('Failed to browse folder:', error);
            showStatusMessage('选择目标文件夹失败', 3000);
        }
    };

    // 执行项目还原
    const executeProjectRestore = async () => {
        const textContent = elements.restoreProjectText.value.trim();
        if (!textContent) {
            showModal('错误', '请先粘贴项目文本内容', 'error');
            return;
        }

        if (!targetRestoreFolder) {
            showModal('错误', '请先选择目标文件夹', 'error');
            return;
        }

        try {
            // 显示进度条
            elements.progressContainer.style.display = 'flex';
            elements.stopBtn.style.display = 'none';
            showStatusMessage('正在还原项目结构...', 0);

            // 隐藏对话框
            hideRestoreProjectModal();

            // 调用后端API
            await window.pywebview.api.restore_project_from_text(textContent, targetRestoreFolder);
        } catch (error) {
            console.error('Failed to restore project:', error);
            showModal('错误', '还原项目时发生错误', 'error');
            resetProgressUI();
        }
    };

    // 更新还原进度
    const updateRestoreProgress = (current, total, percentage) => {
        elements.progressInner.style.width = `${percentage}%`;
        elements.progressText.textContent = `${percentage}%`;
        showStatusMessage(`还原文件 ${current}/${total}...`, 0);
    };

    // 还原完成
    const restoreComplete = (result) => {
        // 恢复UI
        resetProgressUI();

        if (result.missing_content && result.missing_content.length > 0) {
            // 构建缺少内容文件列表
            const missingFiles = result.missing_content.filter(file => !file.startsWith('跳过'));
            const skippedFiles = result.missing_content.filter(file => file.startsWith('跳过'));

            let message = `<p>项目还原完成! 共处理 ${result.processed} 个项目。</p>`;

            if (missingFiles.length > 0) {
                message += `<p>以下 ${missingFiles.length} 个文件缺少内容，已创建为空文件:</p>
                <div style="max-height: 200px; overflow-y: auto; margin: 10px 0; border: 1px solid var(--border-color); padding: 10px;">
                    <ul style="margin: 0; padding-left: 20px;">
                        ${missingFiles.map(file => `<li>${file}</li>`).join('')}
                    </ul>
                </div>`;
            }

            if (skippedFiles.length > 0) {
                message += `<p>以下 ${skippedFiles.length} 个文件已存在，已跳过:</p>
                <div style="max-height: 200px; overflow-y: auto; margin: 10px 0; border: 1px solid var(--border-color); padding: 10px;">
                    <ul style="margin: 0; padding-left: 20px;">
                        ${skippedFiles.map(file => `<li>${file.replace('跳过已存在的文件: ', '')}</li>`).join('')}
                    </ul>
                </div>`;
            }

            showModal('还原结果', message, 'info');
        } else {
            showStatusMessage(`项目还原成功，共${result.processed}个文件/文件夹`, 5000);
        }
    };

    // 初始化
    init();

    // 公开API
    return {
        updateProgress,
        processComplete,
        processError,
        processStopped,
        formatFileSize,
        showStatusMessage,
        updateRestoreProgress,
        restoreComplete
    };
})();