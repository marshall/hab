package com.arcaner.pepper2;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.os.Message;
import android.util.Log;

public class MainActivity extends Activity {
    private static final String TAG = "Main";
    public static final int PHOTO_RESULT = 10;

    private Handler mPhotoHandler;
    private int mPhotoHandlerMsg;
    private BluetoothServer mBtServer;

    public void setPhotoHandler(Handler handler, int msgType) {
        mPhotoHandler = handler;
        mPhotoHandlerMsg = msgType;
    }

    public void takePhoto() {
        Intent intent = new Intent(this, DroidCamera.class);
        startActivityForResult(intent, PHOTO_RESULT);
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
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
            Log.i(TAG, "got photo result in MainActiivty");
            Message msg = Message.obtain(mPhotoHandler, mPhotoHandlerMsg);
            msg.arg1 = resultCode;
            msg.setData(data.getExtras());
            msg.sendToTarget();
        }
        super.onActivityResult(requestCode, resultCode, data);
    }
}