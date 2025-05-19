/**
 * Context Menu Component
 * Provides right-click menu functionality similar to the Qt version
 */
class ContextMenuComponent {
    constructor() {
        this.menuElement = null;
        this.visible = false;
        this.currentNode = null;
        this.callbacks = {};

        // Create menu element
        this.createMenuElement();

        // Close menu on document click
        document.addEventListener('click', () => {
            if (this.visible) {
                this.hideMenu();
            }
        });
    }

    /**
     * Create the menu DOM element
     */
    createMenuElement() {
        // Remove existing menu if any
        if (this.menuElement) {
            document.body.removeChild(this.menuElement);
        }

        // Create menu container
        this.menuElement = document.createElement('div');
        this.menuElement.className = 'context-menu';
        this.menuElement.style.display = 'none';
        this.menuElement.addEventListener('click', (e) => {
            e.stopPropagation();
        });

        document.body.appendChild(this.menuElement);
    }

    /**
     * Show context menu
     * @param {number} x - X position
     * @param {number} y - Y position
     * @param {Object} options - Menu options
     * @param {HTMLElement} targetNode - Target node element
     */
    showMenu(x, y, options, targetNode) {
        this.currentNode = targetNode;

        // Clear existing menu items
        this.menuElement.innerHTML = '';

        // Add menu items
        options.forEach((option, index) => {
            if (option.type === 'separator') {
                const separator = document.createElement('div');
                separator.className = 'context-menu-separator';
                this.menuElement.appendChild(separator);
            } else {
                const item = document.createElement('div');
                item.className = 'context-menu-item';

                if (option.id) {
                    item.dataset.id = option.id;
                } else {
                    item.dataset.id = `item-${index}`;
                }

                if (option.disabled) {
                    item.classList.add('disabled');
                }

                // Add icon if provided
                if (option.icon) {
                    const icon = document.createElement('i');
                    icon.className = option.icon;
                    item.appendChild(icon);
                }

                // Add label
                const label = document.createElement('span');
                label.textContent = option.label;
                item.appendChild(label);

                // Add submenu indicator if it has submenu
                if (option.submenu && option.submenu.length > 0) {
                    const submenuIcon = document.createElement('i');
                    submenuIcon.className = 'fas fa-chevron-right submenu-icon';
                    item.appendChild(submenuIcon);

                    // Create the submenu container
                    const submenu = document.createElement('div');
                    submenu.className = 'context-submenu';

                    // Add submenu items
                    option.submenu.forEach(submenuItem => {
                        const subItem = document.createElement('div');
                        subItem.className = 'context-menu-item';

                        // Add icon if provided
                        if (submenuItem.icon) {
                            const subIcon = document.createElement('i');
                            subIcon.className = submenuItem.icon;
                            subItem.appendChild(subIcon);
                        }

                        // Add label
                        const subLabel = document.createElement('span');
                        subLabel.textContent = submenuItem.label;
                        subItem.appendChild(subLabel);

                        // Add click handler
                        if (!submenuItem.disabled && submenuItem.action) {
                            subItem.addEventListener('click', (e) => {
                                e.stopPropagation();
                                this.hideMenu();
                                submenuItem.action(this.currentNode);
                            });
                        }

                        submenu.appendChild(subItem);
                    });

                    item.appendChild(submenu);

                    // Show submenu on hover
                    item.addEventListener('mouseenter', () => {
                        submenu.style.display = 'block';
                    });

                    item.addEventListener('mouseleave', () => {
                        submenu.style.display = 'none';
                    });
                } else if (!option.disabled && option.action) {
                    // If no submenu but has action
                    item.addEventListener('click', (e) => {
                        e.stopPropagation();
                        this.hideMenu();
                        option.action(this.currentNode);
                    });
                }

                this.menuElement.appendChild(item);
            }
        });

        // Position menu
        this.menuElement.style.left = `${x}px`;
        this.menuElement.style.top = `${y}px`;

        // Show menu
        this.menuElement.style.display = 'block';
        this.visible = true;

        // Adjust position if menu goes out of viewport
        const rect = this.menuElement.getBoundingClientRect();
        if (rect.right > window.innerWidth) {
            this.menuElement.style.left = `${x - rect.width}px`;
        }
        if (rect.bottom > window.innerHeight) {
            this.menuElement.style.top = `${y - rect.height}px`;
        }
    }

    /**
     * Hide menu
     */
    hideMenu() {
        this.menuElement.style.display = 'none';
        this.visible = false;
        this.currentNode = null;
    }
}