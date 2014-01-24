package com.arcaner.pepper2;

import java.io.IOException;
import java.util.UUID;

import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothServerSocket;
import android.bluetooth.BluetoothSocket;
import android.os.Build;
import android.util.Log;

public class BluetoothServer implements Runnable {
    private static final String TAG = "BluetoothTest";
    private static final String UUID_STR = "de746609-6dbf-4917-9040-40d1d2ce9c79";

    private BluetoothServerSocket mBtServer;
    private Pepper2Droid mPepper2Droid;
    private BluetoothAdapter mBtAdapter;
    private boolean mRunning = false;

    public BluetoothServer(MainActivity context) {
        mPepper2Droid = new Pepper2Droid(context);

        if (Build.VERSION.SDK_INT <= Build.VERSION_CODES.JELLY_BEAN_MR1) {
            mBtAdapter = BluetoothAdapter.getDefaultAdapter();
        } else {
            mBtAdapter = (BluetoothAdapter) context
                    .getSystemService("bluetooth");
        }

        new Thread(this).start();
    }

    public void shutdown() {
        mRunning = false;

        if (mBtServer != null) {
            try {
                mBtServer.close();
            } catch (IOException e) {
            }
        }

        if (mPepper2Droid != null) {
            mPepper2Droid.shutdown();
        }

        mPepper2Droid = null;
        mBtAdapter = null;
    }

    private boolean ensureServerRunning() {
        if (mBtServer != null) {
            return true;
        }

        try {
            mBtServer = mBtAdapter.listenUsingRfcommWithServiceRecord(
                    "pepper2 service", UUID.fromString(UUID_STR));
            return true;
        } catch (IOException e) {
            Log.e(TAG, "error setting up bt server", e);
        }

        return false;
    }

    public void run() {
        mRunning = true;
        while (mRunning) {
            try {
                if (!ensureServerRunning()) {
                    try {
                        Thread.sleep(2000L);
                    } catch (InterruptedException e) {
                    }
                }

                BluetoothSocket socket = mBtServer.accept();
                if (socket == null) {
                    continue;
                }

                mPepper2Droid.setBluetoothSocket(socket);
            } catch (IOException e) {
                Log.e(TAG, "error accepting", e);
            }
        }
    }
}
