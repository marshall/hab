package com.arcaner.pepper2;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileNotFoundException;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;

import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.hardware.Sensor;
import android.hardware.SensorEvent;
import android.hardware.SensorEventListener;
import android.hardware.SensorManager;
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
import android.telephony.SmsManager;
import android.telephony.TelephonyManager;
import android.util.Log;

import com.arcaner.pepper2.proto.DroidTelemetry;
import com.arcaner.pepper2.proto.PhotoData;
import com.arcaner.pepper2.proto.ProtoMessage;

public class Pepper2Droid extends Thread implements LocationListener, SensorEventListener {
    public static enum AccelState {
        LEVEL, RISING, FALLING
    };

    private static final String TAG = "PEPPER2-DROID";
    private static final boolean DBG = false;

    private static final int TWO_MINUTES = 1000 * 60 * 2;
    private static final int TELEMETRY_INTERVAL = 5 * 1000;
    private static final int PHOTO_INTERVAL = 1000 * 30;
    private static final int PHOTO_CHUNK_INTERVAL = 1000;
    private static final int PHOTO_CHUNK_SIZE = ProtoMessage.MAX_DATA_LEN;
    private static final int MAX_PHOTOS = 255;
    private static final int SMS_ALERT_INTERVAL = 1000 * 15; // TODO make this like 10 minutes
    private static final int MIN_ACCEL_STABILITY = 1000 * 10;
    private static final int ACCEL_SAMPLE_SIZE = 20;
    private static final float ACCEL_RISING  =  1.1f;
    private static final float ACCEL_FALLING = -1.1f;

    private static final String SMS_SENT = "SMS_SENT";
    private static final String SMS_DELIVERED = "SMS_DELIVERED";
    private static final int MAX_SMS_MSG_LEN = 160;
    private static final int SMS_MSG_COUNT = 2;
    private static final String GMAPS_URL = "http://maps.google.com/maps?q=";
    private static final String SMS_PHONE_NUMBER = "+12145006076";

    private static final int MSG_UPDATE_TELEMETRY   = 100;
    private static final int MSG_TAKE_PHOTO         = 101;
    private static final int MSG_SEND_PHOTO_CHUNK   = 102;
    private static final int MSG_HANDLE_PHOTO       = 103;
    private static final int MSG_START_PHOTO_DATA   = 104;
    private static final int MSG_STOP_PHOTO_DATA    = 105;
    private static final int MSG_SEND_TEXT          = 106;
    private static final int MSG_SEND_TEXT_ALERT    = 107;
    private static final int MSG_ADD_PHONE_NUMBER   = 108;

    private MainActivity mContext;
    private BluetoothServer mBtServer;
    private Handler mHandler;
    private Location mLocation;
    private Criteria mCriteria = new Criteria();
    private int mAccelSamples = 0;
    private float[] mGravity = new float[3], mLinearAccel = new float[3], mAvgLinearAccel = new float[3];
    private AccelState mAccelState = AccelState.LEVEL;
    private long mAccelStateBegin = 0;
    private IntentFilter mBatteryFilter = new IntentFilter(Intent.ACTION_BATTERY_CHANGED);
    private TelephonyManager mTelephony;
    private int mRadioLevel;
    private DroidTelemetry mTelemetry = new DroidTelemetry();
    private PhotoData mPhotoData = new PhotoData();
    private int mPhotoCount = 0;
    private boolean mSendingChunks = false;
    private File mPhotoFile;
    private StringBuilder[] mSmsMessages = new StringBuilder[SMS_MSG_COUNT];
    private ArrayList<String> mPhoneNumbers = new ArrayList<String>();

    public Pepper2Droid(MainActivity context, BluetoothServer btServer) {
        super((ThreadGroup) null, TAG);
        mContext = context;
        mBtServer = btServer;

        for (int i = 0; i < SMS_MSG_COUNT; i++) {
            mSmsMessages[i] = new StringBuilder(MAX_SMS_MSG_LEN);
        }
        mAccelStateBegin = System.currentTimeMillis();

        mPhoneNumbers.add(SMS_PHONE_NUMBER);

        mTelephony = (TelephonyManager) context
                .getSystemService(Context.TELEPHONY_SERVICE);

        LocationManager locationManager = (LocationManager) context
                .getSystemService(Context.LOCATION_SERVICE);
        mLocation = locationManager
                .getLastKnownLocation(LocationManager.GPS_PROVIDER);
        mCriteria.setAccuracy(Criteria.ACCURACY_FINE);
    }

    public void shutdown() {
        mHandler.getLooper().quit();

        LocationManager locationManager = (LocationManager) mContext.getSystemService(Context.LOCATION_SERVICE);
        locationManager.removeUpdates(this);
        SensorManager sensorManager = (SensorManager) mContext.getSystemService(Context.SENSOR_SERVICE);
        sensorManager.unregisterListener(this);
        mContext = null;
        mTelephony = null;
    }

    public void startPhotoData(int index) {
        Message msg = mHandler.obtainMessage(MSG_START_PHOTO_DATA, index, 0);
        msg.sendToTarget();
    }

    public void stopPhotoData() {
        mHandler.sendEmptyMessage(MSG_STOP_PHOTO_DATA);
    }

    public void sendText() {
        mHandler.sendEmptyMessage(MSG_SEND_TEXT);
    }

    public void addPhoneNumber(String phoneNumber) {
        Message msg = mHandler.obtainMessage(MSG_ADD_PHONE_NUMBER, phoneNumber);
        msg.sendToTarget();
    }

    private void updateTelemetry() {
        Intent batteryIntent = mContext.registerReceiver(null, mBatteryFilter);
        int level = batteryIntent.getIntExtra(BatteryManager.EXTRA_LEVEL, -1);
        int scale = batteryIntent.getIntExtra(BatteryManager.EXTRA_SCALE, -1);
        updateRadioLevel();

        mTelemetry.battery = (short) Math.floor(100 * (level / (float) scale));
        mTelemetry.radio = (short) mRadioLevel;
        mTelemetry.photoCount = mPhotoCount;
        mTelemetry.latitude = mLocation == null ? 0 : mLocation.getLatitude();
        mTelemetry.longitude = mLocation == null ? 0 : mLocation.getLongitude();
        mTelemetry.accelState = (short) mAccelState.ordinal();
        mTelemetry.accelDuration = (int) ((System.currentTimeMillis() - mAccelStateBegin) / 1000);

        for (int i = 0; i < mSmsMessages.length; i++) {
            mSmsMessages[i].delete(0, mSmsMessages[i].length());
        }

        mSmsMessages[0].append("BATT: ")
                       .append(mTelemetry.battery)
                       .append("\nRADIO: ")
                       .append(mTelemetry.radio)
                       .append("\nPHOTOS: ")
                       .append(mTelemetry.photoCount)
                       .append("\n")
                       .append(mAccelState.toString())
                       .append(" for ")
                       .append(mTelemetry.accelDuration)
                       .append(" sec");

        mSmsMessages[1].append("LOCATION\n")
                       .append(GMAPS_URL)
                       .append(mTelemetry.latitude)
                       .append(',')
                       .append(mTelemetry.longitude);

        mBtServer.writeMessage(mTelemetry);
    }

    private void sendPhotoChunk() {
        if (mPhotoCount == 0) {
            return;
        }

        if (mPhotoFile == null) {
            mPhotoFile = new File(mContext.getExternalFilesDir(null),
                                  DroidCamera.getRelativeThumbPath(mPhotoData.index));
            if (!mPhotoFile.exists()) {
                Log.e(TAG, "image file doesn't exist: " + mPhotoFile.getAbsolutePath());
                mPhotoFile = null;
                return;
            }

            mPhotoData.fileSize = mPhotoFile.length();
            mPhotoData.chunk = 0;
            mPhotoData.chunkCount = (int) mPhotoFile.length() / PHOTO_CHUNK_SIZE;
            if (mPhotoFile.length() % PHOTO_CHUNK_SIZE > 0) {
                mPhotoData.chunkCount++;
            }
        }

        try {
            FileInputStream stream = new FileInputStream(mPhotoFile);
            if (mPhotoData.chunk > 0) {
                stream.skip(mPhotoData.chunk * PHOTO_CHUNK_SIZE);
            }

            int bytesRead = stream.read(mPhotoData.chunkData, 0, ProtoMessage.MAX_DATA_LEN);
            stream.close();

            if (bytesRead == -1) {
                mPhotoData.chunk = 0;
                mPhotoFile = null;
                return;
            }

            mPhotoData.chunkDataLen = bytesRead;
            mBtServer.writeMessage(mPhotoData);

            if (bytesRead != PHOTO_CHUNK_SIZE) {
                mPhotoData.chunk = 0;
            } else {
                mPhotoData.chunk++;
            }
        } catch (FileNotFoundException e) {
            Log.e(TAG, "file not found", e);
        } catch (IOException e) {
            // Log.e(TAG, "io exception", e);
        }
    }

    private void sendTextMessage(boolean checkLevel) {
        if (checkLevel) {
            if (mAccelState != AccelState.LEVEL) {
                return;
            }

            long accelDuration = System.currentTimeMillis() - mAccelStateBegin;
            if (accelDuration < MIN_ACCEL_STABILITY) {
                return;
            }
        }

        SmsManager smsManager = SmsManager.getDefault();

        for (StringBuilder b : mSmsMessages) {

            String msg = b.toString();
            if (DBG) {
                Log.d(TAG, "SMS: " + msg.replaceAll("\n", "//"));
            }

            ArrayList<String> msgList = null;
            if (msg.length() > MAX_SMS_MSG_LEN) {
                msgList = smsManager.divideMessage(msg);
            }
    
            for (String phoneNumber : mPhoneNumbers) {
                PendingIntent piSent = PendingIntent.getBroadcast(mContext, 0, new Intent(SMS_SENT), 0);
                PendingIntent piDelivered = PendingIntent.getBroadcast(mContext, 0, new Intent(SMS_DELIVERED), 0);
                
                if (msgList != null) {
                    smsManager.sendMultipartTextMessage(phoneNumber, null, msgList, null, null);
                } else {
                    smsManager.sendTextMessage(phoneNumber, null, msg, piSent, piDelivered);
                }
            }
        }
    }

    @Override
    public void run() {
        Looper.prepare();
        mHandler = new MsgHandler();
        mHandler.sendEmptyMessageDelayed(MSG_UPDATE_TELEMETRY, TELEMETRY_INTERVAL);
        mHandler.sendEmptyMessageDelayed(MSG_TAKE_PHOTO, PHOTO_INTERVAL);
        mHandler.sendEmptyMessageDelayed(MSG_SEND_TEXT_ALERT, SMS_ALERT_INTERVAL);
        mContext.setPhotoHandler(mHandler, MSG_HANDLE_PHOTO);

        LocationManager locationManager = (LocationManager) mContext.getSystemService(Context.LOCATION_SERVICE);
        locationManager.requestLocationUpdates(1000, 10, mCriteria, this, Looper.myLooper()); 

        SensorManager sensorManager = (SensorManager) mContext.getSystemService(Context.SENSOR_SERVICE);
        Sensor sensor = sensorManager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER);
        sensorManager.registerListener(this, sensor, SensorManager.SENSOR_DELAY_NORMAL);

        Looper.loop();
    }

    private class MsgHandler extends Handler {
        public void handleMessage(Message msg) {
            switch (msg.what) {
            case MSG_UPDATE_TELEMETRY:
                updateTelemetry();
                sendEmptyMessageDelayed(MSG_UPDATE_TELEMETRY, TELEMETRY_INTERVAL);
                break;
            case MSG_TAKE_PHOTO:
                mContext.takePhoto();
                break;
            case MSG_SEND_PHOTO_CHUNK:
                if (mSendingChunks) {
                    sendPhotoChunk();
                    sendEmptyMessageDelayed(MSG_SEND_PHOTO_CHUNK, PHOTO_CHUNK_INTERVAL);
                }
                break;
            case MSG_HANDLE_PHOTO:
                mPhotoCount = msg.getData().getInt(DroidCamera.RESULT_IMAGE_COUNT);
                if (mPhotoCount < MAX_PHOTOS) {
                    mHandler.sendEmptyMessageDelayed(MSG_TAKE_PHOTO, PHOTO_INTERVAL);
                }

                if (!mSendingChunks) {
                    startPhotoData(0);
                }
                break;
            case MSG_START_PHOTO_DATA:
                mPhotoData.index = msg.arg1;
                if (!mSendingChunks) {
                    mSendingChunks = true;
                    sendEmptyMessageDelayed(MSG_SEND_PHOTO_CHUNK, PHOTO_CHUNK_INTERVAL);
                }
                break;
            case MSG_STOP_PHOTO_DATA:
                mSendingChunks = false;
                break;
            case MSG_SEND_TEXT:
                sendTextMessage(false);
                break;
            case MSG_SEND_TEXT_ALERT:
                sendTextMessage(true);
                sendEmptyMessageDelayed(MSG_SEND_TEXT_ALERT, SMS_ALERT_INTERVAL);
                break;
            case MSG_ADD_PHONE_NUMBER:
                mPhoneNumbers.add((String) msg.obj);
                break;
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

    @Override
    public void onAccuracyChanged(Sensor sensor, int accuracy) { }

    @Override
    public void onSensorChanged(SensorEvent event) {
        if (event.sensor.getType() != Sensor.TYPE_ACCELEROMETER) {
            return;
        }

        final float alpha = 0.8f;

        mGravity[0] = alpha * mGravity[0] + (1 - alpha) * event.values[0];
        mGravity[1] = alpha * mGravity[1] + (1 - alpha) * event.values[1];
        mGravity[2] = alpha * mGravity[2] + (1 - alpha) * event.values[2];

        mLinearAccel[0] = event.values[0] - mGravity[0];
        mLinearAccel[1] = event.values[1] - mGravity[1];
        mLinearAccel[2] = event.values[2] - mGravity[2];

        if (mAccelSamples == 0) {
            mAvgLinearAccel[0] = mLinearAccel[0];
            mAvgLinearAccel[1] = mLinearAccel[1];
            mAvgLinearAccel[2] = mLinearAccel[2];
        } else {
            mAvgLinearAccel[0] = (mAvgLinearAccel[0] + mLinearAccel[0]) / 2.0f;
            mAvgLinearAccel[1] = (mAvgLinearAccel[1] + mLinearAccel[1]) / 2.0f;
            mAvgLinearAccel[2] = (mAvgLinearAccel[2] + mLinearAccel[2]) / 2.0f;
        }

        mAccelSamples++;
        if (mAccelSamples == ACCEL_SAMPLE_SIZE) {
            AccelState newState;
            if (mAvgLinearAccel[1] <= ACCEL_FALLING) {
                newState = AccelState.FALLING;
            } else if (mAvgLinearAccel[1] >= ACCEL_RISING) {
                newState = AccelState.RISING;
            } else {
                newState = AccelState.LEVEL;
            }

            if (newState != mAccelState) {
                mAccelStateBegin = System.currentTimeMillis();
                mAccelState = newState;
            }

            if (DBG) {
                Log.d(TAG, String.format("accel = %s for %d seconds", mAccelState, ((System.currentTimeMillis() - mAccelStateBegin) / 1000)));
            }
            mAccelSamples = 0;
        }
    }
}
