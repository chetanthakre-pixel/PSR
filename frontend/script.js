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
    const imgHistogram = document.getElementById('img-histogram');
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

    // Helper: File Download (always PNG — encode_img on server uses cv2.imencode('.png'))
    function triggerDownload(base64Data, filename) {
        const link = document.createElement('a');
        link.href = `data:image/png;base64,${base64Data}`;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    function countUp(el, endVal, isInt, duration = 800) {
        if (!el || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
            if (el) el.textContent = isInt ? endVal : endVal.toFixed(4);
            return;
        }
        let startTimestamp = null;
        const step = (timestamp) => {
            if (!startTimestamp) startTimestamp = timestamp;
            const progress = Math.min((timestamp - startTimestamp) / duration, 1);
            const easeProgress = 1 - Math.pow(1 - progress, 3);
            const currentVal = easeProgress * endVal;
            el.textContent = isInt ? Math.round(currentVal) : currentVal.toFixed(4);
            if (progress < 1) {
                window.requestAnimationFrame(step);
            } else {
                el.textContent = isInt ? endVal : endVal.toFixed(4);
            }
        };
        window.requestAnimationFrame(step);
    }

    // Tab Switching
    const allTabs = [tabDenoise, tabIllum, tabCompare];
    const allViews = [denoiseView, illumView, compareView];

    function setTab(tab) {
        currentTab = tab;
        // Deactivate all tabs & hide all views
        allTabs.forEach(t => t.classList.remove('active'));
        
        const container = document.querySelector('.content');
        if (container) {
            container.classList.add('glitch-effect');
            setTimeout(() => container.classList.remove('glitch-effect'), 150);
        }
        
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
    
    // Crop labels
    const cropX = document.getElementById('crop-x');
    const cropY = document.getElementById('crop-y');
    const cropXVal = document.getElementById('crop-x-val');
    const cropYVal = document.getElementById('crop-y-val');
    
    if (cropX) {
        cropX.addEventListener('input', (e) => cropXVal.textContent = e.target.value);
    }
    if (cropY) {
        cropY.addEventListener('input', (e) => cropYVal.textContent = e.target.value);
    }

    // Handle File Selection
    function updateFilePreview(file) {
        const metadataSection = document.getElementById('metadata-section');
        const cropSection = document.getElementById('crop-section');
        const previewContainer = document.getElementById('upload-preview-container');
        const previewImg = document.getElementById('upload-preview-img');
        if (file) {
            selectedFile = file;
            fileName.textContent = file.name;
            fileSize.textContent = formatFileSize(file.size);
            fileBadge.classList.remove('hidden');
            dropzoneContent.classList.add('hidden');
            imageSelect.value = ''; // Clear dropdown selection to indicate custom file is active
            if (metadataSection) metadataSection.style.display = 'none';
            if (cropSection) cropSection.style.display = 'none'; // Hide native crop tool for custom files
            
            const reader = new FileReader();
            reader.onload = (e) => {
                if(previewImg) previewImg.src = e.target.result;
                if(previewContainer) previewContainer.classList.remove('hidden');
            };
            reader.readAsDataURL(file);
        } else {
            selectedFile = null;
            if(previewContainer) previewContainer.classList.add('hidden');
            if(previewImg) previewImg.src = '';
            imageUpload.value = '';
            fileBadge.classList.add('hidden');
            dropzoneContent.classList.remove('hidden');
            if (cropSection) cropSection.style.display = 'block'; // Show crop tool again
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

    const metadataSection = document.getElementById('metadata-section');
    const metadataContent = document.getElementById('metadata-content');

    async function fetchMetadata(imageName) {
        if (!imageName || imageName === 'psr_source.jpg') {
            if (metadataSection) metadataSection.style.display = 'none';
            return;
        }
        try {
            const res = await fetch(`${API_BASE}/metadata/${imageName}`);
            if (res.ok) {
                const data = await res.json();
                if (data.available && metadataSection && metadataContent) {
                    let html = `<div style="margin-bottom: 4px;"><strong>Orbit:</strong> ${data.orbit_number}</div>`;
                    html += `<div style="margin-bottom: 4px;"><strong>Date:</strong> ${data.start_date_time && data.start_date_time.split('T')[0]}</div>`;
                    html += `<div style="margin-bottom: 4px;"><strong>Lat/Lon:</strong><br>${data.latitude}°, ${data.longitude}°</div>`;
                    html += `<div style="margin-bottom: 4px;"><strong>Solar Incidence:</strong> ${data.incidence_angle}°</div>`;
                    html += `<div style="margin-bottom: 4px;"><strong>Sun Elevation:</strong> ${data.emission_angle}°</div>`;
                    metadataContent.innerHTML = html;
                    metadataSection.style.display = 'block';
                } else {
                    if (metadataSection) metadataSection.style.display = 'none';
                }
            }
        } catch (e) {
            console.error("Failed to fetch metadata", e);
        }
    }

    // When dropdown changes, clear uploaded custom file and fetch metadata
    imageSelect.addEventListener('change', (e) => {
        if (e.target.value !== '') {
            updateFilePreview(null);
            fetchMetadata(e.target.value);
        } else {
            if (metadataSection) metadataSection.style.display = 'none';
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

    // Global reference for metrics export
    let lastMetricsData = null;

    // Helper: generate delta badge
    function getDeltaBadge(current, baseline, higherIsBetter) {
        if (baseline === 0) return '';
        const pct = ((current - baseline) / Math.abs(baseline)) * 100;
        if (Math.abs(pct) < 0.1) return `<span class="delta-badge delta-neu">~0%</span>`;
        const sign = pct > 0 ? '+' : '';
        const cls = (pct > 0 && higherIsBetter) || (pct < 0 && !higherIsBetter) ? 'delta-pos' : 'delta-neg';
        return `<span class="delta-badge ${cls}">${sign}${pct.toFixed(1)}%</span>`;
    }

    // Pipeline Execution Handler
    runBtn.addEventListener('click', async () => {
        const formData = new FormData();
        formData.append('clip', parseFloat(clipLimit.value));
        formData.append('tile', parseInt(tileSize.value));
        if (cropX) formData.append('crop_x', parseFloat(cropX.value));
        if (cropY) formData.append('crop_y', parseFloat(cropY.value));

        const fileToUpload = selectedFile || (imageUpload.files && imageUpload.files.length > 0 ? imageUpload.files[0] : null);

        if (fileToUpload) {
            formData.append('image', fileToUpload);
        } else if (imageSelect.value) {
            formData.append('image_name', imageSelect.value);
        } else {
            alert('Please select a sample swath or choose an image file to upload.');
            return;
        }

        // Show loading state & update status indicator
        const statusText = document.getElementById('status-text');
        const statusDot = document.getElementById('status-dot');
        if (statusText) statusText.textContent = "PROCESSING...";
        if (statusDot) statusDot.style.background = "#F5D061";
        
        welcome.classList.add('hidden');
        results.classList.add('hidden');
        illumEmpty.classList.add('hidden');
        illumResults.classList.add('hidden');
        compareEmpty.classList.add('hidden');
        compareResults.classList.add('hidden');
        loading.classList.remove('hidden');

        const pipelineStages = document.getElementById('pipeline-stages');
        const scanBeam = document.getElementById('scan-beam');
        let stageInterval = null;
        if (pipelineStages) pipelineStages.classList.remove('hidden');
        if (scanBeam) scanBeam.classList.add('scanning');

        [1,2,3,4].forEach(i => {
            const s = document.getElementById(`stage-${i}`);
            if(s) { s.classList.remove('active'); s.classList.remove('done'); }
        });
        let currentStage = 1;
        const setStage = (s) => {
            if(s > 1) {
                const prev = document.getElementById(`stage-${s-1}`);
                if(prev) { prev.classList.remove('active'); prev.classList.add('done'); }
            }
            const curr = document.getElementById(`stage-${s}`);
            if(curr) curr.classList.add('active');
        };
        setStage(1);

        stageInterval = setInterval(() => {
            currentStage++;
            if(currentStage <= 4) {
                setStage(currentStage);
            } else {
                clearInterval(stageInterval);
            }
        }, 1200);

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
                if (statusText) statusText.textContent = "TELEMETRY READY";
                if (statusDot) statusDot.style.background = "var(--success)";
                setTab(currentTab);
                return;
            }

            hasData = true;
            lastMetricsData = data; // store for CSV export

            // Stage 1: Preprocessing Images
            imgOrig.src = `data:image/png;base64,${data.preprocessing.original}`;
            imgNorm.src = `data:image/png;base64,${data.preprocessing.normalized}`;
            imgClahe.src = `data:image/png;base64,${data.preprocessing.clahe}`;
            
            if (data.preprocessing.histogram_plot && imgHistogram) {
                imgHistogram.src = `data:image/png;base64,${data.preprocessing.histogram_plot}`;
                const histContainer = document.getElementById('histogram-container');
                if (histContainer) histContainer.classList.remove('hidden');
            } else if (imgHistogram) {
                const histContainer = document.getElementById('histogram-container');
                if (histContainer) histContainer.classList.add('hidden');
            }

            // Winner Announcement
            winnerName.textContent = `${data.best_method} — Recommended`;
            if (winnerReason) {
                winnerReason.textContent = `Optimal algorithm determined via multi-criteria objective score (${data.ranking[0][1].toFixed(4)}) prioritizing edge retention (EdgePI) and contrast (CNR).`;
            }

            // Baseline metrics for deltas
            const baseM = data.preprocessing.baseline_metrics;

            // Stage 2: Enhancement Benchmarks
            denoisersGrid.innerHTML = '';
            data.ranking.forEach(([methodName, score]) => {
                const res = data.results[methodName];
                const isBest = methodName === data.best_method;

                const card = document.createElement('div');
                card.className = `img-card ${isBest ? 'best' : ''}`;

                card.innerHTML = `
                    ${isBest ? '<div class="reticle reticle-tl"></div><div class="reticle reticle-tr"></div><div class="reticle reticle-bl"></div><div class="reticle reticle-br"></div>' : ''}
                    <div class="img-card-head">
                        <span style="color: ${isBest ? 'var(--accent)' : 'inherit'}; font-weight: 600;">
                            ${methodName} ${isBest ? '🏆' : ''}
                        </span>
                        <div class="card-head-right">
                            <span style="color: var(--txt-dim); font-size: 0.68rem; margin-right: 6px;">⏱ ${res.metrics._time.toFixed(2)}s</span>
                            <button class="card-download-btn" title="Download Image" data-method="${methodName}">⬇</button>
                        </div>
                    </div>
                    <div class="compare-box">
                        <img class="img-clean" src="data:image/png;base64,${res.image}" alt="${methodName} Denoised">
                        <img class="img-noisy" src="data:image/png;base64,${data.preprocessing.clahe}" alt="Pre-denoised CLAHE">
                        <div class="compare-badge">HOVER/TAP TO COMPARE</div>
                        <div class="compare-crosshair"></div>
                    </div>
                    <div class="mcard">
                        <div class="mrow">
                            <span class="mk">Weighted Score <span class="info-tooltip" data-tooltip="Weighted for PSR use-case: prioritizes CNR + Entropy for shadow-detail recovery.">ⓘ</span></span>
                            <span class="mv ${isBest ? 'best-v' : ''}"><span class="num-val" data-val="${score}">0.0000</span></span>
                        </div>
                        <div class="mrow">
                            <span class="mk">EdgePI</span>
                            <span class="mv"><span class="num-val" data-val="${res.metrics.EdgePI}">0.0000</span> ${baseM ? getDeltaBadge(res.metrics.EdgePI, baseM.EdgePI, true) : ''}</span>
                        </div>
                        <div class="mrow">
                            <span class="mk">CNR</span>
                            <span class="mv"><span class="num-val" data-val="${res.metrics.CNR}">0.0000</span> ${baseM ? getDeltaBadge(res.metrics.CNR, baseM.CNR, true) : ''}</span>
                        </div>
                        <div class="mrow">
                            <span class="mk">SNR</span>
                            <span class="mv"><span class="num-val" data-val="${res.metrics.SNR}">0.0000</span> ${baseM ? getDeltaBadge(res.metrics.SNR, baseM.SNR, true) : ''}</span>
                        </div>
                        <div class="mrow">
                            <span class="mk">Entropy</span>
                            <span class="mv"><span class="num-val" data-val="${res.metrics.Entropy}">0.0000</span> ${baseM ? getDeltaBadge(res.metrics.Entropy, baseM.Entropy, true) : ''}</span>
                        </div>
                    </div>
                `;
                
                // Wire individual download button
                const btn = card.querySelector('.card-download-btn');
                btn.addEventListener('click', () => {
                    triggerDownload(res.image, `PSR_${methodName.replace(/ /g, '_')}.png`);
                });

                denoisersGrid.appendChild(card);
                
                const compareBox = card.querySelector('.compare-box');
                const crosshair = card.querySelector('.compare-crosshair');
                if(compareBox && crosshair) {
                    compareBox.addEventListener('mousemove', (e) => {
                        const rect = compareBox.getBoundingClientRect();
                        crosshair.style.left = `${e.clientX - rect.left}px`;
                        crosshair.style.top = `${e.clientY - rect.top}px`;
                    });
                }

                setTimeout(() => {
                    card.querySelectorAll('.mrow').forEach(mrow => mrow.classList.add('animate-bar'));
                    card.querySelectorAll('.num-val').forEach(el => {
                        countUp(el, parseFloat(el.getAttribute('data-val')), false, 800);
                    });
                }, 50);
            });

            // Stage 3: Illumination Map
            const bestImageBase64 = data.results[data.best_method].image;
            imgIllumGray.src = `data:image/png;base64,${bestImageBase64}`;
            if (illumGrayMethod) {
                illumGrayMethod.textContent = data.best_method;
            }

            if (data.illumination_map) {
                imgIllumColor.src = `data:image/png;base64,${data.illumination_map}`;
            }

            // Download Buttons (highest quality PNG)
            if (downloadBtn) {
                downloadBtn.onclick = () => {
                    triggerDownload(bestImageBase64, `PSR_Cleaned_${data.best_method.replace(/\s+/g, '_')}.png`);
                };
            }
            if (downloadGrayBtn) {
                downloadGrayBtn.onclick = () => {
                    triggerDownload(bestImageBase64, `PSR_Optimal_Grayscale_${data.best_method.replace(/\s+/g, '_')}.png`);
                };
            }
            if (downloadIllumBtn && data.illumination_map) {
                downloadIllumBtn.onclick = () => {
                    triggerDownload(data.illumination_map, `PSR_Relative_Illumination_Inferno_${data.best_method.replace(/\s+/g, '_')}.png`);
                };
            }

            // Preprocessing + Histogram download buttons — enable & wire up
            const dlOrig = document.getElementById('download-orig-btn');
            if (dlOrig) { dlOrig.disabled = false; dlOrig.onclick = () => triggerDownload(data.preprocessing.original, 'PSR_Raw_Input.png'); }
            const dlNorm = document.getElementById('download-norm-btn');
            if (dlNorm) { dlNorm.disabled = false; dlNorm.onclick = () => triggerDownload(data.preprocessing.normalized, 'PSR_Normalized.png'); }
            const dlClahe = document.getElementById('download-clahe-btn');
            if (dlClahe) { dlClahe.disabled = false; dlClahe.onclick = () => triggerDownload(data.preprocessing.clahe, 'PSR_CLAHE_Enhanced.png'); }
            const dlHist = document.getElementById('download-histogram-btn');
            if (dlHist && data.preprocessing.histogram_plot) { dlHist.disabled = false; dlHist.onclick = () => triggerDownload(data.preprocessing.histogram_plot, 'PSR_Histogram_Plot.png'); }
            
            // Export Metrics Button
            const exportMetricsBtn = document.getElementById('export-metrics-btn');
            if (exportMetricsBtn) {
                exportMetricsBtn.onclick = () => {
                    if (!lastMetricsData) return;
                    let csv = "Algorithm,Weighted Score,EdgePI,CNR,SNR,Entropy,Time(s)\n";
                    // Include baseline
                    if (lastMetricsData.preprocessing.baseline_metrics) {
                        const m = lastMetricsData.preprocessing.baseline_metrics;
                        csv += `Baseline (CLAHE),${m._score.toFixed(4)},${m.EdgePI.toFixed(4)},${m.CNR.toFixed(4)},${m.SNR.toFixed(4)},${m.Entropy.toFixed(4)},0.0\n`;
                    }
                    lastMetricsData.ranking.forEach(([name, score]) => {
                        const m = lastMetricsData.results[name].metrics;
                        csv += `${name},${score.toFixed(4)},${m.EdgePI.toFixed(4)},${m.CNR.toFixed(4)},${m.SNR.toFixed(4)},${m.Entropy.toFixed(4)},${m._time.toFixed(3)}\n`;
                    });
                    const blob = new Blob([csv], { type: 'text/csv' });
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = "PSR_Metrics_Report.csv";
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    document.body.removeChild(a);
                };
            }

            // Final Compare tab images
            imgCompareRaw.src = `data:image/png;base64,${data.preprocessing.original}`;
            imgCompareClean.src = `data:image/png;base64,${bestImageBase64}`;
            if (compareMethod) compareMethod.textContent = data.best_method;
            resetZoom();

            // Done loading
            if(stageInterval) clearInterval(stageInterval);
            const s4 = document.getElementById('stage-4');
            if(s4) { s4.classList.remove('active'); s4.classList.add('done'); }
            if (scanBeam) scanBeam.classList.remove('scanning');
            setTimeout(() => { if (pipelineStages) pipelineStages.classList.add('hidden'); }, 2000);

            loading.classList.add('hidden');
            if (statusText) statusText.textContent = "TELEMETRY READY";
            if (statusDot) statusDot.style.background = "var(--success)";
            setTab(currentTab);
        } catch (error) {
            if(stageInterval) clearInterval(stageInterval);
            if (scanBeam) scanBeam.classList.remove('scanning');
            console.error('Pipeline execution error:', error);
            alert(`Execution failed: ${error.message || 'Could not connect to backend server.'}`);
            loading.classList.add('hidden');
            if (statusText) statusText.textContent = "TELEMETRY READY";
            if (statusDot) statusDot.style.background = "var(--success)";
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
