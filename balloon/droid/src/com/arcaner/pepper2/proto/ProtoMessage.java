package com.arcaner.pepper2.proto;

import java.io.IOException;
import java.io.OutputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.zip.CRC32;

import android.util.Log;

public abstract class ProtoMessage {
    private static final String TAG = "PEPPER2-MSG";

    public static final int MARKER_BEGIN = 0x9d9a;
    public static final int MARKER_END   = 0x9592;
    public static final int MARKER_LEN   = 2;
    public static final int HEADER_LEN   = 6;
    public static final int ENVELOPE_LEN = MARKER_LEN + HEADER_LEN + MARKER_LEN;
    public static final int MAX_MSG_LEN  = 255;
    public static final int MAX_DATA_LEN = MAX_MSG_LEN - ENVELOPE_LEN;
    public static final int HEADER_END   = MARKER_LEN + HEADER_LEN;

    protected ByteBuffer mBuffer;
    protected Header mHeader;

    public abstract void fillBuffer(ByteBuffer buf);
    public abstract int getType();
    public abstract int getLen();

    public static class Header {
        public int msgType, msgLen;
        public long crc32;
    }

    public static Header readHeader(ByteBuffer buf) 
        throws BadMarker, IndexOutOfBoundsException
    {
        buf.position(0);
        int begin = buf.getShort() & 0xffff;
        if (begin != MARKER_BEGIN) {
            throw new BadMarker(begin, MARKER_BEGIN);
        }

        if (buf.remaining() < HEADER_END - 1) {
            throw new IndexOutOfBoundsException();
        }

        Header header = new Header();
        header.msgType = (int) (buf.get() & 0xff);
        header.msgLen = (int) (buf.get() & 0xff);
        header.crc32 = (long) (buf.get() & 0xffffffff);
        return header;
    }

    public static ProtoMessage readMessage(ByteBuffer buf)
        throws BadMarker, BadMsgType, BadChecksum, IndexOutOfBoundsException
    {
        return readMessage(readHeader(buf), buf);
    }

    public static ProtoMessage readMessage(Header header, ByteBuffer buf)
        throws BadMarker, BadMsgType, BadChecksum, IndexOutOfBoundsException
    {
        CRC32 crc32 = new CRC32();
        for (int i = HEADER_END; i < HEADER_END + header.msgLen; i++) {
            crc32.update(buf.get(i));
        }
        if (header.crc32 != crc32.getValue()) {
            throw new BadChecksum(crc32.getValue(), header.crc32);
        }

        buf.position(HEADER_END);
        ProtoMessage msg = null;
        switch (header.msgType) {
            case DroidTelemetry.TYPE:
                msg = new DroidTelemetry(header, buf);
                break;
            case PhotoData.TYPE:
                msg = new PhotoData(header, buf);
                break;
            case StartPhotoData.TYPE:
                msg = new StartPhotoData(header, buf);
                break;
            case StopPhotoData.TYPE:
                msg = new StopPhotoData(header, buf);
                break;
            case SendText.TYPE:
                msg = new SendText(header, buf);
                break;
            case AddPhoneNumber.TYPE:
                msg = new AddPhoneNumber(header, buf);
                break;
            default:
                throw new BadMsgType(header.msgType);
        }

        if (buf.remaining() < MARKER_LEN) {
            throw new IndexOutOfBoundsException("Not enough room for end marker");
        }

        int endMarker = (int) (buf.getShort() & 0xffff);
        if (endMarker != MARKER_END) {
            throw new BadMarker(endMarker, MARKER_END);
        }

        return msg;
    }

    public ProtoMessage() {
        mHeader = null;
        mBuffer = allocate(MAX_MSG_LEN);
    }

    public ProtoMessage(Header header, ByteBuffer buf) {
        mHeader = header;
        mBuffer = buf;
    }

    public static ByteBuffer allocate(int msgDataLen) {
        ByteBuffer buf = ByteBuffer.allocate(MARKER_LEN + HEADER_LEN + msgDataLen + MARKER_LEN);
        buf.order(ByteOrder.BIG_ENDIAN);
        buf.position(0);
        return buf;
    }

    private ByteBuffer writeHeader(ByteBuffer buf) {
        buf.putShort((short) MARKER_BEGIN);
        buf.put((byte) getType());
        buf.put((byte) getLen());
        return buf;
    }

    private ByteBuffer writeData(ByteBuffer buf) {
        buf.position(HEADER_END);
        fillBuffer(buf);

        CRC32 crc32 = new CRC32();
        for (int i = HEADER_END; i < HEADER_END + getLen(); i++) {
            crc32.update(buf.get(i));
        }
        buf.putInt(HEADER_END - 4, (int) crc32.getValue());
        buf.putShort(HEADER_END + getLen(), (short) MARKER_END);
        return buf;
    }

    public ByteBuffer writeTo(ByteBuffer buf) {
        return writeData(writeHeader(buf));
    }

    public void writeTo(OutputStream out)
        throws IOException
    {
        mBuffer.position(0);
        writeTo(mBuffer);

        StringBuilder sb = new StringBuilder("Write ");
        sb.append(getClass().getSimpleName());
        sb.append('[');
        mBuffer.position(0);
        for (int i = 0; i < getBufferLen(); i++) {
            byte b = mBuffer.get(i);
            sb.append(Integer.toHexString(b & 0xff)).append(" ");
            out.write(b);
        }
        sb.append(']');

        Log.d(TAG, sb.toString());
    }

    public ByteBuffer getBuffer() {
        mBuffer.position(0);
        writeTo(mBuffer);

        mBuffer.position(0);
        return mBuffer;
    }

    public int getBufferLen() {
        return getLen() + HEADER_END + MARKER_LEN;
    }
}
