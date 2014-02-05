package com.arcaner.pepper2.proto;

import java.nio.ByteBuffer;

public class DroidTelemetry extends ProtoMessage {
    public static final int TYPE = 2;
    public static final int LEN  = 23;

    public short battery, radio, accelState;
    public int accelDuration, photoCount;
    public double latitude, longitude;

    public DroidTelemetry() {
        super();
    }

    public DroidTelemetry(Header header, ByteBuffer buf) {
        super(header, buf);
        battery = (short) (buf.get() & 0xff);
        radio = (short) (buf.get() & 0xff);
        accelState = (short) (buf.get() & 0xff);
        accelDuration = buf.getShort() & 0xffff;
        photoCount = buf.getShort() & 0xffff;
        latitude = buf.getDouble();
        longitude = buf.getDouble();
    }

    public void fillBuffer(ByteBuffer buf) {
        buf.put((byte) battery)
           .put((byte) radio)
           .put((byte) accelState)
           .putShort((short) accelDuration)
           .putShort((short) photoCount)
           .putDouble(latitude)
           .putDouble(longitude);
    }

    public int getType() {
        return TYPE;
    }

    public int getLen() {
        return LEN;
    }
}
