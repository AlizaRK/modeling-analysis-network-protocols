
(* ============================================ *)
(* VERIFICATION QUERIES FOR CPN MODEL *)
(* ============================================ *)

(* Query 1: Deadlock Freedom *)
fun isDeadlockFree() = 
    Node.Deadlock() = false;

(* Query 2: Liveness - All frames eventually acknowledged *)
fun allFramesAcknowledged(maxSeq: int) =
    Mark.LastAckReceived() >= maxSeq;

(* Query 3: Buffer Bounded *)
fun bufferWithinCapacity() =
    length(Mark.PacketBuffer()) <= 10;

(* Query 4: Window Constraint *)
fun windowSynchronized() =
    let
        val sendWindow = Mark.SendWindow()
        val recvWindow = Mark.RecvWindow()
    in
        length(sendWindow) = length(recvWindow)
    end;

(* Query 5: No Duplication *)
fun noDuplicateDelivery() =
    (* Check that NextFrameExpected only increases *)
    Mark.NextFrameExpected() >= LastObserved.NextFrameExpected();

(* Query 6: Ordered Delivery *)
fun orderedDelivery() =
    (* All frames up to NextFrameExpected-1 have been delivered *)
    Mark.NextFrameExpected() = expectedNext;

(* State Space Queries *)
CPN'StateSpace.AllNodes(isDeadlockFree);
CPN'StateSpace.AllNodes(bufferWithinCapacity);
CPN'StateSpace.SomeNode(allFramesAcknowledged(20));

(* Performance Queries *)
fun averageDelay() =
    (* Calculate average time from send to ACK *)
    let
        val allTimestamps = getTimestamps()
    in
        sum(allTimestamps) / length(allTimestamps)
    end;

fun throughput() =
    (* Frames delivered per time unit *)
    Mark.LastAckReceived() / currentTime();

fun retransmissionRate() =
    (* Percentage of retransmitted frames *)
    totalRetransmissions() / totalFramesSent() * 100.0;
