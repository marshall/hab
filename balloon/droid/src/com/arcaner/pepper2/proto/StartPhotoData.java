package com.arcaner.pepper2.proto;

import java.nio.ByteBuffer;

public class StartPhotoData extends ProtoMessage {
    public static final int TYPE = 10;
    public static final int LEN  = 2;

    public int index;

    public StartPhotoData() {
        super();
    }

    public StartPhotoData(Header header, ByteBuffer buf) {
        super(header, buf);
        index = (int) (buf.getShort() & 0xffff);
    }

    @Override
    public void fillBuffer(ByteBuffer buf) {
        buf.putShort((short) index);
    }

    @Override
    public int getType() {
        return TYPE;
    }

    @Override
    public int getLen() {
        return LEN;
    }

}
