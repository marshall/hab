package com.arcaner.pepper2.proto;

import java.io.IOException;
import java.io.InputStream;
import java.nio.ByteBuffer;

import com.arcaner.pepper2.proto.ProtoMessage.Header;

public class ProtoMessageReader {
    public static enum State {
        HEADER, DATA, END
    };

    private ByteBuffer mBuffer;
    private Header mHeader;
    private ProtoMessage mMessage;
    private State mState = State.HEADER;
    private int mIndex = 0;

    public ProtoMessage read(InputStream in) {
        mBuffer = ByteBuffer.allocate(ProtoMessage.MAX_MSG_LEN);
        while (mState != State.END) {
            try {
                if (in.available() == 0) {
                    return null;
                }

                int b = in.read();
                if (b == -1) {
                    return null;
                }

                mBuffer.put(mIndex, (byte) b);
                mIndex++;

                switch (mState) {
                    case HEADER:
                        handleHeaderByte();
                        break;
                    case DATA:
                        handleDataByte();
                        break;
                    default:
                        break;
                }
            } catch (IOException e) {
                break;
            }
        }

        mState = State.HEADER;
        mIndex = 0;
        return mMessage;
    }

    private void handleHeaderByte() {
        if (mIndex != ProtoMessage.HEADER_END) {
            return;
        }

        try {
            mHeader = ProtoMessage.readHeader(mBuffer);
            mState = State.DATA;
        } catch (BadMarker e) {
            return;
        } catch (IndexOutOfBoundsException e) {
            return;
        }
    }

    private void handleDataByte() {
        if (mIndex != ProtoMessage.HEADER_END + mHeader.msgLen + ProtoMessage.MARKER_LEN) {
            return;
        }

        try {
            mMessage = ProtoMessage.readMessage(mHeader, mBuffer);
            mState = State.END;
        } catch (BadMarker e) {
            return;
        } catch (BadMsgType e) {
            return;
        } catch (BadChecksum e) {
            return;
        } catch (IndexOutOfBoundsException e) {
            return;
        }
    }
}