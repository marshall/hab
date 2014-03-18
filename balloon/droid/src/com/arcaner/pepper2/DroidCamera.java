package com.arcaner.pepper2;

import java.io.File;
import java.io.FileNotFoundException;
import java.io.FileOutputStream;
import java.io.IOException;

import android.app.Activity;
import android.content.Intent;
import android.content.pm.ActivityInfo;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.hardware.Camera;
import android.media.ThumbnailUtils;
import android.os.Bundle;
import android.util.Log;
import android.view.SurfaceHolder;
import android.view.SurfaceView;
import android.view.Window;
import android.view.WindowManager;

public class DroidCamera extends Activity
                         implements SurfaceHolder.Callback, Camera.PictureCallback
{
    public static final String RESULT_IMAGE_FILE = "image_file";
    public static final String RESULT_THUMB_FILE = "thumb_file";
    public static final String RESULT_IMAGE_COUNT = "image_count";

    public static final String IMAGE_DIR = "images";
    public static final String IMAGE_FORMAT = "img-%03d.jpg";
    public static final String THUMB_FORMAT = "img-%03d-thumb.jpg";
    public static final String REL_IMAGE_FORMAT = IMAGE_DIR + "/"
            + IMAGE_FORMAT;
    public static final String REL_THUMB_FORMAT = IMAGE_DIR + "/"
            + THUMB_FORMAT;

    private static final String TAG = "DroidCamera";
    private static final int THUMB_WIDTH = 2560 / 5;
    private static final int THUMB_HEIGHT = 1920 / 5;

    private static int imageCount = 0;

    private Camera mCamera;
    private SurfaceView mSurfaceView;
    private SurfaceHolder mHolder;
    private File imageDir;

    public static String getRelativeImagePath(int index) {
        return String.format(REL_IMAGE_FORMAT, index);
    }

    public static String getRelativeThumbPath(int index) {
        return String.format(REL_THUMB_FORMAT, index);
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        // TODO Auto-generated method stub
        super.onCreate(savedInstanceState);

        imageDir = new File(getExternalFilesDir(null), IMAGE_DIR);
        if (!imageDir.exists()) {
            imageDir.mkdirs();
        }

        requestWindowFeature(Window.FEATURE_NO_TITLE);
        getWindow().setFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN,
                WindowManager.LayoutParams.FLAG_FULLSCREEN);
        setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_PORTRAIT);

        if (!initCamera()) {
            Intent resultIntent = new Intent();
            resultIntent.putExtra(RESULT_IMAGE_COUNT, imageCount);
            setResult(RESULT_CANCELED, resultIntent);
            finish();
        }

        mSurfaceView = new SurfaceView(this);
        setContentView(mSurfaceView);

        // Install a SurfaceHolder.Callback so we get notified when the
        // underlying surface is created and destroyed.
        mHolder = mSurfaceView.getHolder();
        mHolder.addCallback(this);
        mHolder.setType(SurfaceHolder.SURFACE_TYPE_PUSH_BUFFERS);
    }

    private boolean initCamera() {
        if (!safeCameraOpen()) {
            Log.e(TAG, "Couldn't open camera");
            return false;
        }

        Camera.Parameters params = mCamera.getParameters();
        params.setJpegQuality(100);
        params.setFlashMode(Camera.Parameters.FLASH_MODE_OFF);
        params.setJpegThumbnailQuality(75);
        params.setJpegThumbnailSize(THUMB_WIDTH, THUMB_HEIGHT);
        mCamera.setParameters(params);
        return true;
    }

    private boolean safeCameraOpen() {
        boolean qOpened = false;

        try {
            releaseCameraAndPreview();
            mCamera = Camera.open();
            qOpened = (mCamera != null);
        } catch (Exception e) {
            Log.e(TAG, "failed to open Camera", e);
        }

        return qOpened;
    }

    private void releaseCameraAndPreview() {
        if (mCamera != null) {
            mCamera.stopPreview();
            mCamera.release();
            mCamera = null;
        }
    }

    @Override
    public void surfaceCreated(SurfaceHolder holder) {
        try {
            mCamera.setPreviewDisplay(holder);
            mCamera.startPreview();
            mCamera.takePicture(null, null, this);
        } catch (IOException e) {
            Log.e(TAG, "error setting preview display", e);
        }
    }

    @Override
    public void surfaceChanged(SurfaceHolder holder, int format, int width,
            int height) {
    }

    @Override
    public void surfaceDestroyed(SurfaceHolder holder) {
        if (mCamera != null) {
            mCamera.stopPreview();
        }
    }

    @Override
    public void onPictureTaken(byte[] data, Camera camera) {
        Log.i(TAG, String.format("picture %d taken, %d bytes", imageCount,
                data.length));

        File imgFile = new File(imageDir, String.format(IMAGE_FORMAT,
                imageCount));
        File thumbFile = new File(imageDir, String.format(THUMB_FORMAT,
                imageCount));
        Intent resultIntent = new Intent();
        int resultCode = RESULT_OK;

        FileOutputStream fos = null;
        ;
        try {
            fos = new FileOutputStream(imgFile);
            fos.write(data);
            fos.close();
            fos = null;
            resultIntent.putExtra(RESULT_IMAGE_FILE, imgFile.getAbsolutePath());
            resultIntent.putExtra(RESULT_IMAGE_COUNT, imageCount);
            imageCount++;

            Bitmap thumbBitmap = ThumbnailUtils.extractThumbnail(
                    BitmapFactory.decodeByteArray(data, 0, data.length),
                    THUMB_WIDTH, THUMB_HEIGHT);
            fos = new FileOutputStream(thumbFile);
            thumbBitmap.compress(Bitmap.CompressFormat.JPEG, 75, fos);
            fos.close();
            fos = null;
            resultIntent.putExtra(RESULT_THUMB_FILE,
                    thumbFile.getAbsolutePath());

        } catch (FileNotFoundException e) {
            resultCode = RESULT_CANCELED;
            Log.e(TAG, "file not found", e);
        } catch (IOException e) {
            resultCode = RESULT_CANCELED;
            Log.e(TAG, "io exception", e);
        }

        if (fos != null) {
            try {
                fos.close();
            } catch (IOException e) {
            }
        }

        releaseCameraAndPreview();
        setResult(resultCode, resultIntent);
        finish();
    }
}
