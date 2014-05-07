package com.arcaner.pepper2;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileNotFoundException;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Arrays;
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
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;
import android.os.Message;
import android.os.StatFs;
import android.telephony.PhoneStateListener;
import android.telephony.SignalStrength;
import android.telephony.SmsManager;
import android.telephony.TelephonyManager;
import android.text.format.Formatter;
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
    private static final boolean SEND_TXT_MESSAGES = true;

    private static final int TWO_MINUTES = 1000 * 60 * 2;
    private static final int TELEMETRY_INTERVAL = 5 * 1000;
    private static final int PHOTO_INTERVAL = 1000 * 30;
    private static final int PHOTO_CHUNK_INTERVAL = 1000;
    private static final int PHOTO_SKIP = (TWO_MINUTES * 2) / PHOTO_INTERVAL; // only stream one photo every 4 minutes
    private static final int PHOTO_CHUNK_SIZE = ProtoMessage.MAX_DATA_LEN;
    private static final int MAX_PHOTOS = 768;
    
    private static final int SMS_ALERT_INTERVAL = 1000 * 60 * 10;
    private static final int MIN_ACCEL_STABILITY = 1000 * 10;
    private static final int ACCEL_SAMPLE_SIZE = 20;
    private static final float ACCEL_RISING  =  1.1f;
    private static final float ACCEL_FALLING = -1.1f;

    private static final String SMS_SENT = "SMS_SENT";
    private static final String SMS_DELIVERED = "SMS_DELIVERED";
    private static final int MAX_SMS_MSG_LEN = 160;
    private static final int SMS_MSG_COUNT = 2;
    private static final String GMAPS_URL = "http://maps.google.com/maps?q=";
    private static final String[] SMS_PHONE_NUMBERS = new String[] { "+12145006076", "+12145008098" };

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
    private int mRadioDbm, mRadioBars;
    private DroidTelemetry mTelemetry = new DroidTelemetry();
    private PhotoData mPhotoData = new PhotoData();
    private int mPhotoCount = 0;
    private long mPhotoDataStart = 0;
    private long mTotalPhotoSize = 0, mTotalThumbSize = 0;
    private boolean mSendingChunks = false;
    private File mPhotoFile;
    private StringBuilder[] mSmsMessages = new StringBuilder[SMS_MSG_COUNT];
    private ArrayList<String> mPhoneNumbers = new ArrayList<String>();
    private IntentFilter mSmsFilter;
    private SmsReceiver mSmsReceiver;
    private DataLogger mDataLogger;

    public Pepper2Droid(MainActivity context, BluetoothServer btServer) {
        super((ThreadGroup) null, TAG);
        mContext = context;
        mBtServer = btServer;

        for (int i = 0; i < SMS_MSG_COUNT; i++) {
            mSmsMessages[i] = new StringBuilder(MAX_SMS_MSG_LEN);
        }
        mAccelStateBegin = System.currentTimeMillis();

        for (String phoneNumber : SMS_PHONE_NUMBERS) {
            mPhoneNumbers.add(phoneNumber);
        }

        mTelephony = (TelephonyManager) context
                .getSystemService(Context.TELEPHONY_SERVICE);
        mTelephony.listen(new PhoneStateListener() {
            @Override
            public void onSignalStrengthsChanged(SignalStrength signalStrength) {
                updateRadio(signalStrength);
            }
        }, PhoneStateListener.LISTEN_SIGNAL_STRENGTHS);

        LocationManager locationManager = (LocationManager) context
                .getSystemService(Context.LOCATION_SERVICE);
        mLocation = locationManager
                .getLastKnownLocation(LocationManager.GPS_PROVIDER);
        mCriteria.setAccuracy(Criteria.ACCURACY_FINE);

        mSmsReceiver = new SmsReceiver(this);
        mSmsFilter = new IntentFilter();
        mSmsFilter.addAction("android.provider.Telephony.SMS_RECEIVED");
        mContext.registerReceiver(mSmsReceiver, mSmsFilter);
    }

    public void shutdown() {
        mHandler.getLooper().quit();

        LocationManager locationManager = (LocationManager) mContext.getSystemService(Context.LOCATION_SERVICE);
        locationManager.removeUpdates(this);
        SensorManager sensorManager = (SensorManager) mContext.getSystemService(Context.SENSOR_SERVICE);
        sensorManager.unregisterListener(this);
        mContext.unregisterReceiver(mSmsReceiver);
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

    private void updateRadio(SignalStrength signalStrength) {
        if (signalStrength.isGsm()) {
            int asu = signalStrength.getGsmSignalStrength();
            mRadioDbm = -1;
            if (asu != 99) {
                mRadioDbm = -113 + 2 * asu;
            }

            if (asu <= 2 || asu == 99) mRadioBars = 0;
            else if (asu >= 12) mRadioBars = 100;
            else {
                mRadioBars = (int) Math.round(100 * (((double) asu - 2) / 12.0));
            }
        } else {
            mRadioDbm = signalStrength.getCdmaDbm();
            int ecio = signalStrength.getCdmaEcio();
            int levelDbm, levelEcio;

            if (mRadioDbm >= -75) levelDbm = 100;
            else if (mRadioDbm < -100) levelDbm = 0;
            else {
                levelDbm = (int) Math.round(100 * (((double) mRadioDbm + 100.0) / 25.0));
            }

            // Ec/Io are in dB*10
            if (ecio >= -90) levelEcio = 100;
            else if (ecio < -150) levelEcio = 0;
            else {
                levelEcio = (int) Math.round(100 * (((double) ecio + 150.0) / 60.0));
            }
            mRadioBars = (levelDbm < levelEcio) ? levelDbm : levelEcio;
        }
    }

    private void updateTelemetry() {
        Intent batteryIntent = mContext.registerReceiver(null, mBatteryFilter);
        int level = batteryIntent.getIntExtra(BatteryManager.EXTRA_LEVEL, -1);
        int scale = batteryIntent.getIntExtra(BatteryManager.EXTRA_SCALE, -1);

        mTelemetry.battery = (short) Math.floor(100 * (level / (float) scale));
        mTelemetry.radioDbm = (short) mRadioDbm;
        mTelemetry.radioBars = (short) mRadioBars;
        mTelemetry.photoCount = mPhotoCount;
        mTelemetry.latitude = mLocation == null ? 0 : mLocation.getLatitude();
        mTelemetry.longitude = mLocation == null ? 0 : mLocation.getLongitude();
        mTelemetry.accelState = (short) mAccelState.ordinal();
        mTelemetry.accelDuration = (int) ((System.currentTimeMillis() - mAccelStateBegin) / 1000);

        File path = Environment.getExternalStorageDirectory();
        StatFs stat = new StatFs(path.getPath());
        long blockSize = stat.getBlockSize();
        long availableBlocks = stat.getAvailableBlocks();
        String diskAvailable = Formatter.formatFileSize(mContext, availableBlocks * blockSize);

        for (int i = 0; i < mSmsMessages.length; i++) {
            mSmsMessages[i].delete(0, mSmsMessages[i].length());
        }

        String totalPhotoSizeMb = String.format("%.2f MB", ((double) mTotalPhotoSize) / 1024.0 / 1024.0);
        mSmsMessages[0].append("BATT: ")
                       .append(mTelemetry.battery)
                       .append("%\nRADIO: ")
                       .append(mTelemetry.radioDbm)
                       .append(" dBm / ")
                       .append(mRadioBars)
                       .append("%")
                       .append("\nPHOTOS: ")
                       .append(mTelemetry.photoCount)
                       .append(" / ")
                       .append(totalPhotoSizeMb)
                       .append("\n")
                       .append(mAccelState.toString())
                       .append(" for ")
                       .append(mTelemetry.accelDuration)
                       .append(" sec")
                       .append("\n")
                       .append("DISK FREE: ")
                       .append(diskAvailable);

        mSmsMessages[1].append("LOCATION\n")
                       .append(GMAPS_URL)
                       .append(mTelemetry.latitude)
                       .append(',')
                       .append(mTelemetry.longitude);

        mBtServer.writeMessage(mTelemetry);
        mDataLogger.log(mTelemetry);
        mContext.updateUI(mPhotoCount, mBtServer.isConnected(), mTelemetry.battery, mRadioBars, diskAvailable);
    }

    private void onPhotoTaken(int photoCount, String photoPath, String thumbPath) {
        //mPhotoCount = msg.getData().getInt(DroidCamera.RESULT_IMAGE_COUNT);
        mPhotoCount = photoCount;

        File photoFile = new File(photoPath);
        mTotalPhotoSize += photoFile.length();

        File thumbFile = new File(thumbPath);
        mTotalThumbSize += thumbFile.length();

        takeNextPhoto();

        if (!mSendingChunks) {
            startPhotoData(0);
        }
    }

    private void takeNextPhoto() {
        if (mPhotoCount < MAX_PHOTOS) {
            mHandler.sendEmptyMessageDelayed(MSG_TAKE_PHOTO, PHOTO_INTERVAL);
        }
    }

    private void sendPhotoChunk() {
        if (mPhotoCount == 0) {
            return;
        }

        if (System.currentTimeMillis() - mPhotoDataStart >= PHOTO_INTERVAL * PHOTO_SKIP) {
            mPhotoData.index = Math.min(mPhotoCount, mPhotoData.index + PHOTO_SKIP);
            mPhotoFile = null;
            mPhotoDataStart = System.currentTimeMillis();
            mDataLogger.log("Skipping ahead to photo " + mPhotoData.index);
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

    private String handlePhotoCommand(String args[]) {
        if (args.length == 1 || args[1].equalsIgnoreCase("HELP")) {
            return "PHOTO commands: START <index>, STOP";
        }

        String command = args[1];
        if (command.equalsIgnoreCase("START")) {
            if (args.length == 2) {
                return "ERR: PHOTO START requires an index";
            }

            int index = Integer.parseInt(args[2]);
            if (index >= mPhotoCount) {
                return "ERR: Only " + mPhotoCount + " photos";
            }

            startPhotoData(index);
            return "START SENDING PHOTO " + index;
        } else if (command.equalsIgnoreCase("STOP")) {
            stopPhotoData();
            return "STOP SENDING PHOTO";
        }

        return "Unknown PHOTO command: " + command;
    }

    public void onTextReceived(String msgBody, String srcAddr) {
        mDataLogger.log(String.format("SMS RCVD FROM %s: %s", srcAddr, msgBody));

        SmsManager smsManager = SmsManager.getDefault();
        try {
            String tokens[] = msgBody.split(" ");
            if (tokens.length == 0 || tokens[0].equalsIgnoreCase("HELP")) {
                sendSingleTextMessage(smsManager, srcAddr, "Commands: PHOTO, STATS");
                return;
            }

            String command = tokens[0];
            if (command.equalsIgnoreCase("PHOTO")) {
                sendSingleTextMessage(smsManager, srcAddr, handlePhotoCommand(tokens));
            } else if (command.equalsIgnoreCase("STATS")) {
                sendStatsTextMessage(smsManager, false, Arrays.asList(srcAddr));
            } else {
                sendSingleTextMessage(smsManager, srcAddr, "Unknown command: " + command);
            }
        } catch (Exception e) {
            sendSingleTextMessage(smsManager, srcAddr, "Error processing: " + e.getMessage());
        }
    }

    private void sendStatsTextMessage(SmsManager smsManager, boolean checkLevel, List<String> phoneNumbers) {
        if (checkLevel) {
            if (mAccelState != AccelState.LEVEL) {
                return;
            }

            long accelDuration = System.currentTimeMillis() - mAccelStateBegin;
            if (accelDuration < MIN_ACCEL_STABILITY) {
                return;
            }
        }

        for (StringBuilder b : mSmsMessages) {

            String msg = b.toString();
            ArrayList<String> msgList = null;
            if (msg.length() > MAX_SMS_MSG_LEN) {
                msgList = smsManager.divideMessage(msg);
            }
    
            for (String phoneNumber : phoneNumbers) {
                if (msgList != null) {
                    sendMultipartTextMessage(smsManager, phoneNumber, msgList);
                } else {
                    sendSingleTextMessage(smsManager, phoneNumber, msg);
                }
            }
        }
    }
    
    private void sendStatsTextMessage(boolean checkLevel) {
        sendStatsTextMessage(SmsManager.getDefault(), checkLevel, mPhoneNumbers);
    }

    private void sendSingleTextMessage(SmsManager manager, String phoneNumber, String msg) {
        mDataLogger.log(String.format("SMS %s: %s", phoneNumber, msg));

        PendingIntent piSent = PendingIntent.getBroadcast(mContext, 0, new Intent(SMS_SENT), 0);
        PendingIntent piDelivered = PendingIntent.getBroadcast(mContext, 0, new Intent(SMS_DELIVERED), 0);
        manager.sendTextMessage(phoneNumber, null, msg, piSent, piDelivered);
    }

    private void sendMultipartTextMessage(SmsManager manager, String phoneNumber, ArrayList<String> msgList) {
        int i = 0;
        for (String msg : msgList) {
            mDataLogger.log(String.format("SMS %s[%d]: %s", phoneNumber, i, msg));
            i++;
        }
        manager.sendMultipartTextMessage(phoneNumber, null, msgList, null, null);
    }

    @Override
    public void run() {
        Looper.prepare();
        mDataLogger = new DataLogger(mContext);
        mHandler = new MsgHandler();
        mHandler.sendEmptyMessageDelayed(MSG_UPDATE_TELEMETRY, TELEMETRY_INTERVAL);
        mHandler.sendEmptyMessageDelayed(MSG_TAKE_PHOTO, PHOTO_INTERVAL);
        if (SEND_TXT_MESSAGES) {
            mHandler.sendEmptyMessageDelayed(MSG_SEND_TEXT_ALERT, SMS_ALERT_INTERVAL);
        }
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
                if (msg.arg1 == DroidCamera.RESULT_CANCELED) {
                    takeNextPhoto();
                    return;
                }
                int photoCount = msg.getData().getInt(DroidCamera.RESULT_IMAGE_COUNT);
                String photoPath = msg.getData().getString(DroidCamera.RESULT_IMAGE_FILE);
                String thumbPath = msg.getData().getString(DroidCamera.RESULT_THUMB_FILE);
                onPhotoTaken(photoCount, photoPath, thumbPath);
                break;
            case MSG_START_PHOTO_DATA:
                mPhotoData.index = msg.arg1;
                if (!mSendingChunks) {
                    mSendingChunks = true;
                    mPhotoDataStart = System.currentTimeMillis();
                    sendEmptyMessageDelayed(MSG_SEND_PHOTO_CHUNK, PHOTO_CHUNK_INTERVAL);
                }
                break;
            case MSG_STOP_PHOTO_DATA:
                mSendingChunks = false;
                break;
            case MSG_SEND_TEXT:
                sendStatsTextMessage(false);
                break;
            case MSG_SEND_TEXT_ALERT:
                sendStatsTextMessage(true);
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
