(function () {
    const csrfToken = () => document.querySelector('input[name="csrfmiddlewaretoken"]')?.value || '';

    const scrollToBottom = (node) => {
        if (node) {
            node.scrollTop = node.scrollHeight;
        }
    };

    const setError = (node, message) => {
        if (!node) {
            return;
        }
        node.textContent = message || '';
        node.classList.toggle('hidden', !message);
    };

    const autoResizeTextarea = (textarea) => {
        if (!textarea) {
            return;
        }
        textarea.style.height = 'auto';
        textarea.style.height = `${Math.min(textarea.scrollHeight, 144)}px`;
    };

    const createAssistantHighlights = (highlights = []) => {
        const values = (Array.isArray(highlights) ? highlights : []).filter(Boolean);
        if (!values.length) {
            return null;
        }
        const wrap = document.createElement('div');
        wrap.className = 'assistant-highlight-list';
        values.forEach((item) => {
            const chip = document.createElement('span');
            chip.className = 'assistant-highlight-chip';
            chip.textContent = item;
            wrap.appendChild(chip);
        });
        return wrap;
    };

    const createAssistantSuggestions = (suggestions = []) => {
        const values = (Array.isArray(suggestions) ? suggestions : []).filter((item) => item?.url && item?.label);
        if (!values.length) {
            return null;
        }
        const wrap = document.createElement('div');
        wrap.className = 'assistant-suggestion-row';
        values.forEach((item) => {
            const link = document.createElement('a');
            link.className = 'assistant-suggestion-link';
            link.href = item.url;
            link.textContent = item.label;
            wrap.appendChild(link);
        });
        return wrap;
    };

    const createAssistantBubble = ({ role, text, highlights = [], suggestions = [] }) => {
        const bubble = document.createElement('div');
        bubble.className = `assistant-bubble ${role === 'user' ? 'assistant-bubble--user' : 'assistant-bubble--assistant'}`;

        const label = document.createElement('p');
        label.className = `text-xs uppercase tracking-[0.24em] ${role === 'user' ? 'text-slate-500' : 'text-red-500'}`;
        label.textContent = role === 'user' ? 'You' : 'BayStays AI';
        bubble.appendChild(label);

        const body = document.createElement('p');
        body.className = 'mt-2 text-slate-700 whitespace-pre-line';
        body.textContent = text || '';
        bubble.appendChild(body);

        if (role !== 'user') {
            const highlightsNode = createAssistantHighlights(highlights);
            const suggestionNode = createAssistantSuggestions(suggestions);
            if (highlightsNode) {
                bubble.appendChild(highlightsNode);
            }
            if (suggestionNode) {
                bubble.appendChild(suggestionNode);
            }
        }

        return bubble;
    };

    const bindAssistantShell = (shell) => {
        if (!shell || shell.dataset.bound === 'true') {
            return;
        }
        shell.dataset.bound = 'true';
        const form = shell.querySelector('[data-assistant-form]');
        const transcript = shell.querySelector('[data-assistant-transcript]');
        const errorNode = shell.querySelector('[data-assistant-error]');
        if (!form || !transcript) {
            return;
        }
        const input = form.querySelector('textarea[name="prompt"]');
        autoResizeTextarea(input);
        input?.addEventListener('input', () => autoResizeTextarea(input));
        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            const button = form.querySelector('button[type="submit"]');
            const prompt = input?.value.trim();
            if (!prompt) {
                return;
            }
            button?.setAttribute('disabled', 'disabled');
            setError(errorNode, '');

            try {
                const response = await fetch(form.action, {
                    method: 'POST',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': csrfToken(),
                    },
                    body: new FormData(form),
                });
                const payload = await response.json();
                if (!response.ok || !payload.ok) {
                    setError(errorNode, payload.error || 'BayStays AI could not respond just now.');
                    return;
                }
                transcript.appendChild(createAssistantBubble({
                    role: 'user',
                    text: prompt,
                }));
                transcript.appendChild(createAssistantBubble({
                    role: 'assistant',
                    text: payload.response?.text || '',
                    highlights: payload.response?.highlights || [],
                    suggestions: payload.response?.suggestions || [],
                }));
                input.value = '';
                autoResizeTextarea(input);
                scrollToBottom(transcript);
                input?.focus({ preventScroll: true });
            } catch (error) {
                setError(errorNode, 'BayStays AI is unavailable right now. Please try again shortly.');
            } finally {
                button?.removeAttribute('disabled');
            }
        });
    };

    const initConversationThread = () => {
        document.querySelectorAll('[data-conversation-thread]').forEach((thread) => {
            if (thread.dataset.bound === 'true') {
                return;
            }
            thread.dataset.bound = 'true';
            const endpoint = thread.dataset.threadUrl;
            let currentVersion = thread.dataset.threadVersion || 'none';
            const form = document.querySelector('[data-conversation-form]');
            const errorNode = form?.querySelector('[data-conversation-error]');
            let fallbackIntervalId = null;

            const refresh = async (force = false) => {
                if (!endpoint || document.hidden) {
                    return;
                }
                try {
                    const response = await fetch(endpoint, {
                        headers: {
                            'X-Requested-With': 'XMLHttpRequest',
                        },
                    });
                    const payload = await response.json();
                    if (!response.ok) {
                        setError(errorNode, payload.error || 'We could not refresh this conversation right now.');
                        return;
                    }
                    if (!force && payload.version === currentVersion) {
                        return;
                    }
                    thread.innerHTML = payload.html;
                    currentVersion = payload.version || currentVersion;
                    setError(errorNode, '');
                    scrollToBottom(thread);
                } catch (error) {
                    // keep the last good thread state
                }
            };

            form?.addEventListener('submit', async (event) => {
                event.preventDefault();
                const input = form.querySelector('textarea[name="body"]');
                const button = form.querySelector('button[type="submit"]');
                if (!input?.value.trim()) {
                    return;
                }
                button?.setAttribute('disabled', 'disabled');
                setError(errorNode, '');
                try {
                    const response = await fetch(form.action, {
                        method: 'POST',
                        headers: {
                            'X-Requested-With': 'XMLHttpRequest',
                            'X-CSRFToken': csrfToken(),
                        },
                        body: new FormData(form),
                    });
                    const payload = await response.json();
                    if (!response.ok || !payload.ok) {
                        setError(errorNode, payload.error || 'We could not send that message just now.');
                        return;
                    }
                    input.value = '';
                    await refresh(true);
                } catch (error) {
                    setError(errorNode, 'Your message was not sent. Please try again in a moment.');
                } finally {
                    button?.removeAttribute('disabled');
                }
            });

            const ensureFallbackPolling = () => {
                if (fallbackIntervalId !== null) {
                    return;
                }
                fallbackIntervalId = window.setInterval(() => refresh(false), 5000);
            };

            const wsUrl = thread.dataset.wsUrl;
            if (wsUrl && typeof window.WebSocket === 'function') {
                try {
                    const socket = new window.WebSocket(wsUrl);
                    socket.addEventListener('message', () => refresh(true));
                    socket.addEventListener('close', () => ensureFallbackPolling());
                    socket.addEventListener('error', () => ensureFallbackPolling());
                } catch (error) {
                    ensureFallbackPolling();
                }
            } else {
                ensureFallbackPolling();
            }

            scrollToBottom(thread);
        });
    };

    const initAssistant = () => {
        document.querySelectorAll('[data-assistant-shell]').forEach((shell) => bindAssistantShell(shell));
    };

    const initAssistantWidget = () => {
        const shell = document.querySelector('[data-assistant-widget-shell]');
        if (!shell || shell.dataset.bound === 'true') {
            return;
        }
        shell.dataset.bound = 'true';
        const content = shell.querySelector('[data-assistant-widget-content]');
        const panel = shell.querySelector('.assistant-widget-panel');
        const widgetUrl = shell.dataset.widgetUrl;
        const backdrop = shell.querySelector('.assistant-widget-backdrop');
        const triggers = Array.from(document.querySelectorAll('[data-assistant-widget-toggle]'));
        let hasLoaded = false;
        let activeTrigger = null;
        const focusableSelector = 'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

        const syncTriggers = (isOpen) => {
            triggers.forEach((trigger) => {
                trigger.classList.toggle('is-open', isOpen);
                trigger.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
            });
            document.documentElement.classList.toggle('assistant-widget-open', isOpen);
            document.body.classList.toggle('assistant-widget-open', isOpen);
        };

        const syncWidgetFields = () => {
            content.querySelectorAll('input[name="path"]').forEach((input) => {
                input.value = window.location.pathname;
            });
        };

        const focusComposer = () => {
            const composer = content.querySelector('textarea[name="prompt"]');
            composer?.focus({ preventScroll: true });
            scrollToBottom(content.querySelector('[data-assistant-transcript]'));
        };

        const getFocusableNodes = () => Array.from(shell.querySelectorAll(focusableSelector)).filter((node) => !node.hasAttribute('hidden') && node.offsetParent !== null);

        const renderLoadingState = () => {
            content.innerHTML = `
                <div class="assistant-widget-card panel p-5 lg:p-6 assistant-shell" data-assistant-shell>
                    <div class="assistant-widget-card__header flex items-start justify-between gap-3">
                        <div class="assistant-widget-card__intro">
                            <span class="badge badge-primary mb-3">BayStays AI</span>
                            <h2 class="font-display text-2xl font-semibold">Opening assistant</h2>
                            <p class="mt-2 text-sm text-slate-600">Loading your latest context and actions.</p>
                        </div>
                    </div>
                    <div class="assistant-widget-card__body">
                        <div class="assistant-transcript assistant-transcript--widget">
                            <div class="assistant-bubble assistant-bubble--assistant">
                                <p class="text-xs uppercase tracking-[0.24em] text-red-500">BayStays AI</p>
                                <p class="mt-2 text-slate-700">One moment while I set up your assistant workspace.</p>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        };

        const closeWidget = () => {
            shell.classList.remove('is-open');
            shell.classList.add('hidden');
            shell.setAttribute('aria-hidden', 'true');
            syncTriggers(false);
            activeTrigger?.focus?.();
            activeTrigger = null;
        };

        const openWidget = async (trigger = null) => {
            activeTrigger = trigger || activeTrigger;
            shell.classList.remove('hidden');
            shell.classList.add('is-open');
            shell.setAttribute('aria-hidden', 'false');
            syncTriggers(true);
            panel?.focus({ preventScroll: true });
            if (hasLoaded) {
                syncWidgetFields();
                focusComposer();
                return;
            }
            if (!widgetUrl) {
                return;
            }
            try {
                renderLoadingState();
                const url = new URL(widgetUrl, window.location.origin);
                url.searchParams.set('path', window.location.pathname);
                const response = await fetch(url.toString(), {
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                    },
                });
                const payload = await response.json();
                if (!response.ok || !payload.ok) {
                    return;
                }
                content.innerHTML = payload.html;
                hasLoaded = true;
                initAssistant();
                syncWidgetFields();
                content.querySelectorAll('[data-assistant-widget-close]').forEach((button) => {
                    button.addEventListener('click', closeWidget);
                });
                focusComposer();
            } catch (error) {
                closeWidget();
                if (trigger?.href) {
                    window.location.assign(trigger.href);
                }
            }
        };

        triggers.forEach((trigger) => {
            trigger.addEventListener('click', (event) => {
                event.preventDefault();
                if (shell.classList.contains('is-open')) {
                    closeWidget();
                    return;
                }
                void openWidget(trigger);
            });
        });

        shell.querySelectorAll('[data-assistant-widget-close]').forEach((button) => {
            button.addEventListener('click', closeWidget);
        });

        backdrop?.addEventListener('click', closeWidget);

        shell.addEventListener('click', (event) => {
            if (event.target === shell.querySelector('[data-assistant-widget-close]') || event.target === shell.querySelector('.assistant-widget-backdrop')) {
                closeWidget();
            }
        });

        document.addEventListener('keydown', (event) => {
            if (!shell.classList.contains('is-open')) {
                return;
            }
            if (event.key === 'Escape') {
                closeWidget();
                return;
            }
            if (event.key !== 'Tab') {
                return;
            }
            const focusableNodes = getFocusableNodes();
            if (!focusableNodes.length) {
                event.preventDefault();
                panel?.focus({ preventScroll: true });
                return;
            }
            const first = focusableNodes[0];
            const last = focusableNodes[focusableNodes.length - 1];
            const active = document.activeElement;
            if (event.shiftKey && active === first) {
                event.preventDefault();
                last.focus();
                return;
            }
            if (!event.shiftKey && active === last) {
                event.preventDefault();
                first.focus();
            }
        });
    };

    const initSubscriptionManage = () => {
        document.querySelectorAll('.subscription-shell').forEach((shell) => {
            if (shell.dataset.bound === 'true') {
                return;
            }
            shell.dataset.bound = 'true';
            const bindForm = () => {
                const region = shell.querySelector('[data-live-content]');
                const form = region?.querySelector('[data-subscription-form]');
                const feedback = region?.querySelector('[data-subscription-feedback]');
                if (!form || form.dataset.bound === 'true') {
                    return;
                }
                form.dataset.bound = 'true';
                form.addEventListener('submit', async (event) => {
                    event.preventDefault();
                    const button = form.querySelector('button[type="submit"]');
                    button?.setAttribute('disabled', 'disabled');
                    if (feedback) {
                        feedback.classList.add('hidden');
                        feedback.classList.remove('is-success', 'is-error');
                        feedback.textContent = '';
                    }
                    try {
                        const response = await fetch(window.location.href, {
                            method: 'POST',
                            headers: {
                                'X-Requested-With': 'XMLHttpRequest',
                                'X-CSRFToken': csrfToken(),
                            },
                            body: new FormData(form),
                        });
                        const payload = await response.json();
                        if (payload.html && region) {
                            region.innerHTML = payload.html;
                            bindForm();
                        }
                        const activeFeedback = shell.querySelector('[data-subscription-feedback]');
                        if (activeFeedback && payload.message) {
                            activeFeedback.textContent = payload.message;
                            activeFeedback.classList.remove('hidden');
                            activeFeedback.classList.remove('is-success', 'is-error');
                            activeFeedback.classList.add(payload.ok ? 'is-success' : 'is-error');
                        }
                    } catch (error) {
                        if (feedback) {
                            feedback.textContent = 'We could not update that plan right now. Please try again shortly.';
                            feedback.classList.remove('hidden');
                            feedback.classList.add('is-error');
                        }
                    } finally {
                        button?.removeAttribute('disabled');
                    }
                });
            };
            bindForm();
        });
    };

    initConversationThread();
    initAssistant();
    initAssistantWidget();
    initSubscriptionManage();
    window.addEventListener('load', () => {
        initConversationThread();
        initAssistant();
        initAssistantWidget();
        initSubscriptionManage();
    });
})();
