package com.arcaner.pepper2.proto;

public class BadMsgType extends Exception {
    public BadMsgType(int msgType) {
        super(String.format("Bad message type %d", msgType));
    }
}
