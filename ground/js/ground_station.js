var map = null;
function initMap() {
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

    var mapEl = document.getElementById('map')
    map = new google.maps.Map(mapEl, mapOptions);
}

var columnClasses = '';
for (var i = 2; i <= 12; i+= 2) {
    columnClasses += 'col-xs-' + i + ' ';
    columnClasses += 'col-sm-' + i + ' ';
    columnClasses += 'col-md-' + i + ' ';
    columnClasses += 'col-lg-' + i + ' ';
}

function onOrientationChange(event) {
    console.log('new orientation:', event.orientation);
    var els = $('#hab-info, #map, #hab-info-thumbnail, #hab-info-data');
    els.removeClass();
    $('#hab-info-thumbnail,#hab-info-data').addClass('tiny-padding')

    if (event.orientation === 'portrait') {
        $('#hab-info, #map').addClass('col-xs-12');
        $('#hab-info-thumbnail, #hab-info-data').addClass('col-xs-6');
    } else {
        $('#hab-info').addClass('col-xs-4 col-md-3');
        $('#map').addClass('col-xs-8 col-md-9');
        $('#hab-info-thumbnail, #hab-info-data').addClass('col-xs-12');
    }

    $('#map').css('height', $(window).height());
}

function DOMMapper() {
    this.elements = {};
    this.marker = null;
}

function durationMapper(id) {
    return function(duration) {
        var hours = Math.floor(duration / 3600);
        var minutes = Math.floor(duration / 60) - (hours * 60);
        var seconds = duration - (hours * 3600) - (minutes * 60);
        this.element(id).text(
                sprintf('%02d:%02d:%02d', hours, minutes, seconds));
    }
}

var latLongFmt = '%0.6f'
DOMMapper.prototype = {
    formatters: {
        cpu_usage: '%0.1f%%',
        free_mem: '%d MB',
        int_humidity: '%0d%%',
        location_latitude: latLongFmt,
        location_longitude: latLongFmt,
        location_altitude: '%0.1f KM',
        droid_latitude: latLongFmt,
        droid_longitude: latLongFmt
    },


    mappers: {
        root: function(data) {
            var droidConnected = data.droid && data.droid.connected;
            this.togglePanelSuccessError('droid_', droidConnected);
            this.togglePanelSuccessError('location_', !!data.location);
            this.togglePanelSuccessError('system_', !!data.uptime);
            this.markLocation(data);
        },

        uptime: durationMapper('uptime'),

        mode: function(mode) {
            this.element('mode').text(sprintf('%8s', mode.toUpperCase()));
        },

        int_temperature: function(temp) {
            this.element('int_temperature').text(sprintf('%0.1fF', 1.8 * temp + 32));
        },

        ext_temperature: function(temp) {
            this.element('ext_temperature').text(sprintf('%0.1fF', 1.8 * temp + 32));
        },

        location: function(location) {
            this.mapData(location, 'location_');
            this.element('position').text(
                sprintf(latLongFmt, location.latitude) + ', ' +
                sprintf(latLongFmt, location.longitude) + ', ' +
                sprintf('%0.1f KM', location.altitude));
        },

        droid: function(droid) {
            this.mapData(droid, 'droid_');
            if (this.marker) {
            }
        },

        droid_accel_state: function(accel_state) {
            this.element('droid_accel_state').text(sprintf('%8s', accel_state.toUpperCase()));
        },

        droid_accel_duration: durationMapper('droid_accel_duration'),

        photo_status: function(photo_status) {
            function buildProgress(status) {
                var completed = status.chunks - status.missing.length;
                var completedPct = 100 * (completed / status.chunks);

                var column = $('<td>');
                column.append($('<span class="progress-label">')
                        .text(completed + '/' + status.chunks))
                    .append($('<div class="progress progress-striped">')
                            .append($('<div class="progress-bar">')
                                .css('width', completedPct + '%')));

                var chunkProgress = $('<div class="progress">');
                var chunkPct = 100 / status.chunks;
                for (var i = 0; i < status.chunks; i++) {
                    var bar = $('<div/>').addClass('progress-bar');
                    bar.css('width', chunkPct + '%');
                    if (status.missing.indexOf(i) >= 0) {
                        bar.addClass('progress-bar-info');
                    }
                    chunkProgress.append(bar);
                }
                column.append(chunkProgress);
                return column;
            }

            var tbody = this.element('photo_download_tbody');
            tbody.empty();
            $.each(photo_status, function(index, status) {
                var row = $('<tr>');
                row.append($('<td>' + status.index + '</td>'));
                row.append($('<td>' + status.chunks + '</td>'));
                if (status.downloading) {
                    row.append(buildProgress(status));
                } else {
                    row.append($('<td><a href="' + status.url + '">View Photo</a></td>'));
                }
                tbody.append(row);
            });
        }
    },

    togglePanelSuccessError: function(prefix, success) {
        this.element(prefix + 'panel').
            toggleClass('panel-success', success).
            toggleClass('panel-danger', !success);

        if (!success) {
            $('div[id^="' + prefix + '"][class="data"]').text('??');
        }
    },

    togglePanelSuccessInfo: function(prefix, success) {
        this.element(prefix + 'panel').
            toggleClass('panel-success', success).
            toggleClass('panel-info', !success);
    },

    markLocation: function(data) {
        if (!map) {
            return;
        }

        var lat = 0, lng = 0;
        if (data.location) {
            lat = data.location.latitude;
            lng = data.location.longitude;
        }

        if (lat == 0 || lng == 0) {
            if (!data.droid) {
                return;
            }

            lat = data.droid.latitude;
            lng = data.droid.longitude;
        }

        if (lat == 0 || lng == 0) {
            return;
        }

        if (!this.marker) {
            this.marker = new google.maps.Marker({
                title: 'PEPPER-2',
                icon: 'img/hab-icon.png',
                map: map
            });
        }

        var latlng = new google.maps.LatLng(lat, lng);
        map.panTo(latlng);
        this.marker.setPosition(latlng);
    },

    element: function(id) {
        if (!(id in this.elements)) {
            this.elements[id] = $('#' + id);
        }
        return this.elements[id];
    },

    mapData: function(data, prefix) {
        prefix = prefix || '';
        if (prefix == '') {
            this.mappers.root.call(this, data);
        }

        for (var name in data) {
            if (!data.hasOwnProperty(name)) {
                continue;
            }

            var key = prefix + name;
            if (this.formatters[key]) {
                this.element(key).text(sprintf(this.formatters[key], data[name]));
            } else if (this.mappers[key]) {
                this.mappers[key].call(this, data[name]);
            } else {
                this.element(key).text(data[name]);
            }
        }
    },
}

$(document).ready(function($) {
    var script = document.createElement('script');
    script.type = 'text/javascript';
    script.src = 'https://maps.googleapis.com/maps/api/js?v=3.exp&sensor=false&callback=initMap';
    document.body.appendChild(script);

    var mapper = new DOMMapper();
    mapper.mapData({});

    var updateTimer;
    var mockData = new MockData();

    function handleData(data) {
        if (data.mock === true) {
            mockData.nextData();
            data = mockData;
        }

        mapper.mapData(data);
    }

    function updateData() {
        $.getJSON('/api').done(handleData);
    }

    hideAddressbar('#main')

    $(window).on('orientationchange', onOrientationChange);
    $(window).orientationchange();
    updateTimer = setInterval(updateData, 1000);
});
