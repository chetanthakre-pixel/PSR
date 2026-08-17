document.addEventListener('DOMContentLoaded', () => {
    // API endpoint helper
    const API_BASE = window.location.origin.includes('localhost') || window.location.origin.includes('127.0.0.1')
        ? window.location.origin
        : 'http://localhost:8000';

    // Controls
    const runBtn = document.getElementById('run-btn');
    const imageSelect = document.getElementById('image-select');
    const imageUpload = document.getElementById('image-upload');
    const dropZone = document.getElementById('drop-zone');
    const dropzoneContent = document.getElementById('dropzone-content');
    const fileBadge = document.getElementById('file-badge');
    const fileName = document.getElementById('file-name');
    const fileSize = document.getElementById('file-size');
    const removeFileBtn = document.getElementById('remove-file-btn');

    const clipLimit = document.getElementById('clip-limit');
    const tileSize = document.getElementById('tile-size');
    const clipVal = document.getElementById('clip-val');
    const tileVal = document.getElementById('tile-val');
    const tileVal2 = document.getElementById('tile-val2');

    // Tabs
    const tabDenoise = document.getElementById('tab-denoise');
    const tabIllum = document.getElementById('tab-illum');
    const tabCompare = document.getElementById('tab-compare');
    const denoiseView = document.getElementById('denoise-view');
    const illumView = document.getElementById('illum-view');
    const compareView = document.getElementById('compare-view');

    // UI View Containers
    const welcome = document.getElementById('welcome');
    const loading = document.getElementById('loading');
    const results = document.getElementById('results');
    const illumEmpty = document.getElementById('illum-empty');
    const illumResults = document.getElementById('illum-results');
    const compareEmpty = document.getElementById('compare-empty');
    const compareResults = document.getElementById('compare-results');

    // Image Elements
    const imgOrig = document.getElementById('img-orig');
    const imgNorm = document.getElementById('img-norm');
    const imgClahe = document.getElementById('img-clahe');
    const denoisersGrid = document.getElementById('denoisers-grid');
    const winnerName = document.getElementById('winner-name');
    const winnerReason = document.getElementById('winner-reason');
    const downloadBtn = document.getElementById('download-btn');

    // Illumination Elements
    const imgIllumGray = document.getElementById('img-illum-gray');
    const imgIllumColor = document.getElementById('img-illum-color');
    const illumGrayMethod = document.getElementById('illum-gray-method');
    const downloadGrayBtn = document.getElementById('download-gray-btn');
    const downloadIllumBtn = document.getElementById('download-illum-btn');

    // Compare Elements
    const imgCompareRaw = document.getElementById('img-compare-raw');
    const imgCompareClean = document.getElementById('img-compare-clean');
    const compareMethod = document.getElementById('compare-method');

    let currentTab = 'denoise';
    let hasData = false;
    let selectedFile = null;

    // Helper: Format file size
    function formatFileSize(bytes) {
        if (!bytes || bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    // Helper: File Download
    function triggerDownload(base64Data, filename) {
        const link = document.createElement('a');
        link.href = `data:image/jpeg;base64,${base64Data}`;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    // Tab Switching
    const allTabs = [tabDenoise, tabIllum, tabCompare];
    const allViews = [denoiseView, illumView, compareView];

    function setTab(tab) {
        currentTab = tab;
        // Deactivate all tabs & hide all views
        allTabs.forEach(t => t.classList.remove('active'));
        allViews.forEach(v => v.classList.add('hidden'));

        if (tab === 'denoise') {
            tabDenoise.classList.add('active');
            denoiseView.classList.remove('hidden');
            if (hasData) { welcome.classList.add('hidden'); results.classList.remove('hidden'); }
            else { welcome.classList.remove('hidden'); results.classList.add('hidden'); }
        } else if (tab === 'illum') {
            tabIllum.classList.add('active');
            illumView.classList.remove('hidden');
            if (hasData) { illumEmpty.classList.add('hidden'); illumResults.classList.remove('hidden'); }
            else { illumEmpty.classList.remove('hidden'); illumResults.classList.add('hidden'); }
        } else if (tab === 'compare') {
            tabCompare.classList.add('active');
            compareView.classList.remove('hidden');
            if (hasData) { compareEmpty.classList.add('hidden'); compareResults.classList.remove('hidden'); }
            else { compareEmpty.classList.remove('hidden'); compareResults.classList.add('hidden'); }
        }
    }

    tabDenoise.addEventListener('click', () => setTab('denoise'));
    tabIllum.addEventListener('click', () => setTab('illum'));
    tabCompare.addEventListener('click', () => setTab('compare'));

    // Live parameter labels
    clipLimit.addEventListener('input', (e) => {
        clipVal.textContent = parseFloat(e.target.value).toFixed(1);
    });
    tileSize.addEventListener('input', (e) => {
        tileVal.textContent = e.target.value;
        if (tileVal2) tileVal2.textContent = e.target.value;
    });

    // Handle File Selection
    function updateFilePreview(file) {
        if (file) {
            selectedFile = file;
            fileName.textContent = file.name;
            fileSize.textContent = formatFileSize(file.size);
            fileBadge.classList.remove('hidden');
            dropzoneContent.classList.add('hidden');
            imageSelect.value = ''; // Clear dropdown selection to indicate custom file is active
        } else {
            selectedFile = null;
            imageUpload.value = '';
            fileBadge.classList.add('hidden');
            dropzoneContent.classList.remove('hidden');
        }
    }

    imageUpload.addEventListener('change', (e) => {
        if (e.target.files && e.target.files.length > 0) {
            updateFilePreview(e.target.files[0]);
        }
    });

    if (removeFileBtn) {
        removeFileBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            e.preventDefault();
            updateFilePreview(null);
            // Default back to psr_source.jpg if available
            if ([...imageSelect.options].some(opt => opt.value === 'psr_source.jpg')) {
                imageSelect.value = 'psr_source.jpg';
            }
        });
    }

    // Handle Drag & Drop on Upload Dropzone
    if (dropZone) {
        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropZone.classList.add('dragover');
            }, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropZone.classList.remove('dragover');
            }, false);
        });

        dropZone.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            if (dt && dt.files && dt.files.length > 0) {
                imageUpload.files = dt.files;
                updateFilePreview(dt.files[0]);
            }
        });
    }

    // When dropdown changes, clear uploaded custom file
    imageSelect.addEventListener('change', (e) => {
        if (e.target.value !== '') {
            updateFilePreview(null);
        }
    });

    // Populate available images from backend
    async function loadImages() {
        try {
            const res = await fetch(`${API_BASE}/images`);
            if (res.ok) {
                const images = await res.json();
                imageSelect.innerHTML = '<option value="">-- Select Swath --</option>';
                images.forEach((img) => {
                    const opt = document.createElement('option');
                    opt.value = img;
                    opt.textContent = img === 'psr_source.jpg' ? 'psr_source.jpg (Chandrayaan-2)' : img;
                    imageSelect.appendChild(opt);
                });
                if (images.includes('psr_source.jpg') && !selectedFile) {
                    imageSelect.value = 'psr_source.jpg';
                }
            }
        } catch (err) {
            console.warn('Could not fetch image list from server', err);
        }
    }
    loadImages();

    // Pipeline Execution Handler
    runBtn.addEventListener('click', async () => {
        const formData = new FormData();
        formData.append('clip', parseFloat(clipLimit.value));
        formData.append('tile', parseInt(tileSize.value));

        const fileToUpload = selectedFile || (imageUpload.files && imageUpload.files.length > 0 ? imageUpload.files[0] : null);

        if (fileToUpload) {
            formData.append('image', fileToUpload);
        } else if (imageSelect.value) {
            formData.append('image_name', imageSelect.value);
        } else {
            alert('Please select a sample swath or choose an image file to upload.');
            return;
        }

        // Show loading state
        welcome.classList.add('hidden');
        results.classList.add('hidden');
        illumEmpty.classList.add('hidden');
        illumResults.classList.add('hidden');
        compareEmpty.classList.add('hidden');
        compareResults.classList.add('hidden');
        loading.classList.remove('hidden');

        try {
            const response = await fetch(`${API_BASE}/run-pipeline`, {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.error || `Server error (Status ${response.status})`);
            }

            const data = await response.json();
            if (data.error) {
                alert(`Error: ${data.error}`);
                loading.classList.add('hidden');
                setTab(currentTab);
                return;
            }

            hasData = true;

            // Stage 1: Preprocessing Images
            imgOrig.src = `data:image/jpeg;base64,${data.preprocessing.original}`;
            imgNorm.src = `data:image/jpeg;base64,${data.preprocessing.normalized}`;
            imgClahe.src = `data:image/jpeg;base64,${data.preprocessing.clahe}`;

            // Winner Announcement
            winnerName.textContent = data.best_method;
            if (winnerReason) {
                winnerReason.textContent = `Optimal algorithm determined via multi-criteria objective score (${data.ranking[0][1].toFixed(4)}) prioritizing edge retention (EdgePI) and contrast (CNR).`;
            }

            // Stage 2: Enhancement Benchmarks
            denoisersGrid.innerHTML = '';
            data.ranking.forEach(([methodName, score]) => {
                const res = data.results[methodName];
                const isBest = methodName === data.best_method;

                const card = document.createElement('div');
                card.className = `img-card ${isBest ? 'best' : ''}`;

                card.innerHTML = `
                    <div class="img-card-head">
                        <span style="color: ${isBest ? 'var(--accent)' : 'inherit'}; font-weight: 600;">
                            ${methodName} ${isBest ? '🏆 [BEST]' : ''}
                        </span>
                        <span style="color: var(--txt-dim); font-size: 0.68rem;">⏱ ${res.metrics._time.toFixed(2)}s</span>
                    </div>
                    <div class="compare-box">
                        <img class="img-clean" src="data:image/jpeg;base64,${res.image}" alt="${methodName} Denoised">
                        <img class="img-noisy" src="data:image/jpeg;base64,${data.preprocessing.clahe}" alt="Pre-denoised CLAHE">
                        <div class="compare-badge">HOVER TO COMPARE</div>
                    </div>
                    <div class="mcard">
                        <div class="mrow"><span class="mk">Weighted Score</span><span class="mv ${isBest ? 'best-v' : ''}">${score.toFixed(4)}</span></div>
                        <div class="mrow"><span class="mk">EdgePI (Edge Preservation)</span><span class="mv">${res.metrics.EdgePI.toFixed(4)}</span></div>
                        <div class="mrow"><span class="mk">CNR (Contrast-to-Noise)</span><span class="mv">${res.metrics.CNR.toFixed(4)}</span></div>
                        <div class="mrow"><span class="mk">SNR (Signal-to-Noise)</span><span class="mv">${res.metrics.SNR.toFixed(4)}</span></div>
                        <div class="mrow"><span class="mk">Entropy (Information Density)</span><span class="mv">${res.metrics.Entropy.toFixed(4)}</span></div>
                    </div>
                `;
                denoisersGrid.appendChild(card);
            });

            // Stage 3: Illumination Map
            const bestImageBase64 = data.results[data.best_method].image;
            imgIllumGray.src = `data:image/jpeg;base64,${bestImageBase64}`;
            if (illumGrayMethod) {
                illumGrayMethod.textContent = data.best_method;
            }

            if (data.illumination_map) {
                imgIllumColor.src = `data:image/jpeg;base64,${data.illumination_map}`;
            }

            // Download Buttons
            if (downloadBtn) {
                downloadBtn.onclick = () => {
                    triggerDownload(bestImageBase64, `PSR_Cleaned_${data.best_method.replace(/\s+/g, '_')}.jpg`);
                };
            }
            if (downloadGrayBtn) {
                downloadGrayBtn.onclick = () => {
                    triggerDownload(bestImageBase64, `PSR_Optimal_Grayscale_${data.best_method.replace(/\s+/g, '_')}.jpg`);
                };
            }
            if (downloadIllumBtn && data.illumination_map) {
                downloadIllumBtn.onclick = () => {
                    triggerDownload(data.illumination_map, `PSR_Relative_Illumination_Inferno_${data.best_method.replace(/\s+/g, '_')}.jpg`);
                };
            }

            // Final Compare tab images
            imgCompareRaw.src = `data:image/jpeg;base64,${data.preprocessing.original}`;
            imgCompareClean.src = `data:image/jpeg;base64,${bestImageBase64}`;
            if (compareMethod) compareMethod.textContent = data.best_method;
            resetZoom();

            // Done loading
            loading.classList.add('hidden');
            setTab(currentTab);
        } catch (error) {
            console.error('Pipeline execution error:', error);
            alert(`Execution failed: ${error.message || 'Could not connect to backend server.'}`);
            loading.classList.add('hidden');
            setTab(currentTab);
        }
    });

    // ─── Synchronized Zoom & Pan Engine ─────────────────────────────
    const vpRaw = document.getElementById('zoom-vp-raw');
    const vpClean = document.getElementById('zoom-vp-clean');
    const zoomLevelDisplay = document.getElementById('zoom-level');
    const zoomResetBtn = document.getElementById('zoom-reset-btn');
    const zoomFitBtn = document.getElementById('zoom-fit-btn');

    let zoomScale = 1;
    let panX = 0, panY = 0;
    let isDragging = false;
    let dragStartX = 0, dragStartY = 0;
    let panStartX = 0, panStartY = 0;
    const MIN_ZOOM = 0.5;
    const MAX_ZOOM = 10;

    function applyTransform() {
        const t = `translate(${panX}px, ${panY}px) scale(${zoomScale})`;
        imgCompareRaw.style.transform = t;
        imgCompareClean.style.transform = t;
        zoomLevelDisplay.textContent = Math.round(zoomScale * 100) + '%';
    }

    function resetZoom() {
        zoomScale = 1;
        panX = 0;
        panY = 0;
        applyTransform();
    }

    function fitToView() {
        if (!vpRaw || !imgCompareRaw.naturalWidth) return;
        const vpW = vpRaw.clientWidth;
        const vpH = vpRaw.clientHeight;
        const imgW = imgCompareRaw.naturalWidth;
        const imgH = imgCompareRaw.naturalHeight;
        zoomScale = Math.min(vpW / imgW, vpH / imgH);
        panX = (vpW - imgW * zoomScale) / 2;
        panY = (vpH - imgH * zoomScale) / 2;
        applyTransform();
    }

    if (zoomResetBtn) zoomResetBtn.addEventListener('click', resetZoom);
    if (zoomFitBtn) zoomFitBtn.addEventListener('click', fitToView);

    // Attach zoom/pan to both viewports
    [vpRaw, vpClean].forEach(vp => {
        if (!vp) return;

        // Scroll-to-zoom (zoom towards cursor position)
        vp.addEventListener('wheel', (e) => {
            e.preventDefault();
            const rect = vp.getBoundingClientRect();
            const mx = e.clientX - rect.left;
            const my = e.clientY - rect.top;

            const oldScale = zoomScale;
            const factor = e.deltaY < 0 ? 1.15 : 1 / 1.15;
            zoomScale = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, zoomScale * factor));

            // Adjust pan so cursor position stays fixed
            panX = mx - (mx - panX) * (zoomScale / oldScale);
            panY = my - (my - panY) * (zoomScale / oldScale);
            applyTransform();
        }, { passive: false });

        // Click-drag to pan
        vp.addEventListener('mousedown', (e) => {
            if (e.button !== 0) return;
            isDragging = true;
            dragStartX = e.clientX;
            dragStartY = e.clientY;
            panStartX = panX;
            panStartY = panY;
            e.preventDefault();
        });
    });

    document.addEventListener('mousemove', (e) => {
        if (!isDragging) return;
        panX = panStartX + (e.clientX - dragStartX);
        panY = panStartY + (e.clientY - dragStartY);
        applyTransform();
    });

    document.addEventListener('mouseup', () => {
        isDragging = false;
    });

    // Fit images on first load into the compare view
    imgCompareRaw.addEventListener('load', fitToView);
});
