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
        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            const input = form.querySelector('textarea[name="prompt"]');
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
                const userBubble = document.createElement('div');
                userBubble.className = 'assistant-bubble assistant-bubble--user';
                userBubble.innerHTML = '<p class="text-xs uppercase tracking-[0.24em] text-slate-500">You</p><p class="mt-2 text-slate-700 whitespace-pre-line"></p>';
                userBubble.querySelector('p:last-child').textContent = prompt;
                transcript.appendChild(userBubble);
                const assistantBubble = document.createElement('div');
                assistantBubble.className = 'assistant-bubble assistant-bubble--assistant';
                const suggestions = (payload.response.suggestions || []).map((item) => item.url ? `<a href="${item.url}" class="btn-bay-ghost btn-sm mt-3 mr-2">${item.label}</a>` : '').join('');
                assistantBubble.innerHTML = `<p class="text-xs uppercase tracking-[0.24em] text-red-500">BayStays AI</p><p class="mt-2 text-slate-700 whitespace-pre-line"></p><div>${suggestions}</div>`;
                assistantBubble.querySelector('p:last-of-type').textContent = payload.response.text;
                transcript.appendChild(assistantBubble);
                input.value = '';
                scrollToBottom(transcript);
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
        const widgetUrl = shell.dataset.widgetUrl;
        let hasLoaded = false;

        const closeWidget = () => {
            shell.classList.remove('is-open');
            shell.classList.add('hidden');
            shell.setAttribute('aria-hidden', 'true');
        };

        const openWidget = async () => {
            shell.classList.remove('hidden');
            shell.classList.add('is-open');
            shell.setAttribute('aria-hidden', 'false');
            if (hasLoaded) {
                content.querySelectorAll('input[name="path"]').forEach((input) => {
                    input.value = window.location.pathname;
                });
                return;
            }
            if (!widgetUrl) {
                return;
            }
            try {
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
                content.querySelectorAll('[data-assistant-widget-close]').forEach((button) => {
                    button.addEventListener('click', closeWidget);
                });
            } catch (error) {
                // keep the assistant link fallback available if widget fetch fails
            }
        };

        document.querySelectorAll('[data-assistant-widget-toggle]').forEach((trigger) => {
            trigger.addEventListener('click', (event) => {
                event.preventDefault();
                openWidget();
            });
        });

        shell.querySelectorAll('[data-assistant-widget-close]').forEach((button) => {
            button.addEventListener('click', closeWidget);
        });

        shell.addEventListener('click', (event) => {
            if (event.target === shell.querySelector('[data-assistant-widget-close]') || event.target === shell.querySelector('.assistant-widget-backdrop')) {
                closeWidget();
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
