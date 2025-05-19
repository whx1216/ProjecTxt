/**
 * 文件查看器组件
 * 用于显示文件内容，支持代码高亮
 */
class FileViewer {
    constructor(elements) {
        this.elements = elements;
        this.currentFile = null;

        // 初始化复制按钮事件
        this.elements.copyBtn.addEventListener('click', () => this.copyContent());
    }

    /**
     * 显示文件内容
     * @param {Object} file - 文件信息
     * @param {string} highlightedCode - 高亮后的代码HTML
     * @param {string} css - 高亮代码的CSS样式
     */
    displayFile(file, highlightedCode = null, css = null) {
        if (!file) return;

        this.currentFile = file;

        // 隐藏无选择提示，显示文件预览
        this.elements.noSelection.style.display = 'none';
        this.elements.filePreview.style.display = 'flex';

        // 设置文件名和信息
        this.elements.fileName.textContent = file.path;
        this.elements.fileInfo.textContent = `(${file.line_count}行, ${file.char_count}字符)`;

        // 清空标签容器
        this.elements.fileTags.innerHTML = '';

        // 添加特殊标签
        if (file.is_cdn) {
            this.addTag('CDN', 'tag-cdn');
        }

        if (file.is_minified) {
            this.addTag('压缩', 'tag-minified');
        }

        if (file.is_database) {
            this.addTag('数据库', 'tag-database');
        }

        // 显示文件内容
        if (file.is_text) {
            // 如果有高亮代码，使用高亮显示，否则使用普通文本
            if (highlightedCode) {
                // 添加样式标签
                let styleTag = document.getElementById('highlight-styles');
                if (!styleTag) {
                    styleTag = document.createElement('style');
                    styleTag.id = 'highlight-styles';
                    document.head.appendChild(styleTag);
                }
                styleTag.textContent = css;

                // 设置高亮HTML
                this.elements.codeContainer.innerHTML = highlightedCode;
            } else {
                // 使用预格式化文本显示
                this.elements.codeContainer.innerHTML = `
                    <pre style="margin:0;padding:10px;white-space:pre-wrap;word-break:break-all;">${this.escapeHtml(file.content)}</pre>
                `;
            }
        } else {
            // 如果不是文本文件
            this.elements.codeContainer.innerHTML = `
                <div style="padding:20px;text-align:center;color:var(--text-secondary);">
                    <i class="fas fa-file-alt" style="font-size:32px;margin-bottom:10px;"></i>
                    <p>此文件不是文本文件或无法显示内容</p>
                </div>
            `;
        }
    }

    /**
     * 添加标签
     * @param {string} text - 标签文本
     * @param {string} className - 标签类名
     */
    addTag(text, className) {
        const tag = document.createElement('span');
        tag.className = `file-tag ${className}`;
        tag.textContent = text;
        this.elements.fileTags.appendChild(tag);
    }

    /**
     * 复制当前文件内容到剪贴板
     */
    copyContent() {
        if (!this.currentFile || !this.currentFile.content) return;

        navigator.clipboard.writeText(this.currentFile.content)
            .then(() => {
                // 显示复制成功提示
                const statusMessage = document.getElementById('statusMessage');
                if (statusMessage) {
                    statusMessage.textContent = `已复制 ${this.currentFile.path} 的内容到剪贴板`;
                    setTimeout(() => {
                        statusMessage.textContent = '';
                    }, 2000);
                }
            })
            .catch(err => {
                console.error('Failed to copy:', err);
            });
    }

    /**
     * 清空文件查看器
     */
    clear() {
        this.currentFile = null;
        this.elements.noSelection.style.display = 'flex';
        this.elements.filePreview.style.display = 'none';
        this.elements.fileName.textContent = '';
        this.elements.fileInfo.textContent = '';
        this.elements.fileTags.innerHTML = '';
        this.elements.codeContainer.innerHTML = '';
    }

    /**
     * HTML转义
     * @param {string} text - 待转义的文本
     * @returns {string} - 转义后的文本
     */
    escapeHtml(text) {
        if (!text) return '';
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, m => map[m]);
    }
}