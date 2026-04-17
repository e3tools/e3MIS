$(function () {
    // ─── Recommended icons for field work ────────────────────────────────
    const RECOMMENDED_ICONS = [
        'fa-home', 'fa-tree', 'fa-school', 'fa-users', 'fa-industry',
        'fa-seedling', 'fa-tractor', 'fa-stethoscope', 'fa-water',
        'fa-wheat-awn', 'fa-cow', 'fa-hospital', 'fa-building',
        'fa-person', 'fa-children', 'fa-hand-holding-heart',
        'fa-truck', 'fa-road', 'fa-bridge', 'fa-solar-panel',
        'fa-bolt', 'fa-fish', 'fa-shrimp', 'fa-mountain-sun',
        'fa-tent', 'fa-shop', 'fa-store', 'fa-church', 'fa-mosque',
        'fa-globe-africa', 'fa-map-location-dot', 'fa-location-dot',
        'fa-clipboard-list', 'fa-file-medical', 'fa-book-open',
        'fa-graduation-cap', 'fa-baby', 'fa-heart-pulse',
        'fa-pills', 'fa-syringe', 'fa-apple-whole', 'fa-carrot',
        'fa-bucket', 'fa-faucet-drip', 'fa-toilet', 'fa-shower',
        'fa-house-chimney', 'fa-people-roof', 'fa-cube',
    ];

    // ─── Extended icon set ───────────────────────────────────────────────
    const ALL_ICONS = [
        // People & community
        'fa-user', 'fa-users', 'fa-person', 'fa-children', 'fa-people-group',
        'fa-people-roof', 'fa-person-walking', 'fa-person-cane',
        'fa-baby', 'fa-child', 'fa-user-nurse', 'fa-user-doctor',
        'fa-hand-holding-heart', 'fa-hands-holding-child', 'fa-handshake',
        // Buildings
        'fa-home', 'fa-house', 'fa-house-chimney', 'fa-building',
        'fa-school', 'fa-hospital', 'fa-church', 'fa-mosque',
        'fa-shop', 'fa-store', 'fa-warehouse', 'fa-industry',
        'fa-city', 'fa-landmark',
        // Agriculture
        'fa-tree', 'fa-seedling', 'fa-leaf', 'fa-tractor',
        'fa-wheat-awn', 'fa-apple-whole', 'fa-carrot', 'fa-lemon',
        'fa-pepper-hot', 'fa-cow', 'fa-horse', 'fa-fish', 'fa-shrimp',
        'fa-egg', 'fa-drumstick-bite',
        // Health
        'fa-stethoscope', 'fa-heart-pulse', 'fa-pills', 'fa-syringe',
        'fa-file-medical', 'fa-kit-medical', 'fa-notes-medical',
        'fa-microscope', 'fa-dna', 'fa-virus',
        // Water & sanitation
        'fa-water', 'fa-faucet-drip', 'fa-bucket', 'fa-shower',
        'fa-toilet', 'fa-droplet', 'fa-glass-water',
        // Infrastructure
        'fa-road', 'fa-bridge', 'fa-truck', 'fa-car',
        'fa-solar-panel', 'fa-bolt', 'fa-plug', 'fa-tower-cell',
        'fa-satellite-dish', 'fa-wifi',
        // Environment
        'fa-mountain-sun', 'fa-sun', 'fa-cloud-rain', 'fa-wind',
        'fa-fire', 'fa-globe-africa', 'fa-earth-americas',
        // Education
        'fa-book-open', 'fa-graduation-cap', 'fa-chalkboard-user',
        'fa-pen', 'fa-pencil',
        // Location & mapping
        'fa-map-location-dot', 'fa-location-dot', 'fa-compass',
        'fa-map', 'fa-route',
        // Objects & general
        'fa-clipboard-list', 'fa-file', 'fa-folder', 'fa-chart-bar',
        'fa-chart-line', 'fa-chart-pie', 'fa-calendar', 'fa-clock',
        'fa-bell', 'fa-flag', 'fa-star', 'fa-cube', 'fa-cubes',
        'fa-briefcase', 'fa-toolbox', 'fa-wrench', 'fa-gear',
        'fa-shield', 'fa-key', 'fa-tent', 'fa-campground',
        'fa-circle-info', 'fa-triangle-exclamation',
    ];

    // ─── Render icon grids ──────────────────────────────────────────────
    function renderIconGrid(container, icons) {
        container.empty();
        const currentIcon = $('#id_icon').val() || 'fa-cube';
        icons.forEach(function (icon) {
            const selected = icon === currentIcon ? 'border-primary bg-light' : '';
            const btn = $(
                `<div class="icon-pick-btn d-flex align-items-center justify-content-center m-1 ${selected}"
                      data-icon="${icon}"
                      style="width:44px; height:44px; border-radius:8px; cursor:pointer; border:2px solid #dee2e6;"
                      title="${icon}">
                    <i class="fas ${icon}" style="font-size:1.2rem;"></i>
                </div>`
            );
            container.append(btn);
        });
    }

    renderIconGrid($('#recommended-icons-grid'), RECOMMENDED_ICONS);
    renderIconGrid($('#all-icons-grid'), ALL_ICONS);

    // ─── Icon search ────────────────────────────────────────────────────
    $('#icon-search-input').on('input', function () {
        const q = $(this).val().toLowerCase();
        $('.icon-pick-btn').each(function () {
            const name = $(this).data('icon');
            $(this).toggle(name.includes(q));
        });
    });

    // ─── Icon selection ─────────────────────────────────────────────────
    $(document).on('click', '.icon-pick-btn', function () {
        const icon = $(this).data('icon');
        $('#id_icon').val(icon);
        // Highlight selection
        $('.icon-pick-btn').removeClass('border-primary bg-light').css('border-color', '#dee2e6');
        $(`.icon-pick-btn[data-icon="${icon}"]`).addClass('border-primary bg-light');
        updatePreview();
        $('#iconPickerModal').modal('hide');
    });

    // ─── Color swatch selection ─────────────────────────────────────────
    $('.color-swatch').on('click', function () {
        const token = $(this).data('token');
        $('#id_color').val(token);
        $('.color-swatch').css({ 'border-color': 'transparent', 'box-shadow': 'none' });
        $(this).css({ 'border-color': '#333', 'box-shadow': '0 0 0 2px #fff, 0 0 0 4px #333' });
        updatePreview();
    });

    // Mark initially selected swatch
    const initialColor = $('#id_color').val() || 'slate';
    $(`.color-swatch[data-token="${initialColor}"]`).css({
        'border-color': '#333',
        'box-shadow': '0 0 0 2px #fff, 0 0 0 4px #333'
    });

    // ─── Live preview update ────────────────────────────────────────────
    function updatePreview() {
        const icon = $('#id_icon').val() || 'fa-cube';
        const colorToken = $('#id_color').val() || 'slate';
        const $swatch = $(`.color-swatch[data-token="${colorToken}"]`);
        const tint = $swatch.data('tint') || '#eceff1';
        const solid = $swatch.data('solid') || '#546e7a';
        const name = $('#id_name').val() || 'Object Name';

        // Update icon preview in picker section
        $('#icon-preview-glyph').attr('class', 'fas ' + icon).css('color', solid);
        $('#icon-preview-wrap').css('background-color', tint);

        // Update mobile preview card
        $('#preview-icon-glyph').attr('class', 'fas ' + icon).css('color', solid);
        $('#preview-icon-wrap').css('background-color', tint);
        $('#preview-name').text(name);
    }

    // Update preview when name changes
    $('#id_name').on('input', function () {
        updatePreview();
    });

    // Initial preview
    updatePreview();
});
