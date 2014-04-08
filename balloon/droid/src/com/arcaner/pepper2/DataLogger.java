package com.arcaner.pepper2;

import java.io.File;
import java.io.FileNotFoundException;
import java.io.FileOutputStream;
import java.io.IOException;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

import org.json.JSONException;
import org.json.JSONObject;

import android.content.Context;
import android.os.Handler;
import android.os.Message;
import android.util.Log;

import com.arcaner.pepper2.proto.DroidTelemetry;

public class DataLogger implements Handler.Callback {
    private static final String TAG = "PEPPER2-DLOG";
    private static final int MSG_LOG_STRING    = 900;
    private static final int MSG_LOG_TELEMETRY = 901;

    private Handler mHandler;
    private File mLogFile;
    private JSONObject mData = new JSONObject();
    private JSONObject mTelemetry = new JSONObject();

    public DataLogger(Context context) {
        mHandler = new Handler(this);

        String timestamp = new SimpleDateFormat("yyyyddMM", Locale.US).format(new Date());
        mLogFile = new File(context.getExternalFilesDir(null), "pepper2-" + timestamp + ".log");
        Log.i(TAG, "Logging to " + mLogFile.getAbsolutePath());
    }

    @Override
    public boolean handleMessage(Message msg) {
        switch (msg.what) {
        case MSG_LOG_STRING:
            doLog((String) msg.obj);
            return true;
        case MSG_LOG_TELEMETRY:
            doLog((DroidTelemetry) msg.obj);
            return true;
        }
        return false;
    }

    private void doLog() {
        try {
            FileOutputStream out = new FileOutputStream(mLogFile, true);
            String jsonData = mData.toString();
            out.write(jsonData.getBytes());
            out.write('\n');
            out.close();
        } catch (FileNotFoundException e) {
        } catch (IOException e) {
        }
    }

    private void doLog(String message) {
        try {
            mData.put("type", "string");
            mData.put("data", message);
            doLog();
        } catch (JSONException e) {
        }
    }

    private void doLog(DroidTelemetry telemetry) {
        try {
            mData.put("type", "telemetry");
            mData.put("data", mTelemetry);
            mTelemetry.put("battery", telemetry.battery);
            mTelemetry.put("radioDbm", telemetry.radioDbm);
            mTelemetry.put("radioBars", telemetry.radioBars);
            mTelemetry.put("photoCount", telemetry.photoCount);
            mTelemetry.put("latitude", telemetry.latitude);
            mTelemetry.put("longitude", telemetry.longitude);
            mTelemetry.put("accelState", telemetry.accelState);
            mTelemetry.put("accelDuration", telemetry.accelDuration);
            doLog();
        } catch (JSONException e) {
        }
    }

    public void log(String message) {
        Log.i(TAG, message);
        Message.obtain(mHandler, MSG_LOG_STRING, message).sendToTarget();
    }

    public void log(DroidTelemetry telemetry) {
        Message.obtain(mHandler, MSG_LOG_TELEMETRY, telemetry).sendToTarget();
    }
}
