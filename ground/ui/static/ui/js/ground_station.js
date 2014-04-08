function onOrientationChange(event) {
    var els = $('#hab-info, #hab-info-thumbnail, #hab-info-data');
    els.removeClass();
    $('#hab-info-thumbnail,#hab-info-data').addClass('tiny-padding')

    if (event.orientation === 'portrait') {
        $('#hab-info').addClass('col-xs-12');
        $('#hab-info-thumbnail, #hab-info-data').addClass('col-xs-6');
    } else {
        $('#hab-info').addClass('col-xs-4 col-md-3');
        $('#hab-info-thumbnail, #hab-info-data').addClass('col-xs-12');
    }
}

function DOMMapper() {
    this.elements = {};
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

    accelStates: ['LEVEL', 'RISING', 'FALLING'],

    mappers: {
        root: function(data) {
            var droidConnected = data.droid && data.droid.connected;
            this.togglePanelSuccessError('droid_', droidConnected);
            this.togglePanelSuccessError('location_', !!data.location);
            this.togglePanelSuccessError('system_', !!data.uptime);
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
            this.element('droid_radio').text(sprintf('%d dBm / %d%%', droid.radio_dbm, droid.radio_bars));
        },

        droid_connected: function(connected) {
            this.element('droid_connected').text(connected ? 'YES' : 'NO')

            var droidData = $(".data[id^='droid_']")
                .toggleClass('connected', connected)
                .toggleClass('disconnected', !connected);

            $.each(droidData, function(data) {
                var label = $(data).parent().find('.data-label .label');
                label.toggleClass('label-default', connected)
                     .toggleClass('label-danger', !connected);
            });
        },

        droid_accel_state: function(accel_state) {
            var state = this.accelStates[accel_state];
            this.element('droid_accel_state').text(sprintf('%8s', state));
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

    element: function(id) {
        if (!this.elements[id]) {
            this.elements[id] = $('#' + id);
        }
        return this.elements[id];
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

function getPagedJSON(url, handler) {
    var progress = 0;
    function pageHandler(data) {

        var results = data.results === undefined ? data : data.results;
        var totalCount = data.count === undefined ? 1 : data.count;
        var pageCount = data.results === undefined ? 1 : data.results.length;
        progress += pageCount;

        var handleResult = handler(results, progress, totalCount);

        if (handleResult !== false && data.next !== undefined) {
            $.getJSON(data.next).done(pageHandler);
        }
    }

    $.getJSON(url).done(pageHandler);
}

$(document).ready(function($) {
    $.mobile.linkBindingEnabled = false;
    function csrfSafeMethod(method) {
        // these HTTP methods do not require CSRF protection
        return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
    }

    var csrftoken = $.cookie('csrftoken');
    $.ajaxSetup({
        crossDomain: false, // obviates need for sameOrigin test
        beforeSend: function(xhr, settings) {
            if (!csrfSafeMethod(settings.type)) {
                xhr.setRequestHeader("X-CSRFToken", csrftoken);
            }
        }
    });

    var STATS_INTERVAL = 5000;
    var PHOTO_INTERVAL = 15000;

    var mapper = new DOMMapper();
    mapper.mapData({});

    var statsTimer, photoTimer;
    var mockData = new MockData();

    function handleData(data) {
        if (data.mock === true) {
            mockData.nextData();
            data = mockData;
        }

        mapper.mapData(data);
    }

    function handleLatestPhoto(photo) {
        if (photo.latest) {
            $('#droid_camera').attr('src', photo.latest);
        }

        if (photo.next_progress !== undefined) {
            var isActive = photo.next_progress != 100;
            var smallText = photo.next_progress <= 10;

            $('#photo-progress').toggleClass('active', isActive);
            $('#photo-progress .progress-bar')
                .css('width', photo.next_progress + '%')
                .toggleClass('progress-bar-success', !isActive);

            var progressText = smallText ? photo.next_progress + '%' :
                                           'Next: ' + photo.next_progress + '%';

            $('#photo-progress .progress-label')
                .text(progressText)
                .toggleClass('sr-only', !isActive);
        }
    }

    function updateStats() {
        $.getJSON('/api/stats/').done(handleData);
        statsTimer = setTimeout(updateStats, STATS_INTERVAL);
    }

    function updateLatestPhoto() {
        $.getJSON('/api/photos/latest/').done(handleLatestPhoto);
        photoTimer = setTimeout(updateLatestPhoto, PHOTO_INTERVAL);
    }

    hideAddressbar('#main')

    $(window).on('orientationchange', onOrientationChange);

    setTimeout(function() {
        $(window).orientationchange();
    }, 0);

    updateStats();
    updateLatestPhoto();
});
