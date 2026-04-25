(function () {
    const loader = document.querySelector('[data-loader]');
    const csrfToken = document.querySelector('input[name="csrfmiddlewaretoken"]')?.value || '';

    const setLoader = (active) => {
        if (!loader) {
            return;
        }
        loader.classList.toggle('is-active', !!active);
    };

    const escapeHtml = (value) => String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');

    const setButtonBusy = (button, active) => {
        if (!button) {
            return;
        }
        const idle = button.querySelector('[data-submit-text]');
        const busy = button.querySelector('[data-submit-busy]');
        button.toggleAttribute('disabled', !!active);
        button.classList.toggle('opacity-80', !!active);
        button.classList.toggle('cursor-not-allowed', !!active);
        idle?.classList.toggle('hidden', !!active);
        busy?.classList.toggle('hidden', !active);
        if (busy) {
            busy.classList.toggle('inline-flex', !!active);
        }
    };

    const getSubmitButton = (form) => form.querySelector('button[type="submit"], input[type="submit"]');

    const showInlineFeedback = (target, type, message, extraMarkup = '') => {
        if (!target) {
            return;
        }
        target.className = 'inline-feedback ' + type;
        target.innerHTML = `<div class="flex items-start gap-3"><i class="fa-solid ${type === 'success' ? 'fa-circle-check' : 'fa-circle-exclamation'} mt-0.5"></i><div><p>${escapeHtml(message)}</p>${extraMarkup}</div></div>`;
        target.classList.remove('hidden');
    };

    const clearInlineFeedback = (target) => {
        if (!target) {
            return;
        }
        target.classList.add('hidden');
        target.innerHTML = '';
    };

    const collectErrors = (payload) => {
        const errors = [];
        if (Array.isArray(payload?.non_field_errors)) {
            errors.push(...payload.non_field_errors);
        }
        Object.entries(payload?.errors || {}).forEach(([field, messages]) => {
            const list = Array.isArray(messages) ? messages : [messages];
            list.forEach((message) => {
                if (field === '__all__' || field === 'review') {
                    errors.push(message);
                } else {
                    errors.push(`${field.replace(/_/g, ' ')}: ${message}`);
                }
            });
        });
        return errors.filter(Boolean);
    };

    const temporarilySwapButtonLabel = (button, markup) => {
        if (!button) {
            return;
        }
        if (!button.dataset.originalMarkup) {
            button.dataset.originalMarkup = button.innerHTML;
        }
        button.innerHTML = markup;
        window.setTimeout(() => {
            if (button.dataset.originalMarkup) {
                button.innerHTML = button.dataset.originalMarkup;
            }
        }, 1800);
    };

    const debounce = (fn, delay = 280) => {
        let timeoutId;
        return (...args) => {
            window.clearTimeout(timeoutId);
            timeoutId = window.setTimeout(() => fn(...args), delay);
        };
    };

    const closeClosest = (selector, source) => {
        const shell = source.closest(selector);
        if (shell) {
            shell.classList.remove('is-open');
        }
    };

    document.querySelectorAll('[data-open-drawer]').forEach((button) => {
        button.addEventListener('click', () => {
            document.getElementById(button.dataset.openDrawer)?.classList.add('is-open');
        });
    });

    document.querySelectorAll('[data-close-drawer]').forEach((button) => {
        button.addEventListener('click', () => closeClosest('.drawer-shell', button));
    });

    document.querySelectorAll('[data-open-modal]').forEach((button) => {
        button.addEventListener('click', () => {
            document.getElementById(button.dataset.openModal)?.classList.add('is-open');
        });
    });

    document.querySelectorAll('[data-close-modal]').forEach((button) => {
        button.addEventListener('click', () => closeClosest('.modal-shell', button));
    });

    document.querySelectorAll('[data-open-lightbox]').forEach((trigger) => {
        trigger.addEventListener('click', () => {
            const shell = document.getElementById(trigger.dataset.openLightbox);
            if (!shell) {
                return;
            }
            const image = shell.querySelector('[data-lightbox-image]');
            const caption = shell.querySelector('[data-lightbox-caption]');
            if (image && trigger.dataset.imageSrc) {
                image.src = trigger.dataset.imageSrc;
                image.alt = trigger.dataset.imageAlt || 'Listing image';
            }
            if (caption) {
                caption.textContent = trigger.dataset.imageCaption || trigger.dataset.imageAlt || 'BayStays stay image';
            }
            shell.classList.add('is-open');
        });
    });

    document.querySelectorAll('[data-close-lightbox]').forEach((button) => {
        button.addEventListener('click', () => closeClosest('.lightbox-shell', button));
    });

    document.querySelectorAll('.accordion-toggle').forEach((button) => {
        button.addEventListener('click', () => {
            const panel = document.getElementById(button.getAttribute('aria-controls'));
            const expanded = button.getAttribute('aria-expanded') === 'true';
            button.setAttribute('aria-expanded', expanded ? 'false' : 'true');
            panel?.classList.toggle('is-open', !expanded);
        });
    });

    document.querySelectorAll('[data-toast-close]').forEach((button) => {
        button.addEventListener('click', () => {
            const toast = button.closest('.toast');
            if (!toast) {
                return;
            }
            toast.classList.add('hide');
            setTimeout(() => toast.remove(), 240);
        });
    });

    document.querySelectorAll('[data-auto-dismiss="true"]').forEach((toast) => {
        setTimeout(() => {
            toast.classList.add('hide');
            setTimeout(() => toast.remove(), 240);
        }, 5000);
    });

    document.querySelectorAll('form[data-loading-form="true"]').forEach((form) => {
        if (form.matches('[data-async-booking], [data-async-review]')) {
            return;
        }
        form.addEventListener('submit', () => {
            setLoader(true);
            setButtonBusy(getSubmitButton(form), true);
        });
    });

    const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (entry.isIntersecting) {
                entry.target.classList.add('is-visible');
            }
        });
    }, { threshold: 0.15 });

    document.querySelectorAll('.section-fade').forEach((element) => observer.observe(element));

    document.querySelectorAll('[data-countup]').forEach((element) => {
        const target = Number(element.dataset.countup || 0);
        if (!Number.isFinite(target)) {
            return;
        }
        let started = false;
        const run = () => {
            if (started) {
                return;
            }
            started = true;
            const start = performance.now();
            const duration = 950;
            const tick = (now) => {
                const progress = Math.min((now - start) / duration, 1);
                element.textContent = Math.round(progress * target).toLocaleString();
                if (progress < 1) {
                    requestAnimationFrame(tick);
                }
            };
            requestAnimationFrame(tick);
        };
        const localObserver = new IntersectionObserver((entries) => {
            if (entries[0]?.isIntersecting) {
                run();
                localObserver.disconnect();
            }
        });
        localObserver.observe(element);
    });

    const hero = document.querySelector('[data-hero-carousel]');
    if (hero) {
        const slides = Array.from(hero.querySelectorAll('[data-hero-slide]'));
        const progress = Array.from(hero.querySelectorAll('[data-hero-progress-item]'));
        let activeIndex = 0;
        const heroDuration = Number(hero.dataset.heroDuration || 6500);
        const activate = (index) => {
            slides.forEach((slide, slideIndex) => {
                slide.classList.toggle('is-active', slideIndex === index);
            });
            progress.forEach((item, itemIndex) => {
                item.classList.remove('is-active');
                if (itemIndex === index) {
                    // Force restart of the progress animation.
                    void item.offsetWidth;
                    item.classList.add('is-active');
                }
            });
            activeIndex = index;
        };
        activate(0);
        if (slides.length > 1) {
            window.setInterval(() => {
                activate((activeIndex + 1) % slides.length);
            }, heroDuration);
        }
    }

    document.querySelectorAll('[data-booking-filter]').forEach((button) => {
        button.addEventListener('click', () => {
            const scope = button.closest('[data-booking-filter-group]');
            if (!scope) {
                return;
            }
            const target = button.dataset.bookingFilter;
            scope.querySelectorAll('[data-booking-filter]').forEach((item) => {
                item.classList.toggle('is-active', item === button);
            });
            scope.querySelectorAll('[data-booking-row]').forEach((row) => {
                const status = row.dataset.bookingStatus || '';
                const visible = target === 'all' || status === target;
                row.classList.toggle('hidden', !visible);
            });
        });
    });

    const gallerySlots = Array.from(document.querySelectorAll('[data-image-slot]'));
    gallerySlots.forEach((slot) => {
        const input = slot.querySelector('input[type="file"]');
        const preview = slot.querySelector('[data-image-preview]');
        const previewImage = slot.querySelector('[data-image-preview-image]');
        const emptyState = slot.querySelector('[data-image-empty]');
        const caption = slot.querySelector('input[type="text"]');
        const title = slot.querySelector('[data-image-title]');
        const deleteToggle = slot.querySelector('input[type="checkbox"][name$="-DELETE"]');
        const resetButton = slot.querySelector('[data-remove-image-slot]');

        const setPreview = (file) => {
            if (!preview || !previewImage || !emptyState) {
                return;
            }
            if (!file) {
                preview.classList.add('hidden');
                emptyState.classList.remove('hidden');
                return;
            }
            previewImage.src = URL.createObjectURL(file);
            preview.classList.remove('hidden');
            emptyState.classList.add('hidden');
            if (title) {
                title.textContent = file.name;
            }
            if (caption && !caption.value) {
                caption.value = file.name.replace(/\.[^.]+$/, '').replace(/[-_]+/g, ' ');
            }
            slot.dataset.hasPreview = 'true';
        };

        input?.addEventListener('change', () => {
            const file = input.files && input.files[0];
            setPreview(file || null);
        });

        resetButton?.addEventListener('click', () => {
            if (input) {
                input.value = '';
            }
            if (deleteToggle) {
                deleteToggle.checked = true;
            }
            if (preview && emptyState) {
                preview.classList.add('hidden');
                emptyState.classList.remove('hidden');
            }
            slot.classList.add('opacity-60');
        });
    });

    const addImageButton = document.querySelector('[data-add-image-slot]');
    if (addImageButton) {
        addImageButton.addEventListener('click', () => {
            const nextHidden = gallerySlots.find((slot) => slot.dataset.slotVisible !== 'true');
            if (!nextHidden) {
                return;
            }
            nextHidden.dataset.slotVisible = 'true';
            nextHidden.classList.remove('hidden');
            nextHidden.querySelector('input[type="file"]')?.focus();
            if (!gallerySlots.find((slot) => slot.dataset.slotVisible !== 'true')) {
                addImageButton.setAttribute('disabled', 'disabled');
                addImageButton.classList.add('opacity-50', 'cursor-not-allowed');
            }
        });
    }

    document.querySelectorAll('[data-booking-calculator]').forEach((bookingCalculator) => {
        const checkIn = bookingCalculator.querySelector('input[name="check_in_date"]');
        const checkOut = bookingCalculator.querySelector('input[name="check_out_date"]');
        const guests = bookingCalculator.querySelector('input[name="num_guests"]');
        const nightsNode = bookingCalculator.querySelector('[data-booking-nights]');
        const totalNode = bookingCalculator.querySelector('[data-booking-total]');
        const availabilityNode = document.getElementById('availability-feedback');
        const submitButton = getSubmitButton(bookingCalculator);
        const rate = Number(bookingCalculator.dataset.nightlyRate || 0);
        const unavailableRanges = JSON.parse(bookingCalculator.dataset.unavailableRanges || '[]');

        const updateQuote = () => {
            const start = checkIn?.value ? new Date(checkIn.value) : null;
            const end = checkOut?.value ? new Date(checkOut.value) : null;
            if (!start || !end || Number.isNaN(start.valueOf()) || Number.isNaN(end.valueOf())) {
                if (nightsNode) {
                    nightsNode.textContent = '0 nights';
                }
                if (totalNode) {
                    totalNode.textContent = 'KES 0';
                }
                clearInlineFeedback(availabilityNode);
                submitButton?.removeAttribute('disabled');
                return;
            }
            const diff = Math.max(0, Math.round((end - start) / 86400000));
            if (nightsNode) {
                nightsNode.textContent = diff + (diff === 1 ? ' night' : ' nights');
            }
            if (totalNode) {
                totalNode.textContent = 'KES ' + (diff * rate).toLocaleString();
            }
            if (guests && Number(guests.value || 0) < 1) {
                guests.value = '1';
            }
            const hasConflict = unavailableRanges.some((range) => {
                const blockedStart = new Date(range.check_in);
                const blockedEnd = new Date(range.check_out);
                return start < blockedEnd && end > blockedStart;
            });
            if (hasConflict) {
                const range = unavailableRanges.find((item) => {
                    const blockedStart = new Date(item.check_in);
                    const blockedEnd = new Date(item.check_out);
                    return start < blockedEnd && end > blockedStart;
                });
                showInlineFeedback(
                    availabilityNode,
                    'error',
                    `Those dates overlap with an existing ${range?.status || 'active'} booking. Try different dates before sending your request.`
                );
                submitButton?.setAttribute('disabled', 'disabled');
            } else {
                clearInlineFeedback(availabilityNode);
                submitButton?.removeAttribute('disabled');
            }
        };

        bookingCalculator._updateQuote = updateQuote;
        checkIn?.addEventListener('change', updateQuote);
        checkOut?.addEventListener('change', updateQuote);
        guests?.addEventListener('input', updateQuote);
        updateQuote();
    });

    document.querySelectorAll('[data-copy-share-link]').forEach((button) => {
        button.addEventListener('click', async () => {
            const shareUrl = button.dataset.shareUrl || window.location.href;
            try {
                await navigator.clipboard.writeText(shareUrl);
                temporarilySwapButtonLabel(button, '<i class="fa-solid fa-circle-check"></i>Copied');
            } catch (error) {
                temporarilySwapButtonLabel(button, '<i class="fa-solid fa-link"></i>Copy manually');
            }
        });
    });

    document.querySelectorAll('[data-native-share]').forEach((button) => {
        button.addEventListener('click', async () => {
            const shareData = {
                title: button.dataset.shareTitle || document.title,
                text: button.dataset.shareText || '',
                url: button.dataset.shareUrl || window.location.href,
            };
            if (navigator.share) {
                try {
                    await navigator.share(shareData);
                    temporarilySwapButtonLabel(button, '<i class="fa-solid fa-paper-plane"></i>Shared');
                    closeClosest('.modal-shell', button);
                    return;
                } catch (error) {
                    if (error?.name === 'AbortError') {
                        return;
                    }
                }
            }
            try {
                await navigator.clipboard.writeText(shareData.url);
                temporarilySwapButtonLabel(button, '<i class="fa-solid fa-circle-check"></i>Link copied');
            } catch (error) {
                temporarilySwapButtonLabel(button, '<i class="fa-solid fa-paper-plane"></i>Share unavailable');
            }
        });
    });

    document.querySelectorAll('[data-rating-meter-control]').forEach((wrapper) => {
        const meter = wrapper.querySelector('[data-rating-meter]');
        const output = wrapper.querySelector('[data-rating-value]');
        const input = wrapper.querySelector('[data-rating-input]');
        const stars = Array.from(wrapper.querySelectorAll('[data-rating-star]'));
        let lastStarIndex = null;
        const sync = () => {
            const value = Number(input?.value || 0);
            if (meter) {
                meter.style.setProperty('--rating', value);
            }
            if (output) {
                output.textContent = value ? `${value.toFixed(1)} / 5` : 'Select your rating';
            }
            stars.forEach((star) => {
                const starIndex = Number(star.dataset.starIndex || 0);
                const icon = star.querySelector('i');
                star.classList.toggle('is-active', value >= starIndex - 0.5);
                if (!icon) {
                    return;
                }
                if (value >= starIndex) {
                    icon.className = 'fa-solid fa-star';
                } else if (value >= starIndex - 0.5) {
                    icon.className = 'fa-solid fa-star-half-stroke';
                } else {
                    icon.className = 'fa-regular fa-star';
                }
            });
        };
        stars.forEach((star) => {
            star.addEventListener('click', () => {
                const starIndex = Number(star.dataset.starIndex || 0);
                const current = Number(input?.value || 0);
                let next = starIndex - 0.5;

                if (lastStarIndex === starIndex && current === starIndex - 0.5) {
                    next = starIndex;
                } else if (lastStarIndex === starIndex && current === starIndex) {
                    next = Math.max(0, starIndex - 1);
                }

                if (input) {
                    input.value = next.toFixed(1);
                }
                lastStarIndex = starIndex;
                sync();
            });
        });
        sync();
    });

    const updateReviewSummaries = (payload) => {
        if (payload.average_rating) {
            document.querySelectorAll('[data-average-rating-display]').forEach((node) => {
                node.textContent = payload.average_rating;
            });
        }
        if (payload.reviews_count) {
            document.querySelectorAll('[data-reviews-count-display]').forEach((node) => {
                const count = Number(payload.reviews_count);
                node.textContent = `${count} review${count === 1 ? '' : 's'}`;
            });
        }
    };

    document.querySelectorAll('form[data-async-review]').forEach((form) => {
        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            const feedback = document.getElementById('review-feedback');
            const reviewsList = document.getElementById('reviews-list');
            const submitButton = getSubmitButton(form);
            clearInlineFeedback(feedback);
            setButtonBusy(submitButton, true);

            try {
                const response = await fetch(form.action, {
                    method: 'POST',
                    body: new FormData(form),
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': csrfToken,
                    },
                });
                const payload = await response.json();

                if (!response.ok || !payload.ok) {
                    const errors = collectErrors(payload);
                    showInlineFeedback(feedback, 'error', errors[0] || 'We could not save your review yet.');
                    return;
                }

                showInlineFeedback(feedback, 'success', payload.message || 'Review saved successfully.');
                updateReviewSummaries(payload);

                if (reviewsList) {
                    const emptyState = reviewsList.querySelector('.empty-state');
                    if (emptyState) {
                        emptyState.remove();
                    }

                    const reviewMarkup = `
                        <article class="rounded-[0.95rem] border border-slate-100 bg-slate-50 p-5" data-review-id="${escapeHtml(payload.review_id)}">
                            <div class="flex items-center justify-between gap-3 flex-wrap">
                                <div>
                                    <p class="font-semibold">${escapeHtml(payload.reviewer)}</p>
                                    <p class="text-sm text-slate-500">${escapeHtml(payload.created_at)}</p>
                                </div>
                                <div class="flex items-center gap-3">
                                    <span class="rating-meter" style="--rating: ${escapeHtml(payload.rating)};"></span>
                                    <span class="badge badge-warm"><i class="fa-solid fa-star"></i>${escapeHtml(payload.rating)}</span>
                                </div>
                            </div>
                            <p class="mt-3 text-slate-600">${escapeHtml(payload.comment)}</p>
                        </article>
                    `;

                    const existing = reviewsList.querySelector(`[data-review-id="${CSS.escape(String(payload.review_id))}"]`);
                    if (existing) {
                        existing.outerHTML = reviewMarkup;
                    } else {
                        reviewsList.insertAdjacentHTML('afterbegin', reviewMarkup);
                    }
                }
            } catch (error) {
                showInlineFeedback(feedback, 'error', 'We ran into a network issue while saving your review.');
            } finally {
                setButtonBusy(submitButton, false);
            }
        });
    });

    document.querySelectorAll('form[data-async-booking]').forEach((form) => {
        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            const feedback = document.getElementById('booking-feedback');
            const submitButton = getSubmitButton(form);
            clearInlineFeedback(feedback);
            setButtonBusy(submitButton, true);

            try {
                const response = await fetch(form.action, {
                    method: 'POST',
                    body: new FormData(form),
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': csrfToken,
                    },
                });
                const payload = await response.json();

                if (!response.ok || !payload.ok) {
                    const errors = collectErrors(payload);
                    showInlineFeedback(feedback, 'error', errors[0] || 'We could not submit your booking request.');
                    return;
                }

                const extraMarkup = payload.redirect_url
                    ? `<p class="mt-2"><a class="font-semibold underline" href="${escapeHtml(payload.redirect_url)}">Open my bookings</a></p>`
                    : '';
                showInlineFeedback(feedback, 'success', payload.message || 'Booking request submitted successfully.', extraMarkup);
                form.reset();
                form._updateQuote?.();
            } catch (error) {
                showInlineFeedback(feedback, 'error', 'We ran into a network issue while sending your booking request.');
            } finally {
                setButtonBusy(submitButton, false);
            }
        });
    });

    document.querySelectorAll('[data-location-autocomplete]').forEach((wrapper) => {
        const input = wrapper.querySelector('[data-location-input]');
        const suggestions = wrapper.querySelector('[data-location-suggestions]');
        const hiddenLat = wrapper.querySelector('input[name="location_lat"], input[name="latitude"]');
        const hiddenLng = wrapper.querySelector('input[name="location_lng"], input[name="longitude"]');
        const addressField = wrapper.querySelector('[data-location-address]');
        const cityField = wrapper.querySelector('[data-location-city]');
        const stateField = wrapper.querySelector('[data-location-state]');
        const countryField = wrapper.querySelector('[data-location-country]');
        let activeRequest = 0;

        const hideSuggestions = () => {
            if (!suggestions) {
                return;
            }
            suggestions.innerHTML = '';
            suggestions.classList.add('hidden');
        };

        const applySuggestion = (item) => {
            const address = item.address || {};
            if (input) {
                input.value = item.display_name || input.value;
            }
            if (addressField && addressField !== input) {
                addressField.value = item.display_name || addressField.value;
            }
            if (cityField) {
                cityField.value = address.city || address.town || address.village || address.municipality || cityField.value;
            }
            if (stateField) {
                stateField.value = address.state || address.county || stateField.value;
            }
            if (countryField) {
                countryField.value = address.country || countryField.value;
            }
            if (hiddenLat) {
                hiddenLat.value = item.lat || '';
            }
            if (hiddenLng) {
                hiddenLng.value = item.lon || '';
            }
            hideSuggestions();
        };

        const fetchSuggestions = debounce(async () => {
            if (!input || !suggestions) {
                return;
            }
            const query = input.value.trim();
            if (query.length < 3) {
                hideSuggestions();
                return;
            }
            const requestId = ++activeRequest;
            suggestions.classList.remove('hidden');
            suggestions.innerHTML = '<div class="px-4 py-4 text-sm text-slate-500 flex items-center gap-3"><span class="spinner spinner-dark"></span>Looking up places</div>';
            try {
                const response = await fetch(`https://nominatim.openstreetmap.org/search?format=jsonv2&addressdetails=1&limit=5&q=${encodeURIComponent(query)}`, {
                    headers: {
                        'Accept': 'application/json',
                    },
                });
                const data = await response.json();
                if (requestId !== activeRequest) {
                    return;
                }
                if (!Array.isArray(data) || !data.length) {
                    suggestions.innerHTML = '<div class="px-4 py-4 text-sm text-slate-500">No close matches yet. Keep typing the town, area, or address.</div>';
                    return;
                }
                suggestions.innerHTML = data.map((item) => `
                    <button type="button" class="location-suggestion" data-location-choice='${JSON.stringify(item).replace(/'/g, '&#39;')}'>
                        <i class="fa-solid fa-location-dot mt-1 text-red-500"></i>
                        <span>
                            <span class="block font-semibold text-slate-800">${escapeHtml(item.name || item.display_name.split(',')[0])}</span>
                            <span class="block text-sm text-slate-500 mt-1">${escapeHtml(item.display_name)}</span>
                        </span>
                    </button>
                `).join('');
                suggestions.querySelectorAll('[data-location-choice]').forEach((button) => {
                    button.addEventListener('click', () => {
                        const item = JSON.parse(button.dataset.locationChoice.replace(/&#39;/g, "'"));
                        applySuggestion(item);
                    });
                });
            } catch (error) {
                suggestions.innerHTML = '<div class="px-4 py-4 text-sm text-slate-500">Place suggestions are temporarily unavailable. You can still type the location manually.</div>';
            }
        }, 320);

        input?.addEventListener('input', () => {
            if (hiddenLat) {
                hiddenLat.value = '';
            }
            if (hiddenLng) {
                hiddenLng.value = '';
            }
            fetchSuggestions();
        });
        input?.addEventListener('focus', fetchSuggestions);
        document.addEventListener('click', (event) => {
            if (!wrapper.contains(event.target)) {
                hideSuggestions();
            }
        });
    });

    document.querySelectorAll('form[data-explore-form]').forEach((form) => {
        const results = document.querySelector('[data-explore-results]');
        const overlay = document.querySelector('[data-results-overlay]');
        const countNode = document.querySelector('[data-results-count]');
        const avgPriceNode = document.querySelector('[data-results-price]');
        const avgRatingNode = document.querySelector('[data-results-rating]');
        const destinationNode = document.querySelector('[data-results-destination]');

        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            overlay?.classList.add('is-active');
            const submitButton = getSubmitButton(form);
            setButtonBusy(submitButton, true);

            try {
                const params = new URLSearchParams(new FormData(form));
                const response = await fetch(`${form.action || window.location.pathname}?${params.toString()}`, {
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                    },
                });
                const payload = await response.json();
                if (results && typeof payload.html === 'string') {
                    results.innerHTML = payload.html;
                }
                if (countNode) {
                    countNode.textContent = payload.results_count ?? 0;
                }
                if (avgPriceNode) {
                    avgPriceNode.textContent = `KES ${Math.round(Number(payload.avg_price || 0)).toLocaleString()}`;
                }
                if (avgRatingNode) {
                    avgRatingNode.textContent = Number(payload.avg_rating || 0).toFixed(1);
                }
                if (destinationNode) {
                    destinationNode.textContent = payload.top_destination || 'Flexible';
                }
                const url = new URL(window.location.href);
                url.search = params.toString();
                window.history.replaceState({}, '', url);
            } catch (error) {
                if (results) {
                    results.innerHTML = '<div class="empty-state rounded-[1rem] px-6 py-10 md:col-span-2 xl:col-span-3"><div><i class="fa-solid fa-triangle-exclamation text-3xl text-red-500"></i><p class="mt-4 font-semibold text-slate-800">We could not refresh stays right now</p><p class="text-sm text-slate-500 mt-2">Please try your search again in a moment.</p></div></div>';
                }
            } finally {
                overlay?.classList.remove('is-active');
                setButtonBusy(submitButton, false);
            }
        });
    });

    const initPropertyMaps = () => document.querySelectorAll('[data-property-map]').forEach((node) => {
        const lat = Number(node.dataset.lat);
        const lng = Number(node.dataset.lng);
        if (!Number.isFinite(lat) || !Number.isFinite(lng) || typeof window.L === 'undefined') {
            return;
        }
        if (node.dataset.mapReady === 'true') {
            return;
        }
        const map = window.L.map(node, {
            zoomControl: false,
            scrollWheelZoom: false,
        }).setView([lat, lng], 14);
        window.L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OpenStreetMap contributors',
        }).addTo(map);
        window.L.circleMarker([lat, lng], {
            radius: 10,
            color: '#cf2338',
            fillColor: '#f97316',
            fillOpacity: 0.9,
            weight: 3,
        }).addTo(map);
        node.dataset.mapReady = 'true';
    });

    initPropertyMaps();

    window.addEventListener('pageshow', () => setLoader(false));
    window.addEventListener('load', () => {
        setLoader(false);
        initPropertyMaps();
    });
})();
