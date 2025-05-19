/**
 * 文件树组件
 * 支持文件/文件夹的树状结构显示、搜索、选择、展开/折叠等功能
 */
class FileTreeComponent {

    constructor(container) {
        this.container = container;
        this.nodeMap = new Map();  // 节点映射，用于快速查找
        this.files = [];           // 原始文件列表
        this.sortKey = 'folder_first'; // 当前排序方式
        this.onSelectCallback = null;  // 节点选择回调
        this.onSelectionChangeCallback = null; // 选择状态变更回调

        // 初始化上下文菜单
        this.contextMenu = new ContextMenuComponent();
    }


    // Add a new method to handle context menu setup
    setupContextMenu() {
        this.container.addEventListener('contextmenu', (event) => {
            const node = event.target.closest('.tree-node');
            if (!node) return;

            event.preventDefault();
            event.stopPropagation();

            const path = node.dataset.path;
            const nodeData = this.nodeMap.get(path);

            if (!nodeData) return;

            const file = nodeData.data;

            // Use the dedicated method to show context menu
            this.showContextMenuForNode(node, file, event.clientX, event.clientY);
        });
    }

    // Add a method to toggle file selection
    toggleFileSelection(file) {
        file.selected = !file.selected;
        this.updateNodeSelection(file);

        // Trigger selection change callback
        if (this.onSelectionChangeCallback) {
            this.onSelectionChangeCallback(file, file.selected);
        }
    }

    // Add a method to select all files in a folder
    selectFolderFiles(node, select) {
        const count = this._selectChildrenRecursive(node, select);

        // Show status message via main app
        if (window.app && window.app.showStatusMessage) {
            const action = select ? "已选择" : "已取消选择";
            window.app.showStatusMessage(`${action} ${count} 个文件`, 2000);
        }
    }

    // Helper method for recursive selection
    _selectChildrenRecursive(node, select) {
        let count = 0;

        const folder = node.querySelector('.tree-folder');
        if (!folder) return count;

        // Get all child nodes
        const childNodes = folder.querySelectorAll('.tree-node');

        // Process each child
        for (const childNode of childNodes) {
            const path = childNode.dataset.path;
            const isDir = childNode.dataset.isDir === 'true';
            const nodeData = this.nodeMap.get(path);

            if (!nodeData) continue;

            const file = nodeData.data;

            if (isDir) {
                // Recursively process subdirectories
                count += this._selectChildrenRecursive(childNode, select);
            } else {
                // Process file
                if (file.selected !== select) {
                    file.selected = select;
                    this.updateNodeSelection(file);
                    count++;

                    // Trigger selection change callback
                    if (this.onSelectionChangeCallback) {
                        this.onSelectionChangeCallback(file, select);
                    }
                }
            }
        }

        return count;
    }

    /**
     * 构建整棵树
     * @param {Array} files - 文件列表
     * @param {string} sortKey - 排序方式
     */
    buildTree(files, sortKey = 'folder_first') {
        // 保存原始数据
        this.files = files;
        this.sortKey = sortKey;

        // 清空容器和映射
        this.container.innerHTML = '';
        this.nodeMap.clear();

        // 排序文件
        const sortedFiles = this.sortFiles(files, sortKey);

        // 构建目录映射
        const dirMap = new Map();

        // 创建根节点容器
        const rootNode = document.createElement('div');
        rootNode.className = 'tree-root';

        // 处理所有文件和文件夹
        for (const file of sortedFiles) {
            if (file.is_dir) {
                // 处理目录
                const parts = file.path.split('/');
                const dirName = parts[parts.length - 1];
                const parentPath = parts.slice(0, -1).join('/');

                // 创建目录节点
                const dirNode = this.createDirNode(file, dirName);

                // 添加到父目录或顶层
                if (parentPath && dirMap.has(parentPath)) {
                    const parentFolder = dirMap.get(parentPath).querySelector('.tree-folder');
                    parentFolder.appendChild(dirNode);
                } else {
                    rootNode.appendChild(dirNode);
                }

                // 保存目录节点引用
                dirMap.set(file.path, dirNode);
                this.nodeMap.set(file.path, {node: dirNode, data: file});
            } else {
                // 处理文件
                const parts = file.path.split('/');
                const fileName = parts[parts.length - 1];
                const parentPath = parts.slice(0, -1).join('/');

                // 创建文件节点
                const fileNode = this.createFileNode(file, fileName);

                // 添加到父目录或顶层
                if (parentPath && dirMap.has(parentPath)) {
                    const parentFolder = dirMap.get(parentPath).querySelector('.tree-folder');
                    parentFolder.appendChild(fileNode);
                } else {
                    rootNode.appendChild(fileNode);
                }

                // 保存文件节点引用
                this.nodeMap.set(file.path, {node: fileNode, data: file});
            }
        }

        // 添加到容器
        this.container.appendChild(rootNode);
    }

    /**
     * 创建目录节点
     * @param {Object} dirInfo - 目录信息
     * @param {string} dirName - 目录名称
     * @returns {HTMLElement} - 目录节点
     */
    createDirNode(dirInfo, dirName) {
        // 创建节点容器
        const node = document.createElement('div');
        node.className = 'tree-node';
        node.dataset.path = dirInfo.path;
        node.dataset.isDir = 'true';

        // 创建节点内容
        const content = document.createElement('div');
        content.className = 'tree-node-content';

        // 目录图标
        const icon = document.createElement('span');
        icon.className = 'tree-node-icon fas fa-folder';

        // 目录名称
        const label = document.createElement('span');
        label.className = 'tree-node-label';
        label.textContent = dirName;

        // 将元素添加到内容
        content.appendChild(icon);
        content.appendChild(label);
        node.appendChild(content);

        // 创建子文件夹容器
        const folder = document.createElement('div');
        folder.className = 'tree-folder';
        folder.style.display = 'none'; // 初始折叠
        node.appendChild(folder);

        // 左键点击 - 切换展开/折叠状态
        content.addEventListener('click', () => {
            this.toggleFolder(node, icon);

            // 触发节点选择回调
            if (this.onSelectCallback) {
                this.onSelectCallback(dirInfo);
            }
        });

        // 阻止目录节点上的右键菜单默认行为
        content.addEventListener('contextmenu', (event) => {
            event.preventDefault();
            event.stopPropagation();

            // 显示上下文菜单
            this.showContextMenuForNode(node, dirInfo, event.clientX, event.clientY);
        });

        return node;
    }

    /**
     * 创建文件节点
     * @param {Object} fileInfo - 文件信息
     * @param {string} fileName - 文件名称
     * @returns {HTMLElement} - 文件节点
     */
    createFileNode(fileInfo, fileName) {
        // 创建节点容器
        const node = document.createElement('div');
        node.className = 'tree-node';
        node.dataset.path = fileInfo.path;
        node.dataset.isDir = 'false';

        // 添加特殊类型样式
        if (fileInfo.is_cdn) {
            node.classList.add('tree-node-cdn');
        } else if (fileInfo.is_minified) {
            node.classList.add('tree-node-minified');
        } else if (fileInfo.is_database) {
            node.classList.add('tree-node-database');
        }

        // 创建节点内容
        const content = document.createElement('div');
        content.className = 'tree-node-content';

        // 根据选中状态设置样式
        if (fileInfo.selected) {
            content.classList.add('tree-node-selected');
        }

        // 文件图标
        const icon = document.createElement('span');
        icon.className = this.getFileIconClass(fileInfo.file_type);

        // 文件名称
        const label = document.createElement('span');
        label.className = 'tree-node-label';
        label.textContent = fileInfo.selected ? `✓ ${fileName}` : fileName;

        // 文件信息
        const info = document.createElement('div');
        info.className = 'tree-node-info';

        // 文件类型
        const type = document.createElement('span');
        type.textContent = fileInfo.file_type || '-';

        // 文件大小
        const size = document.createElement('span');
        size.textContent = window.app.formatFileSize(fileInfo.size);

        // 文件行数
        const lines = document.createElement('span');
        lines.textContent = fileInfo.line_count || '-';

        // 添加信息元素
        info.appendChild(type);
        info.appendChild(size);
        info.appendChild(lines);

        // 将元素添加到内容
        content.appendChild(icon);
        content.appendChild(label);
        content.appendChild(info);
        node.appendChild(content);

        // 左键点击 - 选择文件
        content.addEventListener('click', (event) => {
            // 只有当左键点击时才切换选择状态
            if (!fileInfo.is_dir) {
                fileInfo.selected = !fileInfo.selected;
                this.updateNodeSelection(fileInfo);

                // 触发选择状态变更回调
                if (this.onSelectionChangeCallback) {
                    this.onSelectionChangeCallback(fileInfo, fileInfo.selected);
                }
            }

            // 触发节点选择回调（预览功能）
            if (this.onSelectCallback) {
                this.onSelectCallback(fileInfo);
            }
        });

        // 阻止文件节点上的右键菜单默认行为
        content.addEventListener('contextmenu', (event) => {
            event.preventDefault();
            event.stopPropagation();

            // 仅显示上下文菜单，不改变选择状态
            this.showContextMenuForNode(node, fileInfo, event.clientX, event.clientY);
        });

        return node;
    }


    /**
     * 为节点显示上下文菜单
     */
    showContextMenuForNode(node, fileInfo, x, y) {
        let options = [];

        if (fileInfo.is_dir) {
            // 目录上下文菜单
            options = [
                {
                    id: 'folder-ops',
                    label: "文件夹操作",
                    icon: "fas fa-folder",
                    submenu: [
                        {
                            label: "选择此文件夹下所有文件",
                            icon: "fas fa-check",
                            action: () => this.selectFolderFiles(node, true)
                        },
                        {
                            label: "取消选择此文件夹下所有文件",
                            icon: "fas fa-times",
                            action: () => this.selectFolderFiles(node, false)
                        },
                        {type: "separator"},
                        {
                            label: "展开此文件夹",
                            icon: "fas fa-folder-open",
                            action: () => this.expandNode(node)
                        },
                        {
                            label: "折叠此文件夹",
                            icon: "fas fa-folder",
                            action: () => {
                                const folder = node.querySelector('.tree-folder');
                                if (folder) {
                                    folder.style.display = 'none';
                                    const icon = node.querySelector('.tree-node-icon');
                                    if (icon) {
                                        icon.className = 'tree-node-icon fas fa-folder';
                                    }
                                }
                            }
                        }
                    ]
                },
                {type: "separator"},
                {
                    label: "展开选中项",
                    icon: "fas fa-expand",
                    action: () => this.expandNode(node)
                },
                {
                    label: "折叠选中项",
                    icon: "fas fa-compress",
                    action: () => {
                        const folder = node.querySelector('.tree-folder');
                        if (folder) {
                            folder.style.display = 'none';
                            const icon = node.querySelector('.tree-node-icon');
                            if (icon) {
                                icon.className = 'tree-node-icon fas fa-folder';
                            }
                        }
                    }
                }
            ];
        } else {
            // 文件上下文菜单
            const isSelected = fileInfo.selected;

            options = [
                {
                    label: isSelected ? "取消选择" : "选择用于复制",
                    icon: isSelected ? "fas fa-times" : "fas fa-check",
                    action: () => {
                        // 这里我们不改变选择状态，而是通过菜单操作改变
                        fileInfo.selected = !fileInfo.selected;
                        this.updateNodeSelection(fileInfo);

                        // 触发选择状态变更回调
                        if (this.onSelectionChangeCallback) {
                            this.onSelectionChangeCallback(fileInfo, fileInfo.selected);
                        }
                    }
                },
                {type: "separator"}
            ];

            // 添加特殊文件类型选项
            if (fileInfo.is_cdn || fileInfo.is_minified || fileInfo.is_database) {
                let specialOptions = [];

                if (fileInfo.is_cdn) {
                    specialOptions.push({
                        label: "选择所有CDN文件",
                        icon: "fas fa-globe",
                        action: () => this.selectByCondition(f => f.is_cdn)
                    });
                }

                if (fileInfo.is_minified) {
                    specialOptions.push({
                        label: "选择所有压缩文件",
                        icon: "fas fa-compress-alt",
                        action: () => this.selectByCondition(f => f.is_minified)
                    });
                }

                if (fileInfo.is_database) {
                    specialOptions.push({
                        label: "选择所有数据库文件",
                        icon: "fas fa-database",
                        action: () => this.selectByCondition(f => f.is_database)
                    });
                }

                if (specialOptions.length > 0) {
                    options.push({
                        id: 'special-ops',
                        label: "特殊文件操作",
                        icon: "fas fa-cog",
                        submenu: specialOptions
                    });

                    options.push({type: "separator"});
                }
            }

            // 添加预览操作
            options.push({
                label: "预览文件",
                icon: "fas fa-eye",
                action: () => {
                    if (this.onSelectCallback) {
                        this.onSelectCallback(fileInfo);
                    }
                }
            });
        }

        // 显示上下文菜单
        this.contextMenu.showMenu(x, y, options, node);
    }

    /**
     * 切换文件夹的展开/折叠状态
     * @param {HTMLElement} node - 目录节点
     * @param {HTMLElement} icon - 图标元素
     */
    toggleFolder(node, icon) {
        const folder = node.querySelector('.tree-folder');
        const isExpanded = folder.style.display !== 'none';

        if (isExpanded) {
            // 折叠
            folder.style.display = 'none';
            icon.className = 'tree-node-icon fas fa-folder';
        } else {
            // 展开
            folder.style.display = 'block';
            icon.className = 'tree-node-icon fas fa-folder-open';
        }
    }

    /**
     * 选择节点
     * @param {HTMLElement} node - 节点元素
     * @param {Object} fileInfo - 文件信息
     */
    selectNode(node, fileInfo) {
        // 如果有回调，则触发
        if (this.onSelectCallback) {
            this.onSelectCallback(fileInfo);
        }

        // 如果是文件，则切换选择状态
        if (!fileInfo.is_dir) {
            fileInfo.selected = !fileInfo.selected;
            this.updateNodeSelection(fileInfo);

            // 触发选择状态变更回调
            if (this.onSelectionChangeCallback) {
                this.onSelectionChangeCallback(fileInfo, fileInfo.selected);
            }
        }
    }

    /**
     * 更新节点的选择状态
     * @param {Object} fileInfo - 文件信息
     */
    updateNodeSelection(fileInfo) {
        const nodeData = this.nodeMap.get(fileInfo.path);
        if (!nodeData) return;

        const node = nodeData.node;
        const content = node.querySelector('.tree-node-content');
        const label = node.querySelector('.tree-node-label');

        if (fileInfo.selected) {
            content.classList.add('tree-node-selected');
            label.textContent = `✓ ${label.textContent.replace(/^✓\s*/, '')}`;
        } else {
            content.classList.remove('tree-node-selected');
            label.textContent = label.textContent.replace(/^✓\s*/, '');
        }
    }

    /**
     * 根据文件类型获取图标类
     * @param {string} fileType - 文件类型
     * @returns {string} - 图标类名
     */
    getFileIconClass(fileType) {
        // 根据文件类型返回不同的图标类
        const fileIconMap = {
            // 代码文件
            'py': 'fab fa-python',
            'js': 'fab fa-js',
            'html': 'fab fa-html5',
            'css': 'fab fa-css3',
            'php': 'fab fa-php',
            'java': 'fab fa-java',
            'c': 'fas fa-file-code',
            'cpp': 'fas fa-file-code',
            'cs': 'fas fa-file-code',
            'go': 'fas fa-file-code',
            'rb': 'fas fa-gem',
            'swift': 'fas fa-file-code',
            'ts': 'fas fa-file-code',
            'jsx': 'fab fa-react',
            'tsx': 'fab fa-react',

            // 数据文件
            'json': 'fas fa-file-code',
            'xml': 'fas fa-file-code',
            'yml': 'fas fa-file-alt',
            'yaml': 'fas fa-file-alt',
            'sql': 'fas fa-database',

            // 文档文件
            'md': 'fas fa-file-alt',
            'txt': 'fas fa-file-alt',
            'pdf': 'fas fa-file-pdf',
            'doc': 'fas fa-file-word',
            'docx': 'fas fa-file-word',
            'xls': 'fas fa-file-excel',
            'xlsx': 'fas fa-file-excel',

            // 配置文件
            'conf': 'fas fa-cog',
            'ini': 'fas fa-cog',
            'config': 'fas fa-cog',
            'gradle': 'fas fa-cog',

            // 脚本文件
            'sh': 'fas fa-terminal',
            'bat': 'fas fa-terminal',
            'ps1': 'fas fa-terminal',

            // 其他类型
            'zip': 'fas fa-file-archive',
            'rar': 'fas fa-file-archive',
            'tar': 'fas fa-file-archive',
            'gz': 'fas fa-file-archive',
            'jpg': 'fas fa-file-image',
            'jpeg': 'fas fa-file-image',
            'png': 'fas fa-file-image',
            'gif': 'fas fa-file-image',
            'svg': 'fas fa-file-image'
        };

        // 返回对应类型的图标，如果没有找到则返回默认图标
        return `tree-node-icon ${fileIconMap[fileType] || 'fas fa-file'}`;
    }

    /**
     * 排序文件列表
     * @param {Array} files - 文件列表
     * @param {string} sortKey - 排序方式
     * @returns {Array} - 排序后的文件列表
     */
    sortFiles(files, sortKey) {
        const sortedFiles = [...files];

        switch (sortKey) {
            case 'folder_first':
                // 先按是否为目录排序（目录在前），再按路径排序
                sortedFiles.sort((a, b) => {
                    if (a.is_dir !== b.is_dir) {
                        return a.is_dir ? -1 : 1;
                    }
                    return a.path.toLowerCase().localeCompare(b.path.toLowerCase());
                });
                break;

            case 'name':
                // 纯按名称排序
                sortedFiles.sort((a, b) => {
                    const nameA = a.path.split('/').pop().toLowerCase();
                    const nameB = b.path.split('/').pop().toLowerCase();
                    return nameA.localeCompare(nameB);
                });
                break;

            case 'type':
                // 按文件类型排序
                sortedFiles.sort((a, b) => {
                    if (a.is_dir !== b.is_dir) {
                        return a.is_dir ? -1 : 1;
                    }
                    const typeA = a.is_dir ? '' : a.file_type.toLowerCase();
                    const typeB = b.is_dir ? '' : b.file_type.toLowerCase();
                    if (typeA === typeB) {
                        return a.path.toLowerCase().localeCompare(b.path.toLowerCase());
                    }
                    return typeA.localeCompare(typeB);
                });
                break;

            case 'size':
                // 按文件大小排序（从大到小）
                sortedFiles.sort((a, b) => {
                    if (a.is_dir !== b.is_dir) {
                        return a.is_dir ? -1 : 1;
                    }
                    if (a.is_dir && b.is_dir) {
                        return a.path.toLowerCase().localeCompare(b.path.toLowerCase());
                    }
                    return b.size - a.size;
                });
                break;

            case 'lines':
                // 按行数排序（从多到少）
                sortedFiles.sort((a, b) => {
                    if (a.is_dir !== b.is_dir) {
                        return a.is_dir ? -1 : 1;
                    }
                    if (a.is_dir && b.is_dir) {
                        return a.path.toLowerCase().localeCompare(b.path.toLowerCase());
                    }
                    return b.line_count - a.line_count;
                });
                break;

            default:
                // 默认排序方式
                sortedFiles.sort((a, b) => {
                    if (a.is_dir !== b.is_dir) {
                        return a.is_dir ? -1 : 1;
                    }
                    return a.path.toLowerCase().localeCompare(b.path.toLowerCase());
                });
        }

        return sortedFiles;
    }

    /**
     * 过滤树节点
     * @param {string} searchText - 搜索文本
     */
    filterTree(searchText) {
        if (!searchText) {
            // 如果搜索文本为空，显示所有节点
            this.resetAllNodesVisibility();
            return;
        }

        // 搜索并只显示匹配的节点
        searchText = searchText.toLowerCase();

        // 遍历所有节点
        this.nodeMap.forEach((nodeData, path) => {
            const node = nodeData.node;
            const file = nodeData.data;

            // 获取文件名
            const fileName = file.path.split('/').pop().toLowerCase();

            // 检查是否匹配
            const match = fileName.includes(searchText);

            // 设置可见性
            if (file.is_dir) {
                // 如果是目录，只有当搜索文本为空或其子节点中有匹配项时才显示
                if (this.hasMatchingChild(node, searchText)) {
                    node.style.display = '';
                    // 确保父节点也可见
                    this.ensureParentVisible(file.path);
                    // 展开目录以显示匹配的子节点
                    this.expandNode(node);
                } else {
                    node.style.display = 'none';
                }
            } else {
                // 如果是文件，根据匹配结果设置可见性
                node.style.display = match ? '' : 'none';

                // 如果匹配，确保父节点可见
                if (match) {
                    this.ensureParentVisible(file.path);
                }
            }
        });
    }

    /**
     * 检查节点是否有匹配的子节点
     * @param {HTMLElement} node - 节点元素
     * @param {string} searchText - 搜索文本
     * @returns {boolean} - 是否有匹配的子节点
     */
    hasMatchingChild(node, searchText) {
        const folder = node.querySelector('.tree-folder');
        if (!folder) return false;

        const childNodes = folder.querySelectorAll('.tree-node');
        for (const childNode of childNodes) {
            const path = childNode.dataset.path;
            const nodeData = this.nodeMap.get(path);
            if (!nodeData) continue;

            const file = nodeData.data;
            const fileName = file.path.split('/').pop().toLowerCase();

            if (fileName.includes(searchText)) {
                return true;
            }

            // 如果是目录，递归检查子节点
            if (file.is_dir && this.hasMatchingChild(childNode, searchText)) {
                return true;
            }
        }

        return false;
    }

    /**
     * 确保父节点可见
     * @param {string} path - 文件路径
     */
    ensureParentVisible(path) {
        const parts = path.split('/');
        if (parts.length <= 1) return;

        const parentPath = parts.slice(0, -1).join('/');
        const parentData = this.nodeMap.get(parentPath);

        if (parentData) {
            const parentNode = parentData.node;
            parentNode.style.display = '';
            this.expandNode(parentNode);

            // 递归确保上层节点也可见
            this.ensureParentVisible(parentPath);
        }
    }

    /**
     * 展开节点
     * @param {HTMLElement} node - 节点元素
     */
    expandNode(node) {
        const folder = node.querySelector('.tree-folder');
        if (folder) {
            folder.style.display = 'block';

            // 更新图标
            const icon = node.querySelector('.tree-node-icon');
            if (icon) {
                icon.className = 'tree-node-icon fas fa-folder-open';
            }
        }
    }

    /**
     * 重置所有节点的可见性
     */
    resetAllNodesVisibility() {
        this.nodeMap.forEach((nodeData) => {
            nodeData.node.style.display = '';
        });
    }

    /**
     * 展开所有节点
     */
    expandAll() {
        this.nodeMap.forEach((nodeData, path) => {
            const node = nodeData.node;
            const file = nodeData.data;

            if (file.is_dir) {
                const folder = node.querySelector('.tree-folder');
                const icon = node.querySelector('.tree-node-icon');

                if (folder) {
                    folder.style.display = 'block';
                }

                if (icon) {
                    icon.className = 'tree-node-icon fas fa-folder-open';
                }
            }
        });
    }

    /**
     * 折叠所有节点
     */
    collapseAll() {
        this.nodeMap.forEach((nodeData, path) => {
            const node = nodeData.node;
            const file = nodeData.data;

            if (file.is_dir) {
                const folder = node.querySelector('.tree-folder');
                const icon = node.querySelector('.tree-node-icon');

                if (folder) {
                    folder.style.display = 'none';
                }

                if (icon) {
                    icon.className = 'tree-node-icon fas fa-folder';
                }
            }
        });
    }

    /**
     * 根据条件选择文件
     * @param {Function} conditionFn - 条件函数
     * @returns {number} - 选择的文件数量
     */
    selectByCondition(conditionFn) {
        let count = 0;

        this.files.forEach(file => {
            if (!file.is_dir && conditionFn(file) && !file.selected) {
                file.selected = true;
                this.updateNodeSelection(file);
                count++;

                // 触发选择状态变更回调
                if (this.onSelectionChangeCallback) {
                    this.onSelectionChangeCallback(file, true);
                }
            }
        });

        return count;
    }

    /**
     * 根据条件取消选择文件
     * @param {Function} conditionFn - 条件函数
     * @returns {number} - 取消选择的文件数量
     */
    deselectByCondition(conditionFn) {
        let count = 0;

        this.files.forEach(file => {
            if (!file.is_dir && conditionFn(file) && file.selected) {
                file.selected = false;
                this.updateNodeSelection(file);
                count++;

                // 触发选择状态变更回调
                if (this.onSelectionChangeCallback) {
                    this.onSelectionChangeCallback(file, false);
                }
            }
        });

        return count;
    }

    /**
     * 反转文件的选择状态
     * @returns {number} - 反转选择状态的文件数量
     */
    invertSelection() {
        let count = 0;

        this.files.forEach(file => {
            if (!file.is_dir) {
                file.selected = !file.selected;
                this.updateNodeSelection(file);
                count++;

                // 触发选择状态变更回调
                if (this.onSelectionChangeCallback) {
                    this.onSelectionChangeCallback(file, file.selected);
                }
            }
        });

        return count;
    }

    /**
     * 获取选中的文件
     * @returns {Array} - 选中的文件列表
     */
    getSelectedFiles() {
        return this.files.filter(file => !file.is_dir && file.selected);
    }

    /**
     * 获取可见节点数量
     * @returns {number} - 可见节点数量
     */
    getVisibleNodesCount() {
        let count = 0;

        this.nodeMap.forEach((nodeData) => {
            if (nodeData.node.style.display !== 'none') {
                count++;
            }
        });

        return count;
    }

    /**
     * 展开到指定深度
     * @param {number} depth - 深度
     */
    expandToDepth(depth) {
        // 重置所有节点状态
        this.collapseAll();

        // 如果深度为0，则直接返回
        if (depth <= 0) return;

        // 展开到指定深度
        this.files.forEach(file => {
            if (file.is_dir) {
                const pathDepth = file.path.split('/').length;
                if (pathDepth <= depth) {
                    const nodeData = this.nodeMap.get(file.path);
                    if (nodeData) {
                        this.expandNode(nodeData.node);
                    }
                }
            }
        });
    }

    /**
     * 清空树
     */
    clear() {
        this.container.innerHTML = '';
        this.nodeMap.clear();
        this.files = [];
    }

    /**
     * Recursively get the text representation of a node with box drawing characters
     * @param {HTMLElement} node - Node element
     * @param {string} indent - Current indentation
     * @param {boolean} isLast - Whether this is the last child in its parent
     * @returns {string} - Node's text representation
     */
    _getNodeText(node, indent = "", isLast = true) {
        if (!node.classList || !node.classList.contains('tree-node')) {
            return '';
        }

        const path = node.dataset.path;
        const isDir = node.dataset.isDir === 'true';
        const name = path.split('/').pop();
        let text = '';

        // Box drawing characters for prettier output
        const boxChars = {
            branch: '├── ',
            corner: '└── ',
            vertical: '│   ',
            empty: '    '
        };

        // Determine the prefix based on whether this is the last item
        const prefix = isLast ? boxChars.corner : boxChars.branch;

        if (isDir) {
            text += indent + prefix + name + '/\n';

            // Process child nodes
            const childNodes = Array.from(node.querySelector('.tree-folder')?.childNodes || [])
                .filter(n => n.classList && n.classList.contains('tree-node'));

            // Generate new indent for children
            const newIndent = indent + (isLast ? boxChars.empty : boxChars.vertical);

            // Process all child nodes
            childNodes.forEach((childNode, index) => {
                const isLastChild = index === childNodes.length - 1;
                text += this._getNodeText(childNode, newIndent, isLastChild);
            });
        } else {
            const nodeData = this.nodeMap.get(path);
            const file = nodeData?.data;

            // Add line count info if available
            let infoStr = '';
            if (file && file.line_count > 0) {
                infoStr = ` (${file.line_count}行)`;
            }

            text += indent + prefix + name + infoStr + '\n';
        }

        return text;
    }


    /**
     * Get the tree's text representation with box drawing characters
     * @returns {string} - Tree's text representation
     */
    getTreeText() {
        // Get folder path
        const folderPath = document.getElementById('folderPath').value;
        let structureText = '';

        if (folderPath) {
            // 修复路径处理方式，确保只显示项目文件夹名称
            const normalizedPath = folderPath.replace(/\\/g, '/');
            const folderName = normalizedPath.split('/').filter(part => part).pop();
            structureText += `${folderName}/\n`;
        }

        // Get top-level nodes
        const rootNodes = Array.from(this.container.querySelector('.tree-root')?.childNodes || [])
            .filter(n => n.classList && n.classList.contains('tree-node'));

        // Process all top-level nodes
        rootNodes.forEach((node, index) => {
            const isLast = index === rootNodes.length - 1;
            structureText += this._getNodeText(node, '', isLast);
        });

        return structureText;
    }

    /**
     * 设置节点选择回调
     * @param {Function} callback - 回调函数
     */
    onNodeSelect(callback) {
        this.onSelectCallback = callback;
    }

    /**
     * 设置选择状态变更回调
     * @param {Function} callback - 回调函数
     */
    onSelectionChange(callback) {
        this.onSelectionChangeCallback = callback;
    }
}