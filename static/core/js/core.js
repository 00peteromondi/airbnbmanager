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

    const markAreaUpdated = (target) => {
        if (!target) {
            return;
        }
        target.classList.remove('ui-refresh-blink');
        void target.offsetWidth;
        target.classList.add('ui-refresh-blink');
        window.setTimeout(() => {
            target.classList.remove('ui-refresh-blink');
        }, 760);
    };

    const formatLocationAddress = (item) => {
        const address = item?.address || {};
        const primaryLine = [
            address.house_number,
            address.road || address.pedestrian || address.cycleway || address.footway,
        ].filter(Boolean).join(' ').trim();

        if (primaryLine) {
            return primaryLine;
        }

        return [
            address.neighbourhood,
            address.suburb,
            address.hamlet,
            address.quarter,
            item?.name,
            item?.display_name?.split(',')?.[0],
        ].find(Boolean) || '';
    };

    const getLocationPayload = (item) => {
        const address = item?.address || {};
        return {
            lat: item?.lat || '',
            lng: item?.lon || '',
            address: formatLocationAddress(item) || item?.display_name || '',
            city: address.city || address.town || address.village || address.municipality || '',
            state: address.state || address.county || '',
            country: address.country || '',
            displayName: item?.display_name || '',
        };
    };

    const setDrawerState = (shell, isOpen) => {
        if (!shell) {
            return;
        }
        shell.classList.toggle('is-open', !!isOpen);
        shell.setAttribute('aria-hidden', isOpen ? 'false' : 'true');
        document.body.classList.toggle('drawer-open', !!isOpen);
        document.documentElement.classList.toggle('drawer-open', !!isOpen);
    };

    const closeClosest = (selector, source) => {
        const shell = source.closest(selector);
        if (shell) {
            if (selector === '.drawer-shell') {
                setDrawerState(shell, false);
                return;
            }
            shell.classList.remove('is-open');
        }
    };

    document.querySelectorAll('[data-open-drawer]').forEach((button) => {
        button.addEventListener('click', () => {
            setDrawerState(document.getElementById(button.dataset.openDrawer), true);
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

    document.querySelectorAll('.lightbox-shell').forEach((shell) => {
        const image = shell.querySelector('[data-lightbox-image]');
        const caption = shell.querySelector('[data-lightbox-caption]');
        const prevButton = shell.querySelector('[data-lightbox-prev]');
        const nextButton = shell.querySelector('[data-lightbox-next]');
        const thumbnails = Array.from(shell.querySelectorAll('[data-lightbox-thumb]'));
        const galleryId = shell.id;
        const triggers = Array.from(document.querySelectorAll(`[data-open-lightbox="${galleryId}"]`));
        const slides = thumbnails.length ? thumbnails.map((thumb) => ({
            src: thumb.dataset.imageSrc || '',
            alt: thumb.dataset.imageAlt || 'Listing image',
            caption: thumb.dataset.imageCaption || thumb.dataset.imageAlt || 'BayStays stay image',
        })) : triggers.map((trigger) => ({
            src: trigger.dataset.imageSrc || '',
            alt: trigger.dataset.imageAlt || 'Listing image',
            caption: trigger.dataset.imageCaption || trigger.dataset.imageAlt || 'BayStays stay image',
        }));

        if (!slides.length) {
            return;
        }

        let activeIndex = 0;

        const syncGallery = (nextIndex) => {
            activeIndex = Math.max(0, Math.min(nextIndex, slides.length - 1));
            const slide = slides[activeIndex];
            if (image) {
                image.src = slide.src;
                image.alt = slide.alt;
            }
            if (caption) {
                caption.textContent = slide.caption;
            }
            thumbnails.forEach((thumb) => {
                const thumbIndex = Number(thumb.dataset.lightboxIndex || 0);
                const isActive = thumbIndex === activeIndex;
                thumb.classList.toggle('is-active', isActive);
                if (isActive) {
                    thumb.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
                }
            });
            if (prevButton) {
                prevButton.disabled = activeIndex === 0;
            }
            if (nextButton) {
                nextButton.disabled = activeIndex === slides.length - 1;
            }
        };

        const openGallery = (index) => {
            syncGallery(index);
            shell.classList.add('is-open');
            document.body.classList.add('lightbox-open');
            document.documentElement.classList.add('lightbox-open');
        };

        const closeGallery = () => {
            shell.classList.remove('is-open');
            document.body.classList.remove('lightbox-open');
            document.documentElement.classList.remove('lightbox-open');
        };

        triggers.forEach((trigger) => {
            trigger.addEventListener('click', () => {
                openGallery(Number(trigger.dataset.lightboxIndex || 0));
            });
        });

        thumbnails.forEach((thumb) => {
            thumb.addEventListener('click', () => {
                syncGallery(Number(thumb.dataset.lightboxIndex || 0));
            });
        });

        prevButton?.addEventListener('click', () => syncGallery(activeIndex - 1));
        nextButton?.addEventListener('click', () => syncGallery(activeIndex + 1));

        shell.querySelectorAll('[data-close-lightbox]').forEach((button) => {
            button.addEventListener('click', closeGallery);
        });

        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') {
                document.querySelectorAll('.drawer-shell.is-open').forEach((shell) => setDrawerState(shell, false));
            }
            if (!shell.classList.contains('is-open')) {
                return;
            }
            if (event.key === 'Escape') {
                closeGallery();
            } else if (event.key === 'ArrowLeft' && activeIndex > 0) {
                syncGallery(activeIndex - 1);
            } else if (event.key === 'ArrowRight' && activeIndex < slides.length - 1) {
                syncGallery(activeIndex + 1);
            }
        });
    });

    document.querySelectorAll('[data-mobile-gallery]').forEach((gallery) => {
        const primaryTrigger = gallery.querySelector('[data-mobile-gallery-primary]');
        const primaryImage = gallery.querySelector('[data-mobile-gallery-image]');
        const countNode = gallery.querySelector('[data-mobile-gallery-count]');
        const thumbs = Array.from(gallery.querySelectorAll('[data-mobile-gallery-thumb]'));
        if (!primaryTrigger || !primaryImage || !thumbs.length) {
            return;
        }

        const total = thumbs.length;
        const syncMobileGallery = (index) => {
            const nextIndex = Math.max(0, Math.min(index, total - 1));
            const activeThumb = thumbs[nextIndex];
            if (!activeThumb) {
                return;
            }
            primaryImage.src = activeThumb.dataset.imageSrc || primaryImage.src;
            primaryImage.alt = activeThumb.dataset.imageAlt || primaryImage.alt;
            primaryTrigger.dataset.lightboxIndex = String(nextIndex);
            primaryTrigger.dataset.imageSrc = activeThumb.dataset.imageSrc || '';
            primaryTrigger.dataset.imageAlt = activeThumb.dataset.imageAlt || '';
            primaryTrigger.dataset.imageCaption = activeThumb.dataset.imageCaption || '';
            thumbs.forEach((thumb, thumbIndex) => {
                const isActive = thumbIndex === nextIndex;
                thumb.classList.toggle('is-active', isActive);
                if (isActive) {
                    thumb.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
                }
            });
            if (countNode) {
                countNode.textContent = `${nextIndex + 1} / ${total}`;
            }
        };

        thumbs.forEach((thumb, index) => {
            thumb.addEventListener('click', () => syncMobileGallery(index));
        });

        syncMobileGallery(0);
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
            setButtonBusy(getSubmitButton(form), true);
        });
    });

    document.addEventListener('submit', (event) => {
        const form = event.target.closest('form[data-loading-form="true"]');
        if (!form || form.matches('[data-async-booking], [data-async-review]')) {
            return;
        }
        setButtonBusy(getSubmitButton(form), true);
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

    document.addEventListener('click', (event) => {
        const button = event.target.closest('[data-booking-filter]');
        if (!button) {
            return;
        }
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

    const gallerySlots = Array.from(document.querySelectorAll('[data-image-slot]'));
    const syncGalleryAddButton = () => {
        const addImageButton = document.querySelector('[data-add-image-slot]');
        if (!addImageButton) {
            return;
        }
        const hasHiddenSlots = gallerySlots.some((slot) => slot.dataset.slotVisible !== 'true');
        addImageButton.toggleAttribute('disabled', !hasHiddenSlots);
        addImageButton.classList.toggle('opacity-50', !hasHiddenSlots);
        addImageButton.classList.toggle('cursor-not-allowed', !hasHiddenSlots);
    };

    const setSlotEnabledState = (slot, enabled) => {
        slot.dataset.slotVisible = enabled ? 'true' : 'false';
        slot.classList.toggle('hidden', !enabled);
        slot.classList.toggle('opacity-60', false);
        slot.querySelectorAll('input, textarea, select').forEach((field) => {
            if (field.type === 'hidden') {
                return;
            }
            if (field.type === 'checkbox' && field.name.endsWith('-DELETE')) {
                field.disabled = !enabled;
                return;
            }
            field.disabled = !enabled;
        });
        syncGalleryAddButton();
    };

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
            const isExisting = slot.querySelector('input[name$="-id"]')?.value;
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
            if (caption) {
                caption.value = '';
            }
            const primaryToggle = slot.querySelector('input[type="checkbox"][name$="-is_primary"]');
            if (primaryToggle) {
                primaryToggle.checked = false;
            }
            if (title) {
                title.textContent = isExisting ? 'Existing gallery image' : 'New gallery image';
            }
            if (isExisting) {
                slot.classList.add('opacity-60');
            } else {
                setSlotEnabledState(slot, false);
            }
        });

        setSlotEnabledState(slot, slot.dataset.slotVisible === 'true');
    });

    const addImageButton = document.querySelector('[data-add-image-slot]');
    if (addImageButton) {
        addImageButton.addEventListener('click', () => {
            const nextHidden = gallerySlots.find((slot) => slot.dataset.slotVisible !== 'true');
            if (!nextHidden) {
                return;
            }
            const deleteToggle = nextHidden.querySelector('input[type="checkbox"][name$="-DELETE"]');
            if (deleteToggle) {
                deleteToggle.checked = false;
            }
            setSlotEnabledState(nextHidden, true);
            nextHidden.querySelector('input[type="file"]')?.focus();
        });
    }
    syncGalleryAddButton();

    document.querySelectorAll('[data-profile-photo-preview]').forEach((wrapper) => {
        const input = wrapper.querySelector('input[type="file"]');
        const previewImages = document.querySelectorAll('[data-profile-preview-image]');
        const previewIcons = document.querySelectorAll('[data-profile-preview-icon]');

        input?.addEventListener('change', () => {
            const file = input.files && input.files[0];
            if (!file) {
                return;
            }
            const objectUrl = URL.createObjectURL(file);
            previewImages.forEach((image) => {
                image.src = objectUrl;
                image.classList.remove('hidden');
            });
            previewIcons.forEach((icon) => {
                icon.classList.add('hidden');
            });
        });
    });

    document.querySelectorAll('[data-booking-calculator]').forEach((bookingCalculator) => {
        const checkIn = bookingCalculator.querySelector('input[name="check_in_date"]');
        const checkOut = bookingCalculator.querySelector('input[name="check_out_date"]');
        const guests = bookingCalculator.querySelector('input[name="num_guests"]');
        const nightsNode = bookingCalculator.querySelector('[data-booking-nights]');
        const totalNode = bookingCalculator.querySelector('[data-booking-total]');
        const availabilityNode = document.getElementById('availability-feedback');
        const submitButton = getSubmitButton(bookingCalculator);
        const rate = Number(bookingCalculator.dataset.nightlyRate || 0);
        let unavailableRanges = JSON.parse(bookingCalculator.dataset.unavailableRanges || '[]');
        const todayIso = new Date(Date.now() + 86400000).toISOString().slice(0, 10);

        const normalizeBlockedRanges = () => unavailableRanges.map((range) => {
            const start = new Date(range.check_in);
            const end = new Date(range.check_out);
            end.setDate(end.getDate() - 1);
            return {
                from: start,
                to: end,
            };
        }).filter((range) => range.from <= range.to);

        const blockedRanges = normalizeBlockedRanges();
        let checkInPicker = null;
        let checkOutPicker = null;

        const dispatchInputUpdate = (input) => {
            input?.dispatchEvent(new Event('change', { bubbles: true }));
        };

        if (typeof window.flatpickr !== 'undefined' && checkIn && checkOut) {
            checkInPicker = window.flatpickr(checkIn, {
                dateFormat: 'Y-m-d',
                minDate: todayIso,
                disable: blockedRanges,
                onChange: (selectedDates, dateStr) => {
                    if (checkOutPicker) {
                        const nextMin = selectedDates[0] ? new Date(selectedDates[0].getTime() + 86400000) : todayIso;
                        checkOutPicker.set('minDate', nextMin);
                        if (checkOut.value && selectedDates[0] && new Date(checkOut.value) <= selectedDates[0]) {
                            checkOutPicker.clear();
                        }
                    }
                    dispatchInputUpdate(checkIn);
                },
            });

            checkOutPicker = window.flatpickr(checkOut, {
                dateFormat: 'Y-m-d',
                minDate: todayIso,
                disable: blockedRanges,
                onChange: () => {
                    dispatchInputUpdate(checkOut);
                },
            });
        }

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
        bookingCalculator._refreshAvailability = (ranges = []) => {
            unavailableRanges = Array.isArray(ranges) ? ranges : [];
            bookingCalculator.dataset.unavailableRanges = JSON.stringify(unavailableRanges);
            const nextBlockedRanges = normalizeBlockedRanges();
            if (checkInPicker) {
                checkInPicker.set('disable', nextBlockedRanges);
            }
            if (checkOutPicker) {
                checkOutPicker.set('disable', nextBlockedRanges);
            }
            updateQuote();
        };
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
                document.dispatchEvent(new CustomEvent('baystays:live-refresh'));
                markAreaUpdated(reviewsList || feedback);

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

                const extraNotes = [];
                if (payload.payment_message) {
                    extraNotes.push(`<p class="mt-2 text-sm">${escapeHtml(payload.payment_message)}</p>`);
                }
                if (payload.redirect_url) {
                    extraNotes.push(`<p class="mt-2"><a class="font-semibold underline" href="${escapeHtml(payload.redirect_url)}">Open my bookings</a></p>`);
                }
                const extraMarkup = extraNotes.join('');
                showInlineFeedback(feedback, 'success', payload.message || 'Booking request submitted successfully.', extraMarkup);
                form.reset();
                form._updateQuote?.();
                document.dispatchEvent(new CustomEvent('baystays:live-refresh'));
                markAreaUpdated(form.closest('.panel') || form);
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
        const hostForm = wrapper.closest('form');
        let activeRequest = 0;

        const hideSuggestions = () => {
            if (!suggestions) {
                return;
            }
            suggestions.innerHTML = '';
            suggestions.classList.add('hidden');
        };

        const dispatchLocationUpdate = (payload) => {
            hostForm?.dispatchEvent(new CustomEvent('baystays:location-updated', {
                bubbles: true,
                detail: payload,
            }));
        };

        const applyLocationPayload = (payload) => {
            if (input) {
                input.value = payload.address || input.value;
            }
            if (addressField && addressField !== input) {
                addressField.value = payload.address || addressField.value;
            }
            if (cityField) {
                cityField.value = payload.city || '';
            }
            if (stateField) {
                stateField.value = payload.state || '';
            }
            if (countryField) {
                countryField.value = payload.country || '';
            }
            if (hiddenLat) {
                hiddenLat.value = payload.lat || '';
            }
            if (hiddenLng) {
                hiddenLng.value = payload.lng || '';
            }
            dispatchLocationUpdate(payload);
            hideSuggestions();
        };

        const applySuggestion = (item) => {
            applyLocationPayload(getLocationPayload(item));
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
            if (cityField) {
                cityField.value = '';
            }
            if (stateField) {
                stateField.value = '';
            }
            if (countryField) {
                countryField.value = '';
            }
            dispatchLocationUpdate({
                lat: '',
                lng: '',
                address: input.value || '',
                city: '',
                state: '',
                country: '',
            });
            fetchSuggestions();
        });
        input?.addEventListener('focus', fetchSuggestions);
        [cityField, stateField, countryField].forEach((field) => {
            field?.addEventListener('input', () => {
                dispatchLocationUpdate({
                    lat: hiddenLat?.value || '',
                    lng: hiddenLng?.value || '',
                    address: input?.value || addressField?.value || '',
                    city: cityField?.value || '',
                    state: stateField?.value || '',
                    country: countryField?.value || '',
                });
            });
        });
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
                if (payload.version) {
                    form.dataset.liveExploreVersion = payload.version;
                }
                markAreaUpdated(results?.closest('.results-shell') || results);
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

    const refreshExploreResults = (payload, form) => {
        const results = document.querySelector('[data-explore-results]');
        const countNode = document.querySelector('[data-results-count]');
        const avgPriceNode = document.querySelector('[data-results-price]');
        const avgRatingNode = document.querySelector('[data-results-rating]');
        const destinationNode = document.querySelector('[data-results-destination]');
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
        if (payload.version && form) {
            form.dataset.liveExploreVersion = payload.version;
        }
    };

    const initGenericLiveRegions = () => {
        document.querySelectorAll('[data-live-region]').forEach((region) => {
            if (region.dataset.liveBound === 'true') {
                return;
            }
            region.dataset.liveBound = 'true';
            const url = region.dataset.liveUrl;
            const intervalMs = Number(region.dataset.livePollInterval || 10000);
            const content = region.querySelector('[data-live-content]');
            if (!url || !content) {
                return;
            }
            let inFlight = false;
            const run = async (force = false) => {
                if (inFlight || document.hidden) {
                    return;
                }
                inFlight = true;
                try {
                    const response = await fetch(url, {
                        headers: {
                            'X-Requested-With': 'XMLHttpRequest',
                        },
                    });
                    const payload = await response.json();
                    if (!response.ok) {
                        return;
                    }
                    if (!force && payload.version && payload.version === region.dataset.liveVersion) {
                        return;
                    }
                    if (typeof payload.html === 'string') {
                        content.innerHTML = payload.html;
                    }
                    if (payload.version) {
                        region.dataset.liveVersion = payload.version;
                    }
                    markAreaUpdated(content);
                } catch (error) {
                    // Keep background syncing resilient and silent.
                } finally {
                    inFlight = false;
                }
            };
            region._runLiveRefresh = run;
            window.setInterval(() => run(false), intervalMs);
        });
    };

    const initExploreRealtime = () => {
        document.querySelectorAll('[data-live-explore]').forEach((shell) => {
            if (shell.dataset.liveBound === 'true') {
                return;
            }
            shell.dataset.liveBound = 'true';
            const form = document.querySelector('form[data-explore-form]');
            const overlay = shell.querySelector('[data-results-overlay]');
            const intervalMs = Number(shell.dataset.livePollInterval || 12000);
            if (!form) {
                return;
            }
            let inFlight = false;
            const run = async (force = false) => {
                if (inFlight || document.hidden) {
                    return;
                }
                inFlight = true;
                try {
                    const params = new URLSearchParams(new FormData(form));
                    const response = await fetch(`${form.action || window.location.pathname}?${params.toString()}`, {
                        headers: {
                            'X-Requested-With': 'XMLHttpRequest',
                        },
                    });
                    const payload = await response.json();
                    if (!response.ok) {
                        return;
                    }
                    if (!force && payload.version && payload.version === form.dataset.liveExploreVersion) {
                        return;
                    }
                    refreshExploreResults(payload, form);
                    markAreaUpdated(shell.querySelector('[data-explore-results]') || shell);
                } catch (error) {
                    // Silent in the background; manual search UI already handles visible failures.
                } finally {
                    inFlight = false;
                }
            };
            shell._runLiveRefresh = run;
            window.setInterval(() => run(false), intervalMs);
        });
    };

    const initRealtimeSocket = () => {
        const nodes = [...document.querySelectorAll('[data-live-region], [data-live-explore], [data-property-live]')];
        const signature = nodes.map((node) => node.dataset.liveGroup || '').filter(Boolean).sort().join('|');
        if (!signature) {
            return;
        }
        if (window.__baystaysRealtimeSignature === signature && window.__baystaysRealtimeSocketOpen) {
            return;
        }
        if (window.__baystaysRealtimeSocket && window.__baystaysRealtimeSocket.readyState < 2) {
            window.__baystaysRealtimeSocket.close();
        }
        window.__baystaysRealtimeSignature = signature;
        window.__baystaysRealtimeGeneration = (window.__baystaysRealtimeGeneration || 0) + 1;
        const generation = window.__baystaysRealtimeGeneration;
        const sockets = [];
        const registerSocketTarget = (socketGroups, callback) => {
            if (!socketGroups.length) {
                return;
            }
            sockets.push({ groups: socketGroups, callback });
        };

        document.querySelectorAll('[data-live-region], [data-live-explore], [data-property-live]').forEach((node) => {
            const groups = (node.dataset.liveGroup || '')
                .split(',')
                .map((group) => group.trim())
                .filter(Boolean);
            registerSocketTarget(groups, () => node._runLiveRefresh?.(true));
        });

        if (!sockets.length) {
            return;
        }

        const uniqueGroups = [...new Set(sockets.flatMap((entry) => entry.groups))];
        if (!uniqueGroups.length) {
            return;
        }

        const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
        const socketUrl = `${protocol}://${window.location.host}/ws/live/?groups=${encodeURIComponent(uniqueGroups.join(','))}`;

        const connect = () => {
            let socket;
            try {
                socket = new window.WebSocket(socketUrl);
            } catch (error) {
                return;
            }
            window.__baystaysRealtimeSocket = socket;

            socket.addEventListener('open', () => {
                window.__baystaysRealtimeSocketOpen = true;
            });

            socket.addEventListener('message', (event) => {
                try {
                    const payload = JSON.parse(event.data);
                    const targetGroups = Array.isArray(payload.groups)
                        ? payload.groups
                        : [payload.group].filter(Boolean);
                    if (!targetGroups.length) {
                        return;
                    }
                    sockets.forEach((entry) => {
                        if (entry.groups.some((group) => targetGroups.includes(group))) {
                            entry.callback();
                        }
                    });
                } catch (error) {
                    // Ignore malformed real-time payloads and keep fallback polling alive.
                }
            });

            socket.addEventListener('close', () => {
                window.__baystaysRealtimeSocketOpen = false;
                if (generation === window.__baystaysRealtimeGeneration) {
                    window.setTimeout(connect, 2500);
                }
            });
        };

        connect();
    };

    const initPropertyRealtime = () => {
        document.querySelectorAll('[data-property-live]').forEach((section) => {
            if (section.dataset.liveBound === 'true') {
                return;
            }
            section.dataset.liveBound = 'true';
            const url = section.dataset.liveUrl;
            const intervalMs = Number(section.dataset.livePollInterval || 12000);
            const availabilityRegion = section.querySelector('[data-availability-region]');
            const reviewsRegion = section.querySelector('[data-reviews-region]');
            const bookingForm = section.querySelector('form[data-async-booking]');
            if (!url || !availabilityRegion || !reviewsRegion) {
                return;
            }
            let inFlight = false;
            const run = async (force = false) => {
                if (inFlight || document.hidden) {
                    return;
                }
                inFlight = true;
                try {
                    const response = await fetch(url, {
                        headers: {
                            'X-Requested-With': 'XMLHttpRequest',
                        },
                    });
                    const payload = await response.json();
                    if (!response.ok) {
                        return;
                    }
                    if (!force && payload.version && payload.version === section.dataset.liveVersion) {
                        return;
                    }
                    if (typeof payload.availability_html === 'string') {
                        availabilityRegion.innerHTML = payload.availability_html;
                        markAreaUpdated(availabilityRegion);
                    }
                    if (typeof payload.reviews_html === 'string') {
                        reviewsRegion.innerHTML = payload.reviews_html;
                        markAreaUpdated(reviewsRegion);
                    }
                    document.querySelectorAll('[data-reviews-count-display]').forEach((node) => {
                        node.textContent = `${payload.reviews_count} review${Number(payload.reviews_count) === 1 ? '' : 's'}`;
                    });
                    document.querySelectorAll('[data-average-rating-display]').forEach((node) => {
                        node.textContent = payload.average_rating;
                    });
                    document.querySelectorAll('[data-average-rating-meter]').forEach((node) => {
                        node.style.setProperty('--rating', payload.average_rating);
                    });
                    bookingForm?._refreshAvailability?.(payload.unavailable_ranges || []);
                    if (payload.version) {
                        section.dataset.liveVersion = payload.version;
                    }
                } catch (error) {
                    // Silent refresh to avoid disrupting booking decisions.
                } finally {
                    inFlight = false;
                }
            };
            section._runLiveRefresh = run;
            window.setInterval(() => run(false), intervalMs);
        });
    };

    document.addEventListener('baystays:live-refresh', () => {
        document.querySelectorAll('[data-live-region], [data-live-explore], [data-property-live]').forEach((node) => {
            node._runLiveRefresh?.(true);
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

    const initListingMaps = () => document.querySelectorAll('[data-listing-map]').forEach((node) => {
        if (typeof window.L === 'undefined' || node.dataset.mapReady === 'true') {
            return;
        }

        const form = node.closest('form');
        const latInput = form?.querySelector('input[name="latitude"]');
        const lngInput = form?.querySelector('input[name="longitude"]');
        const addressInput = form?.querySelector('[data-location-address], input[name="address"]');
        const cityInput = form?.querySelector('[data-location-city], input[name="city"]');
        const stateInput = form?.querySelector('[data-location-state], input[name="state"]');
        const countryInput = form?.querySelector('[data-location-country], input[name="country"]');
        const summaryText = form?.querySelector('[data-location-summary-text]');

        const initialLat = Number(latInput?.value || node.dataset.lat);
        const initialLng = Number(lngInput?.value || node.dataset.lng);
        const hasInitialCoordinates = Number.isFinite(initialLat) && Number.isFinite(initialLng);
        const defaultCenter = [-0.0917, 34.768];
        const map = window.L.map(node, {
            zoomControl: false,
            scrollWheelZoom: false,
        }).setView(hasInitialCoordinates ? [initialLat, initialLng] : defaultCenter, hasInitialCoordinates ? 14 : 6);

        window.L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
            subdomains: 'abcd',
        }).addTo(map);

        const marker = window.L.circleMarker(hasInitialCoordinates ? [initialLat, initialLng] : [-0.0917, 34.768], {
            radius: 10,
            color: '#cf2338',
            fillColor: '#f97316',
            fillOpacity: 0.9,
            weight: 3,
        }).addTo(map);

        const syncSummary = (detail = {}) => {
            if (!summaryText) {
                return;
            }
            const address = detail.address || addressInput?.value || node.dataset.address || '';
            const city = detail.city || cityInput?.value || node.dataset.city || '';
            const state = detail.state || stateInput?.value || '';
            const country = detail.country || countryInput?.value || node.dataset.country || '';
            const fragments = [address, city, state, country].filter(Boolean);
            summaryText.textContent = fragments.length
                ? fragments.join(', ')
                : 'Search for an address or choose a suggestion to lock in the same style of location data guests browse with in Explore Stays.';
        };

        const syncMap = (detail = {}) => {
            const lat = Number(detail.lat || latInput?.value || node.dataset.lat);
            const lng = Number(detail.lng || lngInput?.value || node.dataset.lng);
            syncSummary(detail);
            if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
                marker.setStyle({ opacity: 0, fillOpacity: 0 });
                map.setView(defaultCenter, 6);
                return;
            }
            marker.setStyle({ opacity: 1, fillOpacity: 0.9 });
            marker.setLatLng([lat, lng]);
            map.flyTo([lat, lng], 14, {
                animate: false,
            });
        };

        const reverseGeocode = debounce(async (lat, lng) => {
            try {
                const response = await fetch(`https://nominatim.openstreetmap.org/reverse?format=jsonv2&addressdetails=1&lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lng)}`, {
                    headers: {
                        'Accept': 'application/json',
                    },
                });
                const payload = await response.json();
                if (!payload || !payload.address) {
                    return;
                }
                const locationPayload = getLocationPayload({
                    ...payload,
                    lat,
                    lon: lng,
                });
                if (!locationPayload.address && payload.display_name) {
                    locationPayload.address = payload.display_name.split(',')[0] || '';
                }
                form?.dispatchEvent(new CustomEvent('baystays:apply-location', {
                    bubbles: true,
                    detail: locationPayload,
                }));
            } catch (error) {
                // Let the map interaction stay responsive even if reverse geocoding fails.
            }
        }, 220);

        form?.addEventListener('baystays:location-updated', (event) => {
            syncMap(event.detail || {});
        });

        form?.addEventListener('baystays:apply-location', (event) => {
            const detail = event.detail || {};
            if (latInput) {
                latInput.value = detail.lat || '';
            }
            if (lngInput) {
                lngInput.value = detail.lng || '';
            }
            if (addressInput) {
                addressInput.value = detail.address || '';
            }
            if (cityInput) {
                cityInput.value = detail.city || '';
            }
            if (stateInput) {
                stateInput.value = detail.state || '';
            }
            if (countryInput) {
                countryInput.value = detail.country || '';
            }
            syncMap(detail);
        });

        map.on('click', (event) => {
            const lat = event.latlng.lat.toFixed(6);
            const lng = event.latlng.lng.toFixed(6);
            if (latInput) {
                latInput.value = lat;
            }
            if (lngInput) {
                lngInput.value = lng;
            }
            syncMap({
                lat,
                lng,
                address: addressInput?.value || '',
                city: cityInput?.value || '',
                state: stateInput?.value || '',
                country: countryInput?.value || '',
            });
            reverseGeocode(lat, lng);
        });

        syncMap({
            lat: latInput?.value || node.dataset.lat,
            lng: lngInput?.value || node.dataset.lng,
            address: addressInput?.value || node.dataset.address,
            city: cityInput?.value || node.dataset.city,
            state: stateInput?.value || '',
            country: countryInput?.value || node.dataset.country,
        });
        window.setTimeout(() => map.invalidateSize(), 120);
        node.dataset.mapReady = 'true';
    });

    initGenericLiveRegions();
    initExploreRealtime();
    initPropertyRealtime();
    initRealtimeSocket();
    initPropertyMaps();
    initListingMaps();

    window.addEventListener('pageshow', () => setLoader(false));
    window.addEventListener('load', () => {
        setLoader(false);
        initGenericLiveRegions();
        initExploreRealtime();
        initPropertyRealtime();
        initRealtimeSocket();
        initPropertyMaps();
        initListingMaps();
    });
})();
