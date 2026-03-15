(* Coloured Petri Net Model *)
(* Sliding Window ARQ - Selective Repeat Protocol *)
(* Window Size: 10 *)
(* Timeout: 100ms *)
(* Network Delay: 20ms ± 5ms *)

(* COLOR SETS *)
colset INT = int;
colset BOOL = bool;
colset WINDOW = list INT;
colset PACKET = product INT * INT * BOOL timed;
colset ACK = product INT * BOOL timed;
colset BUFFER_ENTRY = product INT * PACKET * BOOL;
colset MUTEX_STATE = with LOCKED | UNLOCKED;
colset TIMER_LIST = list (INT * INT);

(* PLACES *)
place SendWindow : list int;
(* Sender's sliding window - tracks which frames can be sent *)
markings SendWindow = 1`[0, 1, 2, 3, 4, 5, 6, 7, 8, 9];

place NextFrameToSend : int;
(* Next frame sequence number to send *)
markings NextFrameToSend = 1`0;

place LastAckReceived : int;
(* Last acknowledged frame sequence number *)
markings LastAckReceived = 1`-1;

place SenderReady : bool;
(* Indicates if sender is ready to transmit *)
markings SenderReady = 1`true;

place SenderTimers : list (int * int);
(* List of (seq_num, timeout_time) for sent frames *)
markings SenderTimers = 1`[];

place RecvWindow : list int;
(* Receiver's window - tracks expected frames *)
markings RecvWindow = 1`[0, 1, 2, 3, 4, 5, 6, 7, 8, 9];

place NextFrameExpected : int;
(* Next expected frame in sequence *)
markings NextFrameExpected = 1`0;

place LastFrameAckd : int;
(* Last frame that was acknowledged *)
markings LastFrameAckd = 1`-1;

place ReceiverReady : bool;
(* Indicates if receiver is ready *)
markings ReceiverReady = 1`true;

place NetworkChannel_Frames : product int * int * bool timed;
(* Frames in transit (delay=20ms, jitter=5ms) *)
markings NetworkChannel_Frames = 1`empty;

place NetworkChannel_ACKs : product int * bool timed;
(* ACKs in transit (delay=20ms, jitter=5ms) *)
markings NetworkChannel_ACKs = 1`empty;

place PacketBuffer : product int * (product int * int * bool) * bool;
(* Shared buffer for out-of-order packets (capacity=10) *)
markings PacketBuffer = 1`[];

place BufferMutex : with LOCKED | UNLOCKED;
(* Mutex controlling access to packet buffer (maxAccess=1ms) *)
markings BufferMutex = 1`UNLOCKED;


(* TRANSITIONS *)
trans sendData 
(* Sender transmits a data frame *)
from SenderReady, SendWindow, NextFrameToSend
to NetworkChannel_Frames, SenderTimers, NextFrameToSend, SendWindow
guard [length(sendWindow) > 0 andalso senderReady = true]
action {let
    val nextSeq = hd(sendWindow)
    val data = generateRandomData()
    val packet = (nextSeq, data, true)
    val timer = (nextSeq, currentTime() + 100)
in
    (packet, timer, nextSeq + 1, tl(sendWindow))
end}@+20;

trans receiveACK 
(* Sender receives ACK and updates window *)
from NetworkChannel_ACKs, LastAckReceived, SendWindow, SenderTimers
to LastAckReceived, SendWindow, SenderTimers
guard [ack_seq > lastAck andalso isPositive = true]
action {let
    val newLastAck = ack_seq
    val newWindow = slideWindow(sendWindow, ack_seq, lastAck)
    val newTimers = removeTimer(timers, ack_seq)
in
    (newLastAck, newWindow, newTimers)
end};

trans handleTimeout 
(* Retransmit frame after timeout *)
from SenderTimers, SendWindow
to NetworkChannel_Frames, SenderTimers
guard [exists timer in timers where currentTime() >= timeout_time]
action {let
    val (seq_num, _) = findTimedOutFrame(timers)
    val packet = (seq_num, retrieveData(seq_num), true)
    val newTimer = (seq_num, currentTime() + 100)
    val newTimers = updateTimer(timers, newTimer)
in
    (packet, newTimers)
end}@+20;

trans receiveFrame 
(* Receiver processes incoming frame *)
from NetworkChannel_Frames, RecvWindow, NextFrameExpected, BufferMutex
to NetworkChannel_ACKs, NextFrameExpected, PacketBuffer, BufferMutex
guard [seq_num in recvWindow]
action {let
    val (seq, data, _) = packet
in
    if seq = nextExpected then
        (* In-order frame *)
        let
            val ack = (seq, true)
            val newNext = seq + 1
        in
            (ack, newNext, buffer, UNLOCKED)
        end
    else if seq > nextExpected then
        (* Out-of-order frame - buffer it *)
        let
            val ack = (seq, true)
            val newBuffer = addToBuffer(buffer, packet)
        in
            (ack, nextExpected, newBuffer, UNLOCKED)
        end
    else
        (* Duplicate - just ACK *)
        ((seq, true), nextExpected, buffer, UNLOCKED)
end}@+20;

trans sendACK 
(* Receiver sends acknowledgment *)
from ReceiverReady, LastFrameAckd
to NetworkChannel_ACKs, LastFrameAckd
guard [receiverReady = true]
action {let
    val ack = (lastAckd + 1, true)
in
    (ack, lastAckd + 1)
end}@+20;

trans retrieveFrame 
(* Retrieve consecutive frames from buffer *)
from PacketBuffer, BufferMutex, NextFrameExpected
to PacketBuffer, BufferMutex, NextFrameExpected
guard [mutex = UNLOCKED andalso bufferContains(buffer, nextExpected)]
action {let
    val (frames, newBuffer) = extractConsecutiveFrames(buffer, nextExpected)
    val newNext = nextExpected + length(frames)
in
    (newBuffer, UNLOCKED, newNext)
end};

trans frameDropped [prob=0.05]
(* Simulate frame loss in network (5% probability) *)
from NetworkChannel_Frames
to 
guard [true]
action {(* Frame is dropped - simulates packet loss *)};

trans ackDropped [prob=0.05]
(* Simulate ACK loss in network (5% probability) *)
from NetworkChannel_ACKs
to 
guard [true]
action {(* ACK is dropped - simulates ACK loss *)};
