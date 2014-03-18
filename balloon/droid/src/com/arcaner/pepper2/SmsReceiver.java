package com.arcaner.pepper2;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.Bundle;
import android.telephony.SmsMessage;
import android.util.Log;

public class SmsReceiver extends BroadcastReceiver {
    private static final String TAG = "SmsReceiver";

    private Pepper2Droid mPepper2Droid;

    public SmsReceiver(Pepper2Droid pepper2Droid) {
        mPepper2Droid = pepper2Droid;
    }

    @Override
    public void onReceive(Context context, Intent intent) {
        Bundle extras = intent.getExtras();
        if (extras != null) {
            Object[] smsExtras = (Object[]) extras.get("pdus");
            for (int i = 0; i < smsExtras.length; i++) {
                SmsMessage smsMsg = SmsMessage.createFromPdu((byte[]) smsExtras[i]);
                String strMsgBody = smsMsg.getMessageBody().toString();
                String strMsgSrc = smsMsg.getOriginatingAddress();

                Log.i(TAG, "SMS from " + strMsgSrc + " : " + strMsgBody);
                mPepper2Droid.onTextReceived(strMsgBody, strMsgSrc);
            }
        }
    }

}
