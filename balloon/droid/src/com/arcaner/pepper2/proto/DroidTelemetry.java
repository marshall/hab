package com.arcaner.pepper2.proto;

import java.nio.ByteBuffer;

public class DroidTelemetry extends ProtoMessage {
    public static final int TYPE = 2;
    public static final int LEN  = 24;

    public short battery, radioDbm, radioBars, accelState;
    public int accelDuration, photoCount;
    public double latitude, longitude;

    public DroidTelemetry() {
        super();
    }

    public DroidTelemetry(Header header, ByteBuffer buf) {
        super(header, buf);
        battery = (short) (buf.get() & 0xff);
        radioDbm = (short) (buf.get() & 0xff);
        radioBars = (short) (buf.get() & 0xff);
        accelState = (short) (buf.get() & 0xff);
        accelDuration = buf.getShort() & 0xffff;
        photoCount = buf.getShort() & 0xffff;
        latitude = buf.getDouble();
        longitude = buf.getDouble();
    }

    public void fillBuffer(ByteBuffer buf) {
        buf.put((byte) battery)
           .put((byte) radioDbm)
           .put((byte) radioBars)
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
