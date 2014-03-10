var LOCATION_INTERVAL = 30000;

function GroundMap() {
    var self = this;
    $(window).on('orientationchange', function(event) {
        self.setMapOrientation(event.orientation);
    });

    if (!AUTHENTICATED) {
        console.log('Anonymous user - view only');
    }
}

GroundMap.prototype = {
    map: null,
    markers: {},
    markerIndex: 0,
    polylines: {},
    polylineOptions: {
        _default: {
            geodesic: true,
            strokeOpacity: 1.0,
            strokeWeight: 2,
        },
        B: { strokeColor: '#33CC33', zIndex: 100 },
        C: { strokeColor: '#0000FF', zIndex: 1 },
    },
    timer: null,

    initMap: function() {
        console.log('initMap');
        var mapOptions = {
            zoom: 15,
            streetViewControl: false,
            panControl: true,
            panControlOptions: {
                position: google.maps.ControlPosition.TOP_RIGHT
            },
            zoomControl: true,
            zoomControlOptions: {
                style: google.maps.ZoomControlStyle.LARGE,
                position: google.maps.ControlPosition.TOP_RIGHT
            },
            center: new google.maps.LatLng(-34.397, 150.644),
        };

        var mapEl = document.getElementById('map');
        this.map = new google.maps.Map(mapEl, mapOptions);

        this.markers.balloon = new RichMarker({
            map: this.map,
            flat: true,
            content: $('.marker-balloon').clone()[0],
            zIndex: 100,
        });
        this.initLocations();
    },

    setMapOrientation: function(orientation) {
        var map = $('#map');
        map.removeClass();

        if (orientation === 'portrait') {
            map.addClass('col-xs-12');
        } else {
            map.addClass('col-xs-8 col-md-9');
        }

        map.css('height', $(window).height());
    },

    initLocations: function() {
        var self = this;
        getPagedJSON('/api/locations/', function(data, current, total) {
            $.each(data, function(index, location) {
                self.updateLocation(location);
            });

            if (current == total) {
                console.log('start updating!');
                self.updateFinish();
                self.timer = setTimeout(function() {
                    self.updateLocations();
                }, LOCATION_INTERVAL);
            }
        });

        if (AUTHENTICATED && navigator.geolocation) {
            console.log('Watch position');
            navigator.geolocation.getCurrentPosition(function(position) {
                self.postGeo(position);
                navigator.geolocation.watchPosition(function(position) {
                    self.postGeo(position);
                }, function(err) {
                    console.warn(err.code, err.message);
                }, {
                    timeout: 5000,
                    maximumAge: 0
                });
            });
        }
    },

    getLocationName: function(location) {
        if (location.type === 'B') {
            return 'balloon';
        }

        if (location.type === 'C' &&
            location.chaser !== null &&
            location.chaser !== undefined) {
            return location.chaser;
        }

        return undefined;
    },

    getOrInitPolyline: function(location) {
        var name = this.getLocationName(location);
        if (name === undefined) {
            return;
        }

        var polyline = this.polylines[name];
        if (polyline === undefined) {
            var options = $.extend({}, this.polylineOptions._default,
                                       this.polylineOptions[location.type]);

            polyline = this.polylines[name] = new google.maps.Polyline(options);
            polyline.setMap(this.map);
        }
        return polyline;
    },

    getOrInitMarker: function(location) {
        var name = this.getLocationName(location);
        if (name === undefined) {
            return;
        }

        var marker = this.markers[name];
        if (marker === undefined) {
            var div = $('.marker-chaser').clone();
            $(div).find('.marker-title').text(location.chaser.toUpperCase());

            var index = (this.markerIndex % 3) + 1;
            this.markerIndex++;
            $(div).find('img').addClass('marker-car-' + index).attr('src', null);
            marker = this.markers[name] = new RichMarker({
                map: this.map,
                content: div[0],
                flat: true,
                zIndex: 1,
            });
        }
        return marker;
    },

    updateLocation: function(location) {
        if (location.latitude == 0 || location.longitude == 0) {
            return;
        }

        var polyline = this.getOrInitPolyline(location);
        var marker = this.getOrInitMarker(location);

        var position = new google.maps.LatLng(location.latitude, location.longitude);
        if (polyline) {
            polyline.getPath().push(position);
        }

        if (marker) {
            marker.setPosition(position);
        }
    },

    updateFinish: function() {
        var balloonMarker = this.markers.balloon;
        if (balloonMarker) {
            // Follow the balloon
            this.map.panTo(balloonMarker.getPosition());
        }
    },

    updateLocations: function() {
        var self = this;


        console.log('Getting latest');
        $.getJSON('/api/locations/latest').done(function(latest) {
            $.each(latest, function(index, location) {
                self.updateLocation(location);
            });
            self.updateFinish();
        });

        self.timer = setTimeout(function() {
            self.updateLocations();
        }, LOCATION_INTERVAL);
    },

    postGeo: function(position) {
        console.log('POST LOCATION', position.coords);
        $.post('/api/locations/', {
            type: 'C',
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
            altitude: 0
        });
    },
};

function appendScript(src) {
    var script = document.createElement('script');
    script.type = 'text/javascript';
    script.src = src;
    document.body.appendChild(script);
}

var groundMap = null;
function initMap() {
    groundMap.initMap();
}

$(document).ready(function() {
    groundMap = new GroundMap();
    groundMap.initMap();
});
