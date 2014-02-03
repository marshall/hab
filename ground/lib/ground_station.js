var flightModes = ['preflight', 'ascent', 'descent', 'landed'];

function MockData() {
    this.uptime = 0;
    this.downloading = false;
    this.photo_status = [];
}

MockData.prototype = {
    randFloat: function(min, max) {
        return Math.random() * (max - min) + min;
    },

    randInt: function(min, max) {
        return Math.floor(Math.random() * (max - min + 1)) + min;
    },

    nextData: function MockData_nextData() {
        this.uptime++;
        this.cpu_usage = this.randInt(0, 100);
        this.temperature = this.randInt(-40, 100);
        this.humidity = this.randInt(0, 100);
        this.free_mem = this.randInt(0, 512);
        this.mode = flightModes[this.randInt(0, flightModes.length - 1)];

        var droidConnected = !!this.randInt(0, 1);
        this.droid = { connected: droidConnected };
        if (droidConnected) {
            this.droid.battery = this.randInt(0, 100);
            this.droid.radio = this.randInt(0, 100);
            this.droid.photo_count = this.randInt(0, 255);
            this.droid.latitude = this.randFloat(-90, 90);
            this.droid.longitude = this.randFloat(-180, 180);
            this.droid.altitude = this.randFloat(0, 50);
        }

        var haveLocation = !!this.randInt(0, 1);
        if (haveLocation) {
            this.location = {
                latitude: this.randFloat(-90, 90),
                longitude: this.randFloat(-180, 180),
                altitude: this.randFloat(0, 50),
                quality: this.randInt(0, 2),
                timestamp: [ this.randInt(0, 23),
                             this.randInt(0, 59),
                             this.randInt(0, 59) ],
            };
        }

        if (this.photo_download) {
            var missingIdx = this.randInt(0, this.photo_download.missing.length - 1);
            var chunk = this.photo_download.missing[missingIdx];
            this.photo_download.missing.splice(missingIdx, 1);

            if (this.photo_download.missing.length == 0) {
                this.photo_download.downloading = false;
                this.photo_download.url = 'foobar.jpg';
                this.photo_download = null;
            }
        } else {
            this.mockDownload();
        }
    },

    mockDownload: function MockData_mockDownload() {
        var photo_status = {
            index: this.photo_status.length,
            chunks: this.randInt(16, 32),
            downloading: true,
            missing: [],
            url: null
        };
        this.photo_status.push(photo_status);
        this.photo_download = photo_status;

        for (var i = 0; i < photo_status.chunks; i++) {
            photo_status.missing.push(i);
        }
    },
};

var latLongFmt = '%0.6f'
$(document).ready(function($) {
    function DOMMapper() {
        this.elements = {};
    }

    DOMMapper.prototype = {
        formatters: {
            cpu_usage: '%0.1f%%',
            free_mem: '%d MB',
            temperature: '%0.1fF',
            location_latitude: latLongFmt,
            location_longitude: latLongFmt,
            location_altitude: '%0.1f',
            droid_latitude: latLongFmt,
            droid_longitude: latLongFmt,
            droid_altitude: '%0.1f',
        },

        mappers: {
            root: function(data) {
                var droidConnected = data.droid && data.droid.connected;
                this.togglePanelSuccessError('droid_', droidConnected);
                this.togglePanelSuccessError('location_', !!data.location);
                this.togglePanelSuccessError('system_', !!data.uptime);
            },

            uptime: function(uptime) {
                var hours = Math.floor(uptime / 3600);
                var minutes = Math.floor(uptime / 60) - (hours * 60);
                var seconds = uptime - (minutes * 60);
                this.element('uptime').text(
                    sprintf('%02d:%02d:%02d', hours, minutes, seconds));
            },

            mode: function(mode) {
                this.element('mode').text(sprintf('%8s', mode.toUpperCase()));
            },

            location: function(location) {
                this.mapData(location, 'location_');
            },

            droid: function(droid) {
                this.mapData(droid, 'droid_');
            },

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

    var mapper = new DOMMapper();
    mapper.mapData({});

    function handleData(data) {
        mapper.mapData(data);
    }

    function updateData() {
        $.getJSON('/api').done(handleData);
    }

    var mockData = new MockData();
    function updateMockData() {
        mockData.nextData();
        handleData(mockData);
    }

    setInterval(updateMockData, 1000);
});
