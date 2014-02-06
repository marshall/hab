var flightModes = ['preflight', 'ascent', 'descent', 'landed'];
var accelStates = ['level', 'rising', 'falling'];
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

    randLat: function() {
        return this.randFloat(33, 34);
    },

    randLong: function() {
        return this.randFloat(-98, -97);
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
            this.droid.accel_state = accelStates[this.randInt(0, accelStates.length - 1)];
            this.droid.accel_duration = this.randInt(0, 7200);
            this.droid.photo_count = this.randInt(0, 255);
            this.droid.latitude = this.randLat();
            this.droid.longitude = this.randLong();
        }

        var haveLocation = !!this.randInt(0, 1);
        if (haveLocation) {
            this.location = {
                latitude: this.randLat(),
                longitude: this.randLong(),
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
