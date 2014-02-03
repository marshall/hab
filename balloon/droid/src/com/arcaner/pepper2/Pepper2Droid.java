package com.arcaner.pepper2;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileNotFoundException;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.List;

import org.freehep.util.io.ASCII85OutputStream;

import android.bluetooth.BluetoothSocket;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.location.Criteria;
import android.location.Location;
import android.location.LocationListener;
import android.location.LocationManager;
import android.os.BatteryManager;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.Message;
import android.telephony.CellInfo;
import android.telephony.CellInfoGsm;
import android.telephony.TelephonyManager;
import android.util.Base64;
import android.util.Log;

public class Pepper2Droid implements Runnable, LocationListener, Handler.Callback {
    private static final String TAG = "PEPPER-2";
    private static final int TWO_MINUTES = 1000 * 60 * 2;
    private static final int TELEMETRY_INTERVAL = 5 * 1000;
    private static final int PHOTO_INTERVAL = 1000 * 60 * 5;
    private static final int PHOTO_CHUNK_INTERVAL = 1000;
    private static final int PHOTO_CHUNK_SIZE = 190;

    private static final int MSG_TELEMETRY = 100;
    private static final int MSG_PHOTO_DATA = 101;

    private static final int CMD_START_PHOTO = 200;
    private static final int CMD_STOP_PHOTO = 201;

    private MainActivity mContext;
    private boolean mRunning;
    private BluetoothSocket mSocket;
    private InputStream mIn;
    private OutputStream mOut;
    private Handler mHandler;
    private Location mLocation;
    private Criteria mCriteria = new Criteria();
    private IntentFilter mBatteryFilter = new IntentFilter(
            Intent.ACTION_BATTERY_CHANGED);
    private TelephonyManager mTelephony;
    private int mRadioLevel;
    private String mTelemetry;
    private long mLastTelemetry = 0, mLastPhoto = 0, mLastPhotoData = 0;
    private int mPhotoIndex = 0, mPhotoChunk = 0, mPhotoCount = 0, mChunkCount = 0;
    private boolean mSendingChunks = true;
    private byte mPhotoChunkBuffer[] = new byte[PHOTO_CHUNK_SIZE];

    public Pepper2Droid(MainActivity context) {
        mContext = context;
        mHandler = new Handler(Looper.getMainLooper(), this);
        mContext.setPhotoHandler(mHandler, MSG_PHOTO_DATA);

        mTelephony = (TelephonyManager) context
                .getSystemService(Context.TELEPHONY_SERVICE);

        LocationManager locationManager = (LocationManager) context
                .getSystemService(Context.LOCATION_SERVICE);
        mLocation = locationManager
                .getLastKnownLocation(LocationManager.GPS_PROVIDER);
        mCriteria.setAccuracy(Criteria.NO_REQUIREMENT);
        mCriteria.setAltitudeRequired(true);
        mCriteria.setPowerRequirement(Criteria.POWER_MEDIUM);

        locationManager.requestLocationUpdates(1000, 10, mCriteria, this,
                Looper.getMainLooper());

        Thread thread = new Thread(null, this, "PEPPER-2");
        thread.start();
    }

    public void setBluetoothSocket(BluetoothSocket socket) {
        if (mSocket != null) {
            try {
                mSocket.close();
            } catch (IOException e) {
            }
        }

        mSocket = socket;
        try {
            mIn = mSocket.getInputStream();
            mOut = mSocket.getOutputStream();
        } catch (IOException e) {
            Log.e(TAG, "error getting streams", e);
        }
    }

    public void shutdown() {
        mRunning = false;
        if (mSocket != null) {
            try {
                mSocket.close();
            } catch (IOException e) {
            }
        }

        LocationManager locationManager = (LocationManager) mContext
                .getSystemService(Context.LOCATION_SERVICE);
        locationManager.removeUpdates(this);
        mContext = null;
        mTelephony = null;
    }

    private void updateTelemetry() {
        Intent batteryIntent = mContext.registerReceiver(null, mBatteryFilter);
        int level = batteryIntent.getIntExtra(BatteryManager.EXTRA_LEVEL, -1);
        int scale = batteryIntent.getIntExtra(BatteryManager.EXTRA_SCALE, -1);

        updateRadioLevel();

        StringBuilder builder = new StringBuilder(255);
        String latitude = "0W";
        String longitude = "0N";
        String altitude = "0M";
        if (mLocation != null) {
            latitude = Location.convert(mLocation.getLatitude(),
                    Location.FORMAT_DEGREES);
            longitude = Location.convert(mLocation.getLongitude(),
                    Location.FORMAT_DEGREES);
            altitude = Double.toString(mLocation.getAltitude());
        }

        builder.append(100 * (level / (float) scale)).append(',')
                .append(mRadioLevel).append(',').append(mPhotoCount)
                .append(',').append(mPhotoIndex).append(',')
                .append(mPhotoChunk).append(',').append(latitude).append(',')
                .append(longitude).append(',').append(altitude);

        mTelemetry = builder.toString();
        Log.d(TAG, mTelemetry);

        if (mSocket != null && mSocket.isConnected()) {
            Message msg = Message.obtain(mHandler, MSG_TELEMETRY, mTelemetry);
            msg.sendToTarget();
        }
    }

    private void maybeReadCommand() {
        if (mSocket == null) {
            return;
        }

        try {
            if (mIn.available() < 6) {
                return;
            }

            int length = mIn.read();
            int commandType = mIn.read();
            byte data[] = new byte[length];
            ByteBuffer bb = ByteBuffer.wrap(data);
            mIn.read(data, 0, 4);

            int checksum = bb.getInt();
            bb.rewind();
            mIn.read(data);

            switch (commandType) {
            case CMD_START_PHOTO:
                mSendingChunks = true;
                mPhotoIndex = bb.get();
                break;
            case CMD_STOP_PHOTO:
                mSendingChunks = false;
                break;
            }
        } catch (IOException e) {
            Log.e(TAG, "IO exception", e);
        }
    }

    private void sendPhotoChunk() {
        if (mPhotoCount == 0) {
            return;
        }

        File f = new File(mContext.getExternalFilesDir(null),
                DroidCamera.getRelativeThumbPath(mPhotoIndex));
        if (!f.exists()) {
            Log.e(TAG, "image file doesn't exist: " + f.getAbsolutePath());
            return;
        }

        mChunkCount = (int) f.length() / PHOTO_CHUNK_SIZE;
        if (f.length() % PHOTO_CHUNK_SIZE > 0) {
            mChunkCount++;
        }

        try {
            FileInputStream stream = new FileInputStream(f);
            if (mPhotoChunk > 0) {
                stream.skip(mPhotoChunk * PHOTO_CHUNK_SIZE);
            }

            int bytesRead = stream.read(mPhotoChunkBuffer);
            stream.close();

            if (bytesRead == -1) {
                mPhotoChunk = 0;
                return;
            }

            ByteArrayOutputStream a85Bytes = new ByteArrayOutputStream(255);
            a85Bytes.write(mPhotoIndex);
            a85Bytes.write(mPhotoChunk);
            a85Bytes.write(mChunkCount);
            a85Bytes.write(Base64.encode(mPhotoChunkBuffer, Base64.NO_WRAP));
            //ASCII85OutputStream a85out = new ASCII85OutputStream(a85Bytes);
            //a85out.write(mPhotoChunkBuffer);

            byte chunk[] = a85Bytes.toByteArray();

            int checksum = 0;
            for (int i = 0; i < chunk.length; i++) {
                checksum ^= (chunk[i] & 0xFF);
            }

            ByteBuffer bb = ByteBuffer.allocate(4);
            bb.order(ByteOrder.BIG_ENDIAN);
            mOut.write(chunk.length);
            mOut.write(MSG_PHOTO_DATA);
            mOut.write(bb.putInt(checksum).array());
            mOut.write(chunk);

            if (bytesRead != PHOTO_CHUNK_SIZE) {
                mPhotoChunk = 0;
            } else {
                mPhotoChunk++;
            }
        } catch (FileNotFoundException e) {
            Log.e(TAG, "file not found", e);
        } catch (IOException e) {
            // Log.e(TAG, "io exception", e);
            mSocket = null;
        }
    }

    @Override
    public void run() {
        mRunning = true;
        while (mRunning) {
            boolean isConnected = mSocket != null && mSocket.isConnected();
            if (isConnected) {
                maybeReadCommand();
            }

            if (System.currentTimeMillis() - mLastTelemetry >= TELEMETRY_INTERVAL) {
                updateTelemetry();
                mLastTelemetry = System.currentTimeMillis();
            }

            if (System.currentTimeMillis() - mLastPhoto >= PHOTO_INTERVAL) {
                mContext.takePhoto();
                mLastPhoto = System.currentTimeMillis();
            }

            if (isConnected
                    && mSendingChunks
                    && System.currentTimeMillis() - mLastPhotoData >= PHOTO_CHUNK_INTERVAL) {
                sendPhotoChunk();
                mLastPhotoData = System.currentTimeMillis();
            }

            try {
                Thread.sleep(250L);
            } catch (InterruptedException e) {
                Log.e(TAG, "interrupted", e);
            }
        }
    }

    @Override
    public void onLocationChanged(Location location) {
        if (mLocation == null) {
            mLocation = location;
            return;
        }

        synchronized (mLocation) {
            if (!isBetterLocation(location, mLocation)) {
                return;
            }

            mLocation = location;
        }
    }

    @Override
    public void onProviderDisabled(String provider) {
    }

    @Override
    public void onProviderEnabled(String provider) {
    }

    @Override
    public void onStatusChanged(String provider, int status, Bundle extras) {
    }

    protected void updateRadioLevel() {
        List<CellInfo> infos = mTelephony.getAllCellInfo();
        if (infos == null) {
            return;
        }

        mRadioLevel = -1;
        for (CellInfo info : infos) {
            if (!info.isRegistered()) {
                return;
            }

            if (info instanceof CellInfoGsm) {
                CellInfoGsm gsmInfo = (CellInfoGsm) info;
                mRadioLevel = gsmInfo.getCellSignalStrength().getLevel();
                break;
            }
        }
    }

    protected boolean isBetterLocation(Location location,
            Location currentBestLocation) {
        if (currentBestLocation == null) {
            // A new location is always better than no location
            return true;
        }

        // Check whether the new location fix is newer or older
        long timeDelta = location.getTime() - currentBestLocation.getTime();
        boolean isSignificantlyNewer = timeDelta > TWO_MINUTES;
        boolean isSignificantlyOlder = timeDelta < -TWO_MINUTES;
        boolean isNewer = timeDelta > 0;

        // If it's been more than two minutes since the current location, use
        // the new location
        // because the user has likely moved
        if (isSignificantlyNewer) {
            return true;
            // If the new location is more than two minutes older, it must be
            // worse
        } else if (isSignificantlyOlder) {
            return false;
        }

        // Check whether the new location fix is more or less accurate
        int accuracyDelta = (int) (location.getAccuracy() - currentBestLocation
                .getAccuracy());
        boolean isLessAccurate = accuracyDelta > 0;
        boolean isMoreAccurate = accuracyDelta < 0;
        boolean isSignificantlyLessAccurate = accuracyDelta > 200;

        // Check if the old and new location are from the same provider
        boolean isFromSameProvider = isSameProvider(location.getProvider(),
                currentBestLocation.getProvider());

        // Determine location quality using a combination of timeliness and
        // accuracy
        if (isMoreAccurate) {
            return true;
        } else if (isNewer && !isLessAccurate) {
            return true;
        } else if (isNewer && !isSignificantlyLessAccurate
                && isFromSameProvider) {
            return true;
        }
        return false;
    }

    /** Checks whether two providers are the same */
    private boolean isSameProvider(String provider1, String provider2) {
        if (provider1 == null) {
            return provider2 == null;
        }
        return provider1.equals(provider2);
    }

    private ByteBuffer byteBuffer;

    private void sendTelemetry(String telemetry) throws IOException {
        if (byteBuffer == null) {
            byteBuffer = ByteBuffer.allocate(4);
            byteBuffer.order(ByteOrder.BIG_ENDIAN);
        }

        int checksum = 0;
        int len = telemetry.length();

        for (int i = 0; i < len; i++) {
            checksum ^= (telemetry.charAt(i) & 0xFF);
        }

        byteBuffer.clear();

        mOut.write(len);
        mOut.write(MSG_TELEMETRY);
        mOut.write(byteBuffer.putInt(checksum).array());
        mOut.write(telemetry.getBytes());
    }

    public boolean handleMessage(Message msg) {
        switch (msg.what) {
        case MSG_TELEMETRY:
            try {
                sendTelemetry((String) msg.obj);
            } catch (IOException e) {
                return false;
            }
            return true;
        case MSG_PHOTO_DATA:
            mPhotoCount = msg.getData().getInt(DroidCamera.RESULT_IMAGE_COUNT);
            return true;
        }
        return false;
    }
}
