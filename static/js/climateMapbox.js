function loadGeoJsonMap(
    url, access_token, village_url,
    admin_level_coordinates,
    type, name
) {
    mapboxgl.accessToken = access_token;

    fetch(url)
    .then(response => response.json())
    .then(data => {

        let map_spin = $('.map-spin');
        let regions_spin = $('#regions-nav-link .overlay');
        let regions_angle = $('#regions-nav-link .fa-angle-left');
        let sidebar_back = $('#sidebar_back');
        let load_percentage = $('#load-percentage');
        let map_message = $('#map-message');
        let around_africa_id = 'around_africa';

        function parseListOfLists(input) {
             try {
                // Parse the input string as JSON;
                input = input.replace(/'/g, '"');
                let parsed = JSON.parse(input);

                // Check if parsed is actually an array of arrays
                 if (Array.isArray(parsed)) {
                    return parsed;
                 }else{
                    return [parsed];
                 }
            } catch (error) {
                console.error("Invalid input format:", error.message);
                return null;
            }
        }

        function clearAllTimeout() {
            let id = window.setTimeout(function () {
            }, 0);

            while (id--) {
                window.clearTimeout(id); // will do nothing if no timeout with id is present
            }
        }

        function enableElements() {
            clearAllTimeout();
            if (map_message.html()) {
                setTimeout(function () {
                    map_message.html('').hide();
                    map_spin.hide();
                }, 2000);
            } else {
                map_spin.hide();
                map_message.hide();
            }
            sidebar_back.removeClass('disabled');
            load_percentage.html('');
        }

        function addLayers(geoJson) {
            const colors = ['#FF6633', '#FFB399', '#FF33FF', '#FFFF99', '#00B3E6',
		  '#E6B333', '#3366E6', '#999966', '#99FF99', '#B34D4D',
		  '#80B300', '#809900', '#E6B3B3', '#6680B3', '#66991A',
		  '#FF99E6', '#CCFF1A', '#FF1A66', '#E6331A', '#33FFCC',
		  '#66994D', '#B366CC', '#4D8000', '#B33300', '#CC80CC',
		  '#66664D', '#991AFF', '#E666FF', '#4DB3FF', '#1AB399',
		  '#E666B3', '#33991A', '#CC9999', '#B3B31A', '#00E680',
		  '#4D8066', '#809980', '#E6FF80', '#1AFF33', '#999933',
		  '#FF3380', '#CCCC00', '#66E64D', '#4D80CC', '#9900B3',
		  '#E64D66', '#4DB380', '#FF4D4D', '#99E6E6', '#6666FF'];

            const clusters = new Set(geoJson.features.map(feature => feature.properties.ClusterID));

            mymap.addSource(around_africa_id, {
                'type': 'geojson',
                'data': geoJson
            });
            clusters.forEach((cluster, index) => {
                mymap.addLayer({
                    'id': cluster.toString(),
                    'type': 'fill',
                    'source': around_africa_id,
                    'layout': {},
                    'paint': {
                        'fill-color': colors[index],
                        'fill-opacity': 0.3
                    },
                    'filter': ['==', 'ClusterID', cluster]
                });
                $('#legend').append(`<i class="nav-icon fa fa-square-full" style=color:${colors[index]}></i> <span>Cluster ${cluster}</span> <br>`);
            })

            var sourceLayer = '';
            var shapefileId = '';
            if (type === 'commune') {
                shapefileId = 'leokooshi.16r4x6dm';
                sourceLayer = 'communes_togo-c1mb3n';
            } else if (type === 'canton') {
                shapefileId = 'leokooshi.76xl2wnj';
                sourceLayer = 'canton_togo-207yxg';
            } else if (type === 'prefecture') {
                shapefileId = 'leokooshi.d175fn96';
                sourceLayer = 'prefecture_togo-da9iqd';
            }
            mymap.addLayer({
                  'id': 'shapefile',
                  'type': 'line',
                  'source': {
                      'type': 'vector',
                      'url': `mapbox://${shapefileId}`
                    },
                  'source-layer': sourceLayer,
                  'layout': {
                    'line-join': 'round',
                    'line-cap': 'round'
                  },
                  'paint': {
                    'line-color': '#000000',
                    'line-width': 1
                  }
                });
        }

        function filterFeaturesByProperty(geojsonData, propertyName, propertyValue) {
            return geojsonData.features.filter(
                feature => feature.properties[propertyName] === propertyValue
            );
        }

        // var geoJson = {
        //     "type": "FeatureCollection",
        //     "features": data.features
        // };

        const mymap = new mapboxgl.Map({
            container: 'mapid',
            style: 'mapbox://styles/mapbox/outdoors-v12',
        })

        //  new mapboxgl.Marker()
        // .setLngLat(admin_level_coordinates)
        // .addTo(mymap)

        admin_level_coordinates = parseListOfLists(admin_level_coordinates);
        admin_level_coordinates.forEach( coord => {
            const popup = new mapboxgl.Popup({ offset: 25 }).setText(coord.name);
            let marker = new mapboxgl.Marker()
                .setLngLat(coord.coordinates)
                .addTo(mymap)

            let markerElement = marker.getElement()
            markerElement.addEventListener('click', () => {
                window.open(village_url.replace('0', coord.id.toString()), '_blank')
            });

            markerElement.addEventListener('mouseenter', () => {
                popup.setLngLat(coord.coordinates).addTo(mymap);
            });

            markerElement.addEventListener('mouseleave', () => {
                popup.remove();
            });
        })

        mymap.on('load', () => {

            if (admin_level_coordinates.length > 1) {

                // List of GeoJSON files and unique IDs
                const geojsonSources = [
                    // { id: 'source1', url: '/static/geojson/CANTON MARITIME RGPH 4.json' },
                    { id: 'source2', url: '/static/geojson/COUCHE_CANTON_TOGO.json' }
                ];

                // Loop through each GeoJSON source, add it, and create a corresponding layer
                geojsonSources.forEach(source => {
                    fetch(source.url)
                        .then(response => response.json())
                        .then(data => {
                            // Add each source with its unique ID
                            mymap.addSource(source.id, {
                                type: 'geojson',
                                data: data
                            });

                            // Add a layer for each source
                            mymap.addLayer({
                                id: `${source.id}-layer`,
                                type: 'fill', // Change to 'line' or 'circle' based on data type
                                source: source.id,
                                paint: {
                                    'fill-color': '#ad03fc', // Random color
                                    'fill-opacity': 0.4
                                },
                                filter: ['==', ['get', type.toUpperCase()], name.toUpperCase()]
                            });

                            let filteredFeatures = filterFeaturesByProperty(data, type.toUpperCase(), name.toUpperCase());
                            if (filteredFeatures.length > 0) {
                                // Initialize bounds using the first feature's coordinates
                                const bounds = filteredFeatures.reduce((bounds, feature) => {
                                    // Get coordinates for each feature's polygon
                                    const coordinates = feature.geometry.coordinates[0];
                                    coordinates.forEach(coord => bounds.extend(coord));
                                    return bounds;
                                }, new mapboxgl.LngLatBounds(filteredFeatures[0].geometry.coordinates[0][0], filteredFeatures[0].geometry.coordinates[0][0]));

                                // Center and zoom to fit all filtered features
                                mymap.fitBounds(bounds, {
                                    padding: 20,  // Adds padding around the polygon for better visibility
                                    maxZoom: 15   // Limits maximum zoom level (optional)
                                });
                            }

                        })
                        .catch(error => console.log(`Error loading GeoJSON from ${source.url}:`, error));
                });

            }else{
                mymap.fitBounds([
                    [0.05, 6.1], // Southwest corner
                    [1.8, 11.1]  // Northeast corner
                ], {
                    padding: 20,  // Adds padding around the map view
                    maxZoom: 10   // Limit maximum zoom to prevent over-zooming
                });
            }
        });

        mymap.on('load', () => {
            mymap.dragRotate.disable();

            // addLayers(geoJson);
        });

        regions_angle.hide();
        regions_spin.show();

        mymap.on('load', (e) => {
            setTimeout(function () {
                map_spin.hide();
                map_message.hide();
            }, 1000);
        });

        mymap.on('idle', (e) => {
            setTimeout(function () {
                enableElements();
            }, 1000);
        });

    });
}