package com.arcaner.pepper2.proto;

import java.nio.ByteBuffer;

public class PhotoData extends ProtoMessage {
    public static final int TYPE = 3;
    public static final int LEN  = 10;

    public int index, chunk, chunkCount;
    public long fileSize;
    public byte[] chunkData;
    public int chunkDataLen;

    public PhotoData() {
        super();
        chunkData = new byte[ProtoMessage.MAX_DATA_LEN];
        chunkDataLen = ProtoMessage.MAX_DATA_LEN;
    }

    public PhotoData(Header header, ByteBuffer buf) {
        super(header, buf);
        index = (int) (buf.getShort() & 0xffff);
        chunk = (int) (buf.getShort() & 0xffff);
        chunkCount = (int) (buf.getShort() & 0xffff);
        fileSize = (long) (buf.getInt() & 0xffffffff);
        chunkDataLen = buf.remaining() - MARKER_LEN;
        chunkData = new byte[chunkDataLen];
        buf.get(chunkData);
    }

    @Override
    public void fillBuffer(ByteBuffer buf) {
        buf.putShort((short) index)
           .putShort((short) chunk)
           .putShort((short) chunkCount)
           .putInt((int) fileSize)
           .put(chunkData, 0, chunkDataLen);
    }

    @Override
    public int getType() {
        return TYPE;
    }

    @Override
    public int getLen() {
        return LEN + chunkDataLen;
    }

}
