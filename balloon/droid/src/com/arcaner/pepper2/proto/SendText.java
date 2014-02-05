package com.arcaner.pepper2.proto;

import java.nio.ByteBuffer;

public class SendText extends ProtoMessage {
    public static final int TYPE = 12;
    public static final int LEN  = 0;

    public SendText() {
        super();
    }

    public SendText(Header header, ByteBuffer buf) {
        super(header, buf);
    }

    @Override
    public void fillBuffer(ByteBuffer buf) {
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
