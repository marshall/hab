package com.arcaner.pepper2;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.os.Message;
import android.view.WindowManager;
import android.widget.TableLayout;
import android.widget.TextView;

public class MainActivity extends Activity {
    private static final String TAG = "Main";
    public static final int PHOTO_RESULT = 10;

    private long mBegin = System.currentTimeMillis();
    private Handler mPhotoHandler;
    private int mPhotoHandlerMsg;
    private BluetoothServer mBtServer;
    private Handler mHandler;

    public void setPhotoHandler(Handler handler, int msgType) {
        mPhotoHandler = handler;
        mPhotoHandlerMsg = msgType;
    }

    public void takePhoto() {
        Intent intent = new Intent(this, DroidCamera.class);
        startActivityForResult(intent, PHOTO_RESULT);
    }

    public void updateUI(final int photos, final boolean connected, final int battery, final int cellSignal, final String diskAvailable) {
        runOnUiThread(new Runnable() {
            public void run() {
                ((TextView) findViewById(R.id.photos_label)).setText(Integer.toString(photos));

                TextView connectedLabel = (TextView) findViewById(R.id.connected_label);
                connectedLabel.setText(connected ? "YES" : "NO");
                connectedLabel.setTextColor(getResources().getColor(connected ? R.color.connected_yes : R.color.connected_no));

                long uptime = System.currentTimeMillis() - mBegin;
                long uptimeSecs = uptime / 1000;
                int hours = (int) uptimeSecs / 3600;
                int hrSecs = hours * 3600;
                int minutes = (int) (uptimeSecs - hrSecs) / 60;
                int seconds = (int) uptimeSecs - hrSecs - (minutes * 60);

                ((TextView) findViewById(R.id.uptime_label)).setText(String.format("%02d:%02d:%02d", hours, minutes, seconds));
                ((TextView) findViewById(R.id.battery_label)).setText(String.format("%d%%", battery));
                ((TextView) findViewById(R.id.cell_label)).setText(String.format("%d%%", cellSignal));
                ((TextView) findViewById(R.id.disk_free)).setText(diskAvailable);
            }
        });
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        getWindow().setFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN, WindowManager.LayoutParams.FLAG_FULLSCREEN);
        setContentView(R.layout.activity_main);
        mBtServer = new BluetoothServer(this);
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        mBtServer.shutdown();
        mBtServer = null;
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        if (requestCode == PHOTO_RESULT) {
            Message msg = Message.obtain(mPhotoHandler, mPhotoHandlerMsg);
            msg.arg1 = resultCode;
            msg.setData(data.getExtras());
            msg.sendToTarget();
        }
        super.onActivityResult(requestCode, resultCode, data);
    }

}