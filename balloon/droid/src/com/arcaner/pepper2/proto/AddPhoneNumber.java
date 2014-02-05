package com.arcaner.pepper2.proto;

import java.nio.ByteBuffer;

public class AddPhoneNumber extends ProtoMessage {
    public static final int TYPE = 13;

    public String phoneNumber;

    public AddPhoneNumber() {
        super();
        phoneNumber = "";
    }
    
    public AddPhoneNumber(Header header, ByteBuffer buf) {
        super(header, buf);

        byte[] phoneBytes = new byte[header.msgLen];
        buf.get(phoneBytes);
        phoneNumber = new String(phoneBytes);
    }

    @Override
    public void fillBuffer(ByteBuffer buf) {
        buf.put(phoneNumber.getBytes());
    }

    @Override
    public int getType() {
        return TYPE;
    }

    @Override
    public int getLen() {
        return phoneNumber.length();
    }

}
