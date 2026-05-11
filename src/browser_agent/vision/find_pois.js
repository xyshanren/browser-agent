/**
 * find_pois.js — 网页交互元素（POI）检测引擎 + DOM Dehydration
 * 
 * 从 convergence-ai/proxy-lite 移植并精简。
 * 注入到页面后，通过 findPOIsConvergence() 函数检测所有可交互元素。
 * 
 * 检测策略：
 * 1. 标签匹配（a, button, input, select, textarea, ...）
 * 2. ARIA 角色匹配（role="button", role="link", ...）
 * 3. 事件监听器匹配（onclick, addEventListener('click'), ...）
 * 4. 属性匹配（tabindex, contenteditable, ...）
 * 5. 可滚动元素（overflow: scroll/auto）
 * 6. Shadow DOM 穿透
 * 
 * DOM Dehydration 增强：
 * - 层级缩进：输出父子元素关系（缩进表示深度）
 * - 新元素标记：*[ 标记自上次快照以来新出现的元素
 * - 指纹追踪：通过 tag+text+位置 生成唯一指纹，跨步骤比对
 */

marked_elements_convergence = [];

/* ── DOM Dehydration: 跨步骤新元素检测 ── */
if (typeof _poi_fingerprints === 'undefined') {
    _poi_fingerprints = new Set();
}

const interactiveTags = new Set([
    'a', 'button', 'details', 'embed', 'input', 'label',
    'menu', 'menuitem', 'object', 'select', 'textarea', 'summary',
    'video', 'audio', 'option', 'iframe'
]);

const interactiveRoles = new Set([
    'button', 'menu', 'menuitem', 'link', 'checkbox', 'radio',
    'slider', 'tab', 'tabpanel', 'textbox', 'combobox', 'grid',
    'listbox', 'option', 'progressbar', 'scrollbar', 'searchbox',
    'switch', 'tree', 'treeitem', 'spinbutton', 'tooltip',
    'a-button-inner', 'a-dropdown-button', 'click',
    'menuitemcheckbox', 'menuitemradio', 'a-button-text',
    'button-text', 'button-icon', 'button-icon-only',
    'button-text-icon-only', 'dropdown'
]);

findPOIsConvergence = (input = null) => {
    let rootElement = input ? input : document.documentElement;

    function isScrollable(element) {
        if (input === null && element === document.documentElement) return false;
        const style = window.getComputedStyle(element);
        return (element.scrollHeight > element.clientHeight && 
                (style.overflowY === 'scroll' || style.overflowY === 'auto')) ||
               (element.scrollWidth > element.clientWidth && 
                (style.overflowX === 'scroll' || style.overflowX === 'auto'));
    }

    function isInteractive(element) {
        if (!element) return false;
        return interactiveTags.has(element.tagName.toLowerCase()) ||
               hasInteractiveAttributes(element) ||
               hasInteractiveEventListeners(element) ||
               isScrollable(element);
    }

    function hasInteractiveAttributes(element) {
        const role = element.getAttribute('role');
        const tabIndex = element.getAttribute('tabindex');

        if (element.getAttribute('contenteditable') === 'true') return true;
        if (role && interactiveRoles.has(role)) return true;
        if (tabIndex !== null && tabIndex !== '-1') return true;

        return element.hasAttribute('aria-expanded') ||
               element.hasAttribute('aria-pressed') ||
               element.hasAttribute('aria-selected') ||
               element.hasAttribute('aria-checked');
    }

    function hasInteractiveEventListeners(element) {
        const hasClickHandler = element.onclick !== null ||
            element.getAttribute('onclick') !== null ||
            element.hasAttribute('ng-click') ||
            element.hasAttribute('@click') ||
            element.hasAttribute('v-on:click');
        if (hasClickHandler) return true;
        return false;
    }

    function isElementVisible(element) {
        const style = window.getComputedStyle(element);
        return element.offsetWidth > 0 && element.offsetHeight > 0 &&
               style.visibility !== 'hidden' && style.display !== 'none';
    }

    function isTopElement(element) {
        const rect = element.getBoundingClientRect();
        const point = { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
        try {
            const topEl = document.elementFromPoint(point.x, point.y);
            if (!topEl) return false;
            let current = topEl;
            while (current && current !== document.documentElement) {
                if (current === element) return true;
                current = current.parentElement;
            }
            return false;
        } catch (e) {
            return true;
        }
    }

    function getVisibleText(element) {
        const style = window.getComputedStyle(element);
        if (style.display === 'none' || style.visibility === 'hidden') return '';
        return (element.textContent || '').trim().replace(/\s{2,}/g, ' ').slice(0, 200);
    }

    /**
     * 为元素生成唯一指纹，用于跨步骤新元素检测。
     * 指纹 = tagName + 可见文本 hash + 角色 + 粗略位置
     */
    function makeFingerprint(element, depth) {
        const tag = element.tagName.toLowerCase();
        const text = getVisibleText(element).slice(0, 60);
        const role = element.getAttribute('role') || '';
        const rect = element.getBoundingClientRect();
        const areaKey = Math.round(rect.width / 20) + 'x' + Math.round(rect.height / 20);
        return tag + '|' + text + '|' + role + '|' + areaKey + '|d' + depth;
    }

    function extractInteractiveItems(rootElement) {
        const items = [];

        function processElement(element, depth) {
            if (!element || element.nodeType !== Node.ELEMENT_NODE) return;
            depth = depth || 0;

            if (isInteractive(element) && isElementVisible(element) && isTopElement(element)) {
                const rect = element.getBoundingClientRect();
                items.push({
                    element: element,
                    area: rect.width * rect.height,
                    rect: rect,
                    depth: depth,
                    is_scrollable: isScrollable(element),
                });
            }

            // Shadow DOM 穿透
            if (element.shadowRoot) {
                Array.from(element.shadowRoot.children || []).forEach(child => {
                    processElement(child, depth + 1);
                });
            }

            // iframe 穿透
            if (element.tagName === 'IFRAME') {
                try {
                    const iframeDoc = element.contentDocument || element.contentWindow?.document;
                    if (iframeDoc && iframeDoc.body) {
                        processElement(iframeDoc.body, depth + 1);
                    }
                } catch (e) { /* cross-origin iframe */ }
            }

            // 常规子元素
            Array.from(element.children || []).forEach(child => {
                processElement(child, depth + 1);
            });
        }

        processElement(rootElement, 0);
        return items;
    }

    // ── 主逻辑 ──
    marked_elements_convergence = [];
    let mark_centres = [];
    let marked_element_descriptions = [];
    let items = extractInteractiveItems(rootElement);

    // 按面积排序，优先检测大的交互元素
    items.sort((a, b) => b.area - a.area);

    // 收集本次快照的指纹
    const currentFingerprints = new Set();

    items.forEach(function (item) {
        const el = item.element;
        const rect = item.rect;
        const cx = Math.round(rect.left + rect.width / 2);
        const cy = Math.round(rect.top + rect.height / 2);

        const fp = makeFingerprint(el, item.depth);
        currentFingerprints.add(fp);
        const isNew = !_poi_fingerprints.has(fp);

        marked_elements_convergence.push(item.element);
        mark_centres.push({
            x: cx, y: cy,
            left: Math.round(rect.left),
            top: Math.round(rect.top),
            right: Math.round(rect.right),
            bottom: Math.round(rect.bottom),
        });

        const desc = {
            tag: el.tagName,
            text: getVisibleText(el),
            value: el.value,
            placeholder: el.getAttribute("placeholder"),
            aria_label: el.getAttribute("aria-label"),
            type: el.getAttribute("type"),
            name: el.getAttribute("name"),
            role: el.getAttribute("role"),
            title: el.getAttribute("title"),
            scrollable: item.is_scrollable,
            required: !!el.getAttribute("required"),
            disabled: !!el.getAttribute("disabled"),
            is_new: isNew,
            depth: item.depth,
        };
        marked_element_descriptions.push(desc);
    });

    // 更新指纹集（保留最近 200 个指纹，防止内存膨胀）
    _poi_fingerprints = new Set([...currentFingerprints, ..._poi_fingerprints].slice(-200));

    // ── 构建 DOM Dehydration 文本 ──
    const dehydratedLines = [];
    for (let i = 0; i < marked_element_descriptions.length; i++) {
        const d = marked_element_descriptions[i];
        const indent = '  '.repeat(d.depth);
        const prefix = d.is_new ? '*[' : '[';
        const suffix = d.is_new ? ']' : ']';
        const tagDisplay = d.tag.toLowerCase();
        let label = '';
        if (d.type && ['text', 'search', 'email', 'password', 'url'].includes(d.type)) {
            label = d.placeholder || d.aria_label || d.text || '';
        } else {
            label = d.aria_label || d.text || d.name || '';
        }
        const labelDisplay = label ? ` "${label.slice(0, 100)}"` : '';
        const extraFlags = [];
        if (d.scrollable) extraFlags.push('scrollable');
        if (d.disabled) extraFlags.push('disabled');
        const flagsStr = extraFlags.length ? ` [${extraFlags.join(',')}]` : '';
        dehydratedLines.push(`${indent}${prefix}${i}${suffix} <${tagDisplay}>${labelDisplay}${flagsStr}`);
    }

    return {
        element_descriptions: marked_element_descriptions,
        element_centroids: mark_centres,
        dehydrated_dom: dehydratedLines.join('\n'),
        poi_count: marked_element_descriptions.length,
        new_count: marked_element_descriptions.filter(d => d.is_new).length,
    };
};
