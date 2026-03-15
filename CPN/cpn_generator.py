"""
CPN Model Generator for Sliding Window ARQ Protocol
Generates CPN model in multiple formats without requiring CPN Tools
"""

import json
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from enum import Enum


class PlaceType(Enum):
    """Types of places in the CPN"""
    INT = "int"
    BOOL = "bool"
    STRING = "string"
    WINDOW = "list int"
    PACKET = "product int * int * bool timed"
    ACK = "product int * bool timed"
    BUFFER_ENTRY = "product int * (product int * int * bool) * bool"
    MUTEX_STATE = "with LOCKED | UNLOCKED"
    TIMER_LIST = "list (int * int)"


@dataclass
class Place:
    """Represents a place in the CPN"""
    name: str
    color_set: PlaceType
    initial_marking: str
    description: str
    position: Tuple[int, int] = (0, 0)
    
    def to_cpn_ml(self) -> str:
        """Convert to CPN ML syntax"""
        return f"""place {self.name} : {self.color_set.value};
(* {self.description} *)
markings {self.name} = 1`{self.initial_marking};
"""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON export"""
        return {
            "name": self.name,
            "type": self.color_set.value,
            "initial_marking": self.initial_marking,
            "description": self.description,
            "position": self.position
        }


@dataclass
class Transition:
    """Represents a transition in the CPN"""
    name: str
    input_places: List[str]
    output_places: List[str]
    guard: str
    action: str
    timing: Optional[int] = None
    probability: Optional[float] = None
    description: str = ""
    position: Tuple[int, int] = (0, 0)
    
    def to_cpn_ml(self) -> str:
        """Convert to CPN ML syntax"""
        timing_str = f"@+{self.timing}" if self.timing else ""
        prob_str = f"[prob={self.probability}]" if self.probability else ""
        
        return f"""trans {self.name} {prob_str}
(* {self.description} *)
from {', '.join(self.input_places)}
to {', '.join(self.output_places)}
guard [{self.guard}]
action {{{self.action}}}{timing_str};
"""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON export"""
        return {
            "name": self.name,
            "inputs": self.input_places,
            "outputs": self.output_places,
            "guard": self.guard,
            "action": self.action,
            "timing": self.timing,
            "probability": self.probability,
            "description": self.description,
            "position": self.position
        }


@dataclass
class Arc:
    """Represents an arc connecting a place and transition"""
    source: str
    target: str
    inscription: str
    arc_type: str = "normal"  # normal, inhibitor, reset
    
    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "target": self.target,
            "inscription": self.inscription,
            "type": self.arc_type
        }


class CPNModel:
    """Complete CPN Model for Sliding Window ARQ Protocol"""
    
    def __init__(self, window_size: int = 10, timeout_ms: int = 100, 
                 network_delay_ms: int = 20, jitter_ms: int = 5):
        self.window_size = window_size
        self.timeout_ms = timeout_ms
        self.network_delay_ms = network_delay_ms
        self.jitter_ms = jitter_ms
        
        self.places: List[Place] = []
        self.transitions: List[Transition] = []
        self.arcs: List[Arc] = []
        
        self._create_model()
    
    def _create_model(self):
        """Create the complete CPN model"""
        self._create_places()
        self._create_transitions()
        self._create_arcs()
    
    def _create_places(self):
        """Create all places in the model"""
        window_init = str(list(range(self.window_size)))
        
        # Sender places
        self.places.extend([
            Place("SendWindow", PlaceType.WINDOW, window_init,
                  "Sender's sliding window - tracks which frames can be sent",
                  (100, 100)),
            Place("NextFrameToSend", PlaceType.INT, "0",
                  "Next frame sequence number to send",
                  (100, 200)),
            Place("LastAckReceived", PlaceType.INT, "-1",
                  "Last acknowledged frame sequence number",
                  (100, 300)),
            Place("SenderReady", PlaceType.BOOL, "true",
                  "Indicates if sender is ready to transmit",
                  (100, 400)),
            Place("SenderTimers", PlaceType.TIMER_LIST, "[]",
                  "List of (seq_num, timeout_time) for sent frames",
                  (100, 500)),
        ])
        
        # Receiver places
        self.places.extend([
            Place("RecvWindow", PlaceType.WINDOW, window_init,
                  "Receiver's window - tracks expected frames",
                  (500, 100)),
            Place("NextFrameExpected", PlaceType.INT, "0",
                  "Next expected frame in sequence",
                  (500, 200)),
            Place("LastFrameAckd", PlaceType.INT, "-1",
                  "Last frame that was acknowledged",
                  (500, 300)),
            Place("ReceiverReady", PlaceType.BOOL, "true",
                  "Indicates if receiver is ready",
                  (500, 400)),
        ])
        
        # Channel places
        self.places.extend([
            Place("NetworkChannel_Frames", PlaceType.PACKET, "empty",
                  f"Frames in transit (delay={self.network_delay_ms}ms, jitter={self.jitter_ms}ms)",
                  (300, 150)),
            Place("NetworkChannel_ACKs", PlaceType.ACK, "empty",
                  f"ACKs in transit (delay={self.network_delay_ms}ms, jitter={self.jitter_ms}ms)",
                  (300, 350)),
        ])
        
        # Buffer and mutex places
        self.places.extend([
            Place("PacketBuffer", PlaceType.BUFFER_ENTRY, "[]",
                  f"Shared buffer for out-of-order packets (capacity={self.window_size})",
                  (500, 500)),
            Place("BufferMutex", PlaceType.MUTEX_STATE, "UNLOCKED",
                  "Mutex controlling access to packet buffer (maxAccess=1ms)",
                  (500, 600)),
        ])
    
    def _create_transitions(self):
        """Create all transitions in the model"""
        
        # T1: sendData
        self.transitions.append(Transition(
            name="sendData",
            input_places=["SenderReady", "SendWindow", "NextFrameToSend"],
            output_places=["NetworkChannel_Frames", "SenderTimers", "NextFrameToSend", "SendWindow"],
            guard="length(sendWindow) > 0 andalso senderReady = true",
            action=f"""let
    val nextSeq = hd(sendWindow)
    val data = generateRandomData()
    val packet = (nextSeq, data, true)
    val timer = (nextSeq, currentTime() + {self.timeout_ms})
in
    (packet, timer, nextSeq + 1, tl(sendWindow))
end""",
            timing=self.network_delay_ms,
            description="Sender transmits a data frame",
            position=(200, 100)
        ))
        
        # T2: receiveACK
        self.transitions.append(Transition(
            name="receiveACK",
            input_places=["NetworkChannel_ACKs", "LastAckReceived", "SendWindow", "SenderTimers"],
            output_places=["LastAckReceived", "SendWindow", "SenderTimers"],
            guard="ack_seq > lastAck andalso isPositive = true",
            action="""let
    val newLastAck = ack_seq
    val newWindow = slideWindow(sendWindow, ack_seq, lastAck)
    val newTimers = removeTimer(timers, ack_seq)
in
    (newLastAck, newWindow, newTimers)
end""",
            description="Sender receives ACK and updates window",
            position=(200, 300)
        ))
        
        # T3: handleTimeout
        self.transitions.append(Transition(
            name="handleTimeout",
            input_places=["SenderTimers", "SendWindow"],
            output_places=["NetworkChannel_Frames", "SenderTimers"],
            guard="exists timer in timers where currentTime() >= timeout_time",
            action=f"""let
    val (seq_num, _) = findTimedOutFrame(timers)
    val packet = (seq_num, retrieveData(seq_num), true)
    val newTimer = (seq_num, currentTime() + {self.timeout_ms})
    val newTimers = updateTimer(timers, newTimer)
in
    (packet, newTimers)
end""",
            timing=self.network_delay_ms,
            description="Retransmit frame after timeout",
            position=(200, 500)
        ))
        
        # T4: receiveFrame
        self.transitions.append(Transition(
            name="receiveFrame",
            input_places=["NetworkChannel_Frames", "RecvWindow", "NextFrameExpected", "BufferMutex"],
            output_places=["NetworkChannel_ACKs", "NextFrameExpected", "PacketBuffer", "BufferMutex"],
            guard="seq_num in recvWindow",
            action=f"""let
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
end""",
            timing=self.network_delay_ms,
            description="Receiver processes incoming frame",
            position=(400, 150)
        ))
        
        # T5: sendACK
        self.transitions.append(Transition(
            name="sendACK",
            input_places=["ReceiverReady", "LastFrameAckd"],
            output_places=["NetworkChannel_ACKs", "LastFrameAckd"],
            guard="receiverReady = true",
            action="""let
    val ack = (lastAckd + 1, true)
in
    (ack, lastAckd + 1)
end""",
            timing=self.network_delay_ms,
            description="Receiver sends acknowledgment",
            position=(400, 350)
        ))
        
        # T6: retrieveFrame
        self.transitions.append(Transition(
            name="retrieveFrame",
            input_places=["PacketBuffer", "BufferMutex", "NextFrameExpected"],
            output_places=["PacketBuffer", "BufferMutex", "NextFrameExpected"],
            guard="mutex = UNLOCKED andalso bufferContains(buffer, nextExpected)",
            action="""let
    val (frames, newBuffer) = extractConsecutiveFrames(buffer, nextExpected)
    val newNext = nextExpected + length(frames)
in
    (newBuffer, UNLOCKED, newNext)
end""",
            description="Retrieve consecutive frames from buffer",
            position=(550, 500)
        ))
        
        # T7: frameDropped (packet loss)
        self.transitions.append(Transition(
            name="frameDropped",
            input_places=["NetworkChannel_Frames"],
            output_places=[],
            guard="true",
            action="(* Frame is dropped - simulates packet loss *)",
            probability=0.05,
            description="Simulate frame loss in network (5% probability)",
            position=(300, 100)
        ))
        
        # T8: ackDropped (ACK loss)
        self.transitions.append(Transition(
            name="ackDropped",
            input_places=["NetworkChannel_ACKs"],
            output_places=[],
            guard="true",
            action="(* ACK is dropped - simulates ACK loss *)",
            probability=0.05,
            description="Simulate ACK loss in network (5% probability)",
            position=(300, 400)
        ))
    
    def _create_arcs(self):
        """Create all arcs connecting places and transitions"""
        
        # sendData arcs
        self.arcs.extend([
            Arc("SenderReady", "sendData", "senderReady"),
            Arc("SendWindow", "sendData", "sendWindow"),
            Arc("NextFrameToSend", "sendData", "nextSeq"),
            Arc("sendData", "NetworkChannel_Frames", f"packet@+{self.network_delay_ms}"),
            Arc("sendData", "SenderTimers", "timers^^[timer]"),
            Arc("sendData", "NextFrameToSend", "nextSeq + 1"),
            Arc("sendData", "SendWindow", "tl(sendWindow)"),
        ])
        
        # receiveACK arcs
        self.arcs.extend([
            Arc("NetworkChannel_ACKs", "receiveACK", "(ack_seq, isPositive)"),
            Arc("LastAckReceived", "receiveACK", "lastAck"),
            Arc("SendWindow", "receiveACK", "sendWindow"),
            Arc("SenderTimers", "receiveACK", "timers"),
            Arc("receiveACK", "LastAckReceived", "newLastAck"),
            Arc("receiveACK", "SendWindow", "newWindow"),
            Arc("receiveACK", "SenderTimers", "newTimers"),
        ])
        
        # handleTimeout arcs
        self.arcs.extend([
            Arc("SenderTimers", "handleTimeout", "timers"),
            Arc("SendWindow", "handleTimeout", "sendWindow"),
            Arc("handleTimeout", "NetworkChannel_Frames", f"packet@+{self.network_delay_ms}"),
            Arc("handleTimeout", "SenderTimers", "newTimers"),
        ])
        
        # receiveFrame arcs
        self.arcs.extend([
            Arc("NetworkChannel_Frames", "receiveFrame", "packet"),
            Arc("RecvWindow", "receiveFrame", "recvWindow"),
            Arc("NextFrameExpected", "receiveFrame", "nextExpected"),
            Arc("BufferMutex", "receiveFrame", "mutex"),
            Arc("receiveFrame", "NetworkChannel_ACKs", f"ack@+{self.network_delay_ms}"),
            Arc("receiveFrame", "NextFrameExpected", "newNext"),
            Arc("receiveFrame", "PacketBuffer", "newBuffer"),
            Arc("receiveFrame", "BufferMutex", "UNLOCKED"),
        ])
        
        # Loss transitions arcs
        self.arcs.extend([
            Arc("NetworkChannel_Frames", "frameDropped", "packet"),
            Arc("NetworkChannel_ACKs", "ackDropped", "ack"),
        ])
    
    def to_cpn_ml(self) -> str:
        """Export model in CPN ML syntax"""
        output = []
        output.append("(* Coloured Petri Net Model *)")
        output.append("(* Sliding Window ARQ - Selective Repeat Protocol *)")
        output.append(f"(* Window Size: {self.window_size} *)")
        output.append(f"(* Timeout: {self.timeout_ms}ms *)")
        output.append(f"(* Network Delay: {self.network_delay_ms}ms ± {self.jitter_ms}ms *)")
        output.append("\n(* COLOR SETS *)")
        output.append("colset INT = int;")
        output.append("colset BOOL = bool;")
        output.append("colset WINDOW = list INT;")
        output.append("colset PACKET = product INT * INT * BOOL timed;")
        output.append("colset ACK = product INT * BOOL timed;")
        output.append("colset BUFFER_ENTRY = product INT * PACKET * BOOL;")
        output.append("colset MUTEX_STATE = with LOCKED | UNLOCKED;")
        output.append("colset TIMER_LIST = list (INT * INT);")
        
        output.append("\n(* PLACES *)")
        for place in self.places:
            output.append(place.to_cpn_ml())
        
        output.append("\n(* TRANSITIONS *)")
        for transition in self.transitions:
            output.append(transition.to_cpn_ml())
        
        return "\n".join(output)
    
    def to_json(self) -> str:
        """Export model as JSON"""
        model_dict = {
            "model_name": "Sliding Window ARQ - Selective Repeat",
            "parameters": {
                "window_size": self.window_size,
                "timeout_ms": self.timeout_ms,
                "network_delay_ms": self.network_delay_ms,
                "jitter_ms": self.jitter_ms
            },
            "places": [p.to_dict() for p in self.places],
            "transitions": [t.to_dict() for t in self.transitions],
            "arcs": [a.to_dict() for a in self.arcs]
        }
        return json.dumps(model_dict, indent=2)
    
    def to_graphviz(self) -> str:
        """Export as Graphviz DOT format for visualization"""
        dot = ["digraph CPN {"]
        dot.append('  rankdir=LR;')
        dot.append('  node [shape=circle];')
        
        # Places
        for place in self.places:
            label = f"{place.name}\\n[{place.color_set.value}]\\n{place.initial_marking}"
            dot.append(f'  "{place.name}" [label="{label}", style=filled, fillcolor=lightblue];')
        
        # Transitions
        dot.append('  node [shape=box];')
        for transition in self.transitions:
            label = transition.name
            if transition.probability:
                label += f"\\n[p={transition.probability}]"
            if transition.timing:
                label += f"\\n[@+{transition.timing}]"
            dot.append(f'  "{transition.name}" [label="{label}", style=filled, fillcolor=lightgreen];')
        
        # Arcs
        for arc in self.arcs:
            label = arc.inscription if arc.inscription != "" else ""
            dot.append(f'  "{arc.source}" -> "{arc.target}" [label="{label}"];')
        
        dot.append("}")
        return "\n".join(dot)
    
    def to_pnml(self) -> str:
        """Export as PNML (Petri Net Markup Language)"""
        pnml = ['<?xml version="1.0" encoding="UTF-8"?>']
        pnml.append('<pnml xmlns="http://www.pnml.org/version-2009/grammar/pnml">')
        pnml.append('  <net id="sliding_window_arq" type="http://www.pnml.org/version-2009/grammar/cpn">')
        pnml.append(f'    <name><text>Sliding Window ARQ Protocol</text></name>')
        
        # Places
        for idx, place in enumerate(self.places):
            x, y = place.position
            pnml.append(f'    <place id="p{idx}">')
            pnml.append(f'      <name><text>{place.name}</text></name>')
            pnml.append(f'      <type><text>{place.color_set.value}</text></type>')
            pnml.append(f'      <initialMarking><text>{place.initial_marking}</text></initialMarking>')
            pnml.append(f'      <graphics><position x="{x}" y="{y}"/></graphics>')
            pnml.append(f'    </place>')
        
        # Transitions
        for idx, trans in enumerate(self.transitions):
            x, y = trans.position
            pnml.append(f'    <transition id="t{idx}">')
            pnml.append(f'      <name><text>{trans.name}</text></name>')
            if trans.guard:
                pnml.append(f'      <condition><text>{trans.guard}</text></condition>')
            pnml.append(f'      <graphics><position x="{x}" y="{y}"/></graphics>')
            pnml.append(f'    </transition>')
        
        # Arcs
        for idx, arc in enumerate(self.arcs):
            # Find place and transition indices
            place_idx = next((i for i, p in enumerate(self.places) if p.name == arc.source or p.name == arc.target), -1)
            trans_idx = next((i for i, t in enumerate(self.transitions) if t.name == arc.source or t.name == arc.target), -1)
            
            if place_idx != -1 and trans_idx != -1:
                pnml.append(f'    <arc id="a{idx}" source="{"p" + str(place_idx) if arc.source in [p.name for p in self.places] else "t" + str(trans_idx)}" target="{"t" + str(trans_idx) if arc.target in [t.name for t in self.transitions] else "p" + str(place_idx)}">')
                pnml.append(f'      <inscription><text>{arc.inscription}</text></inscription>')
                pnml.append(f'    </arc>')
        
        pnml.append('  </net>')
        pnml.append('</pnml>')
        return "\n".join(pnml)


def generate_verification_queries() -> str:
    """Generate verification queries for the model"""
    queries = """
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
"""
    return queries


if __name__ == "__main__":
    # Create the CPN model
    print("Generating CPN Model for Sliding Window ARQ Protocol...")
    model = CPNModel(window_size=10, timeout_ms=100, network_delay_ms=20, jitter_ms=5)
    
    # Export in various formats
    print("\n=== Exporting to CPN ML ===")
    with open("cpn_model.ml", "w") as f:
        f.write(model.to_cpn_ml())
    print("Saved to: cpn_model.ml")
    
    print("\n=== Exporting to JSON ===")
    with open("cpn_model.json", "w") as f:
        f.write(model.to_json())
    print("Saved to: cpn_model.json")
    
    print("\n=== Exporting to Graphviz DOT ===")
    with open("cpn_model.dot", "w") as f:
        f.write(model.to_graphviz())
    print("Saved to: cpn_model.dot")
    
    print("\n=== Exporting to PNML ===")
    with open("cpn_model.pnml", "w") as f:
        f.write(model.to_pnml())
    print("Saved to: cpn_model.pnml")
    
    print("\n=== Generating Verification Queries ===")
    with open("cpn_queries.ml", "w") as f:
        f.write(generate_verification_queries())
    print("Saved to: cpn_queries.ml")
    
    print("\n✓ CPN Model generation complete!")
    print("\nModel Statistics:")
    print(f"  - Places: {len(model.places)}")
    print(f"  - Transitions: {len(model.transitions)}")
    print(f"  - Arcs: {len(model.arcs)}")
    print(f"\nModel Parameters:")
    print(f"  - Window Size: {model.window_size}")
    print(f"  - Timeout: {model.timeout_ms}ms")
    print(f"  - Network Delay: {model.network_delay_ms}ms ± {model.jitter_ms}ms")
