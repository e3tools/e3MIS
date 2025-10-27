$(document).ready(function () {
    const spinner = $("#btn-spinner");
    const setStatus = (msg, cls = "muted") => {
        console.log(`status ${cls}`);
        console.log(msg);
        spinner.addClass('d-none');
    };

    const coordsEl = $(".coordinates");

    // Main handler for a successful geolocation read
    async function handlePosition(position) {
        const {latitude, longitude, accuracy} = position.coords;
        coordsEl.val(`${latitude.toFixed(6)} ${longitude.toFixed(6)} ${accuracy.toFixed(2)}`);

        $(".lat-label").text(latitude.toFixed(6));
        $(".lon-label").text(longitude.toFixed(6));
        $(".acc-label").text(accuracy.toFixed(2));
        $("#geolocation-display").removeClass('d-none');
        spinner.addClass('d-none');

        // Optional: reverse geocode to a human-readable address.
        // This uses OSM Nominatim. Be nice: low frequency, cache, and follow their usage policy.
        try {
            const address = await reverseGeocode(latitude, longitude);
            if (address) {
                $(".address-label").html(address);
                $("#geocode-address-display").removeClass('d-none');
            }
        } catch (e) {
            // Don’t make a scene if reverse geocoding fails.
        }
    }

    async function fillPositionLabels(latitude, longitude, accuracy) {
        $(".lat-label").text(latitude);
        $(".lon-label").text(longitude);
        $(".acc-label").text(accuracy);
        $("#geolocation-display").removeClass('d-none');

        // Optional: reverse geocode to a human-readable address.
        // This uses OSM Nominatim. Be nice: low frequency, cache, and follow their usage policy.
        try {
            const address = await reverseGeocode(latitude, longitude);
            if (address) {
                $(".address-label").html(address);
                $("#geocode-address-display").removeClass('d-none');
            }
        } catch (e) {
            // Don’t make a scene if reverse geocoding fails.
        }
    }

    // Errors that the Geolocation API likes to throw when it’s feeling dramatic
    function handlePositionError(err) {
        const map = {
            1: "Permission denied. The browser said no.",
            2: "Position unavailable. Sensors or network couldn’t help.",
            3: "Timeout. It took too long to get a fix."
        };
        setStatus(map[err.code] || `Geolocation error: ${err.message}`, "error");
    }

    // Ask for one-time position
    async function getOnce() {
        // HTTPS or localhost required, and a user gesture helps, especially on iOS.
        if (!('geolocation' in navigator)) {
            setStatus("Geolocation not supported by this browser. Fun.", "error");
            return;
        }

        // Try Permissions API for nicer UX (not supported everywhere; we’ll fail gracefully)
        spinner.removeClass("d-none");
        try {
            if ('permissions' in navigator && navigator.permissions.query) {
                const perm = await navigator.permissions.query({name: 'geolocation'});
                if (perm.state === 'denied') {
                    setStatus("Geolocation is blocked. Enable it in site permissions.", "error");
                    return;
                }
            }
        } catch (_) {
        }

        setStatus("Requesting your location… this might take a few seconds.");

        navigator.geolocation.getCurrentPosition(
            handlePosition,
            handlePositionError,
            {
                enableHighAccuracy: true,   // better GPS when available
                timeout: 10000,             // bail out after 10s
                maximumAge: 30000           // use a recent cached fix if available
            }
        );
    }

    // Tiny reverse-geocoder using OSM Nominatim.
    // For production, add caching, rate limiting, and a proper User-Agent/Referer.
    async function reverseGeocode(lat, lon) {
        const url = new URL("https://nominatim.openstreetmap.org/reverse");
        url.searchParams.set("lat", lat);
        url.searchParams.set("lon", lon);
        url.searchParams.set("format", "jsonv2");

        const resp = await fetch(url.toString(), {
            headers: {
                // Nominatim requires a valid UA/Referer indicating your app
                "Accept": "application/json"
            }
        });
        if (!resp.ok) return null;
        const data = await resp.json();
        return data.display_name || null;
    }

    // Wire up buttons
    $(".btn-use-location").on("click", getOnce);
    if (coordsEl.val()) {
        const loc_values = $(coordsEl).val().split(" ");
        fillPositionLabels(loc_values[0], loc_values[1], loc_values[2]);
    }
})