# Architecture & Design Document

This document describes the current code structure and runtime flow. It is intended as an implementation reference for contributors.

## Table of Contents

1. [System Overview](#system-overview)
2. [Layered Architecture](#layered-architecture)
3. [Module Dependencies](#module-dependencies)
4. [Data Models](#data-models)
5. [Message Flow Diagrams](#message-flow-diagrams)
6. [Error Handling](#error-handling)
7. [Scalability Considerations](#scalability-considerations)

---

## System Overview

Convey uses P2P transfer for model exchange and a central WebSocket service for peer discovery.

### Design Principles

| Principle | Implementation | Benefit |
|-----------|---|---|
| **Direct peer transfer** | Direct P2P sync between clients | Data exchange does not depend on the server |
| **Type safety** | Pydantic models for structured data | Invalid input is rejected early |
| **Modularity** | Interface-based design | Merge and verification logic can be replaced |
| **Failure handling** | Fallback message queue | Temporary disconnects do not drop all state |
| **Extensibility** | Strategy pattern for merging | New merge algorithms can be added incrementally |

---

## Layered Architecture

### Layer 1: Application Layer

**Components**: `terminal_app.py`

**Responsibilities**:
- User interface (async CLI menu)
- Menu option handling
- User input/output

**Key Functions**:
```python
trigger_file_menu()          # Main workflow: sync & merge
upload_file_menu()           # Load metadata from file
create_metadata_menu()       # Interactive config builder
update_others_weights_menu() # Broadcast improvements
```

### Layer 2: Configuration Layer

**Components**: `configs/`

**Responsibilities**:
- Loading/saving configurations
- Path normalization
- Configuration validation

**Key Classes**:
- `MetadataConfig`: Type-safe configuration model
- Network constants in `config.py`
- Directory paths in `paths.py`

**Properties**:
- Serializable to JSON
- Used as the main input to networking and model operations
- Hashed for peer topic selection and synchronization

### Layer 3: Business Logic Layer

**Components**: `controllers/`

**Sub-layers**:

#### 3a. ML/Strategy Layer
- Interface definitions (`controllers/ml/interface/`)
- PyTorch implementations (`controllers/ml/pytorch/`)
- Strategy pattern for merging

#### 3b. Verification Layer
- Consensus algorithm (DateVerifier)
- Accuracy testing (TestStaticModel)
- Acceptance or rejection of candidate updates

#### 3c. Networking Layer
- P2P socket communication (port 47987)
- WebSocket subscription (wss://)
- Request-reply messaging
- Connection pooling
- Fallback queue

### Layer 4: Data Model Layer

**Components**: `models/`

**Responsibilities**:
- Define message structures
- Serialization/deserialization
- Type definitions

**Key Models**:
- `ServerMessage`: WebSocket messages
- `P2PMessage`: Direct peer messages
- `FallbackMessages`: Offline queue

### Layer 5: Infrastructure Layer

**Components**: `server/` (Rust)

**Responsibilities**:
- WebSocket coordination
- Topic management
- Peer discovery
- Message routing

---

## Module Dependencies

The dependency graph below shows the main application path starting at `terminal_app.py`.

### Dependency Graph

```
terminal_app.py
    ├── configs.metadata
    │   ├── configs.config
    │   └── configs.paths
    │
    ├── controllers.ml.pytorch.model (TorchModelStatic)
    │   ├── controllers.ml.interface.model
    │   ├── controllers.ml.pytorch.merge
    │   └── torch / torchvision
    │
    ├── controllers.networking.p2p (P2PNode)
    │   ├── controllers.networking.pool
    │   ├── controllers.networking.serializer
    │   ├── models.clients
    │   └── socket / threading
    │
    ├── controllers.networking.ws_client
    │   ├── controllers.networking.threads
    │   ├── models.server
    │   └── websockets / asyncio
    │
    ├── controllers.networking.req_rep (Requester/Replier)
    │   ├── controllers.networking.p2p
    │   ├── controllers.networking.messages
    │   └── models.clients
    │
    └── controllers.verifier.update_verifier
        ├── controllers.ml.pytorch.model
        └── configs.metadata
```

### Import Organization

**Good imports** (following dependency hierarchy):

```python
# Top-level app imports from config
from configs.metadata import MetadataConfig

# Business logic imports from interfaces
from controllers.ml.interface.model import IVerifier

# Networking as needed
from controllers.networking.p2p import p2p_node
```

**Avoid circular imports**:

```python
# Avoid this: p2p.py imports from msg, msg imports from p2p
# from models.clients import P2PMessage
# from controllers.networking.p2p import p2p_node

# Prefer importing through an intermediate layer
# Use string-type annotations if needed

```

---

## Data Models

### Configuration Data Model

```
MetadataConfig (Pydantic v2)
├── avg_count: int
├── merge_strategy: StrategyType ("SLERP" | "GREEDYSOUP" | "SOUP")
├── dataset_path: str (filepath)
├── model_name: str
├── weights_path: str (filepath)
├── model_obj_path: str (filepath, optional)
├── t: float (0.0 <= t <= 1.0)
├── latest_updated: str (ISO datetime)
├── static_model_path: str (filepath)
├── best_score: float (accuracy %)
├── timestamps: List[str] (hash history)
│
└── Methods:
    ├── save() → JSON file
    ├── parse_file(path) → MetadataConfig
    ├── hash_self() → sha256(metadata)
    └── get_model_name() → str
```

### Network Message Models

#### WebSocket Messages
```
ServerMessage
├── msg_type: MessagesTypes
└── message: Union[SubscribeTopic, ChangeSecret]

SubscribeTopic
├── hashed_metadata: str

ClientsIPAddresses
├── hashed_metadata: str
├── ip: str
└── is_adding: bool (join/leave)
```

#### P2P Messages
```
P2PMessage
├── msg_type: P2PMessagesTypes
├── hashed_metadata: str
└── message: Union[
    ├── IsLatest (query)
    ├── ResIsLatest (response)
    ├── SYNC* (request file)
    └── UPDATE (notify)
    ]

FileMessage
├── header: str (10-byte fixed)
├── length: int (4-byte)
└── payload: bytes (variable)
```

#### Offline Messages
```
FallbackMessages
└── {metadata_hash: [StringMsg | FileMsg]}

StringMsg
├── msg: str (JSON)
└── timestamp: datetime

FileMsg
├── file_path: str
├── target_ip: str
└── file_type: FileType
```

### Type Safety

Most structured configuration and messaging data is represented as Pydantic models:

```python
from pydantic import BaseModel, Field, validator

class MetadataConfig(BaseModel):
    t: float = Field(ge=0.0, le=1.0)  # Constraints
    model_name: str = Field(min_length=1)
    
    @field_validator('t')
    def validate_t(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError('t must be 0.0-1.0')
        return v
    
    class Config:
        json_encoders = {
            Path: str,  # Serialize Path to str
            datetime: lambda v: v.isoformat(),
        }
```

---

## Message Flow Diagrams

These diagrams describe the intended runtime flow. They are useful for tracing behavior across modules, but they are not a substitute for the source code.

### Complete Trigger File Flow

```
User Interface
    │
    ├─────────────────────────────────────────────────┐
    │                                                   │
    ▼                                                   ▼
[List Metadata] ──────────────────────── [Validate Paths]
    │                                           │
    │ Load MetadataConfig from JSON            │ Normalize paths
    │                                           │ Move to ~/.convey/
    │                                           │
    └───────────────────────┬───────────────────┘
                            │
                            ▼
                    [Network Phase 1]
                   WebSocket Subscribe
                            │
                ┌───────────┴───────────┐
                │                       │
        Connect to Server    Receive Peer IPs
                │                       │
                │ ◄──────────────────────┘
                │
                ▼
         [Network Phase 2]
        P2P Network Discovery
                │
        ┌──────┴──────┬──────────┬─────────┐
        │             │          │         │
        ▼             ▼          ▼         ▼
    Connect    Connect      ...        Add to
    Peer 1     Peer 2                 pool
        │             │      │         │
        └──────┬───────┴──────┴─────────┘
               │
               ▼
        [Network Phase 3]
    Consensus: Ask Peers
       "Is your model latest?"
               │
        ┌──────┴──────────────┐
        │                     │
        ▼                     ▼
    Replier         DateVerifier
    Responds      Collects Timestamps
    with Date     │
        │         ├─ Find Majority
        │         ├─ Verify Consensus
        │         └─ Return Source IPs
        │
        └──────┬──────────────┘
               │
       ┌──────┴──────┐
       │             │
   Consensus?   No Consensus
       │             │
       Yes           └─ Wait/Retry
       │
       ▼
[Network Phase 4]
   Download Latest
   ├─ Request file from source IP
   ├─ ReceiveFile (P2P)
   └─ Load weights
       │
       ▼
[ML Phase 1]
Load Base Model
       │
       ├─ Load model object
       ├─ Load base weights
       └─ model.load_state_dict()
       │
       ▼
[ML Phase 2]
Merge Strategy
       │
       ├─ Get Merger (SLERP / GreedySoup)
       ├─ merger.merge(new_weights)
       └─ result: merged_state_dict
       │
       ▼
[ML Phase 3]
Test Merged Model
       │
       ├─ Load test dataset (CIFAR-100)
       ├─ Forward pass on all test samples
       ├─ Calculate accuracy
       └─ accuracy_percent
       │
       ▼
[Verification Phase]
Compare with Best Score
       │
    ┌──┴──┐
    │     │
Better?  Worse?
    │     │
    Yes   No
    │     │
    ▼     ▼
  [Save] [Revert]
    │     │
    │     └─ Discard merged
    │
    ▼
[Broadcast Phase]
Update Network
    │
    ├─ Notify peers: "I have update"
    ├─ Store new best_score
    ├─ Update timestamp
    └─ Save metadata.json
```

### DateVerifier Consensus Algorithm

```
Requester Peer                          Multiple Replier Peers
    │                                          │
    ├────────────── IsLatest(hash) ────────────┤
    │                                          │
    │ ◄────── ResIsLatest(timestamp_1) ────────┤
    │                                          │
    │ ◄────── ResIsLatest(timestamp_2) ────────┤
    │                                          │
    │ ◄────── ResIsLatest(timestamp_1) ────────┤
    │                                          │
    │                [Process]                │
    │         Collect: [t1, t2, t1]           │
    │         Mode: t1 (appears 2x)            │
    │         Consensus: 2/3 > 1/2
    │
    ├─── GetWeights from peers with t1 ──────►│
    │
    │ ◄──────── Binary File Transfer ─────────┤
    │
    └─ Merge weights
```

### SLERP Merge Illustration

```
Old Weights (v₀)              New Weights (v₁)
    │                             │
    ├─ Normalize: v₀ ─────────────┤
    │                             │
    │ Calculate angle θ = arccos(v₀·v₁)
    │
    │ For temperature t=0.95:
    │   θₜ = θ × 0.95
    │   s₀ = sin((1-0.95)θ) / sin(θ)
    │   s₁ = sin(0.95θ) / sin(θ)
    │
    │ Merged = s₀·v₀ + s₁·v₁
    │
    └─────────► Result (Weighted Blend)
```

---

## Error Handling

The codebase does not implement a strict shared exception hierarchy everywhere, but the categories below describe the failures the system is expected to handle.

### Exception Hierarchy

```
Exception
├── NetworkException
│   ├── ConnectionRefused (P2P timeout)
│   ├── WebSocketError (Server unreachable)
│   ├── AuthenticationFailed (Secret key mismatch)
│   └── FileTransferFailed (Checksum/timeout)
│
├── ModelException
│   ├── InvalidWeights (Shape mismatch)
│   ├── ModelLoadError (Corrupted .pth)
│   └── InferenceError (GPU OOM)
│
├── VerificationException
│   ├── NoConsensus (Can't agree on latest)
│   ├── AccuracyTestFailed (Evaluation error)
│   └── ScoreDropped (Regression detected)
│
└── ConfigurationException
    ├── InvalidPath (File not found)
    ├── InvalidMetadata (Malformed JSON)
    └── InvalidStrategy (Unknown merge type)
```

### Try-Catch Patterns

**P2P Connection**:
```python
try:
    p2p_node.connect_to_peer(ip)
except ConnectionRefused:
    logger.warning(f"Peer {ip} offline")
    # Fallback: add to retry queue
    fallback_manager.enqueue(message, ip)
```

**Model Loading**:
```python
try:
    model = torch.load(weights_path)
except EOFError:
    logger.error("Corrupted weights file")
    # Fallback: request fresh copy
    requester.sync_model_weights(metadata_hash)
except torch.cuda.OutOfMemoryError:
    logger.warning("GPU OOM, using CPU")
    model = torch.load(weights_path, map_location='cpu')
```

**Accuracy Testing**:
```python
try:
    accuracy = test_model(loader, model)
except ValueError as e:
    if "input size mismatch" in str(e):
        # Weights incompatible with model architecture
        logger.error("Weight/model shape mismatch")
        return False
    raise
```

---

## Scalability Considerations

These are design notes rather than implemented production features.

### Message Queue Depth

**Current**: In-memory dictionary
**Concern**: Large metadata pools exhaust RAM

**Solution for Scale**:
```python
# Use Redis for distributed caching
from redis import Redis

pool = Redis(host='localhost', port=6379)
pool.setex(f"peers:{metadata_hash}", 3600, json.dumps(ips))
```

### Consensus Overhead

**Current**: Query all known peers synchronously
**Concern**: Network latency with many peers

**Optimization**:
```python
# Sample N peers instead of all
sample_size = min(10, total_peers)
sampled_peers = random.sample(all_peers, sample_size)
responses = asyncio.gather(*[query_peer(p) for p in sampled_peers])
```

### File Transfer Throughput

**Current**: Single-threaded 4-byte framed transfer
**Concern**: Slow on large models (1GB+)

**Optimization**:
```python
# Multi-chunk parallel download
chunks = split_file(path, num_chunks=4)
tasks = [download_chunk(c) for c in chunks]
reassemble(asyncio.gather(*tasks))
```

### Storage Growth

**Current**: All peer files stored locally
**Concern**: Disk space limits on edge devices

**Solution**:
```python
# LRU eviction policy
from functools import lru_cache

@lru_cache(maxsize=5)  # Keep 5 latest models
def load_model(path):
    return torch.load(path)
```

### Network Bandwidth

**Optimization Ideas**:
1. **Delta Sync**: Transfer only weight changes
   ```python
   delta = new_weights - old_weights
   sparse_transfer(delta)  # Send only non-zero
   ```

2. **Compression**: ZIP before transfer
   ```python
   with zipfile.ZipFile(compressed) as z:
       z.write(model_path)
   send_framed(binary_data)
   ```

3. **Quantization**: Lower precision for transfer
   ```python
   quantized = (weights * 255).astype(np.uint8)
   # Dequantize on receive
   ```

---

## Thread Safety

### Critical Sections

**Connection Pool** (shared across threads):
```python
connection_pool = {}  # {hash: [IPs]}
_pool_lock = threading.Lock()

def add_peer(hashed_metadata, ip):
    with _pool_lock:
        if hashed_metadata not in connection_pool:
            connection_pool[hashed_metadata] = []
        connection_pool[hashed_metadata].append(ip)
```

**Fallback Message Queue** (written by WebSocket, read by retry thread):
```python
def add_pending_message(msg):
    with _fallback_lock:
        fallback_messages[msg.target].append(msg)

def process_fallback_queue():
    with _fallback_lock:
        pending = fallback_messages.copy()
    
    for target, msgs in pending.items():
        for msg in msgs:
            if deliver(msg):
                with _fallback_lock:
                    fallback_messages[target].remove(msg)
```

---

## Future Improvements

### Phase 2: Optimization
- [ ] Async file transfers (multi-chunk)
- [ ] Weight quantization (reduce bandwidth)
- [ ] CPU/GPU detection and optimization
- [ ] Caching layer (Redis)

### Phase 3: Features
- [ ] Custom dataset loaders
- [ ] Differential updates (delta sync)
- [ ] Encrypted P2P channels
- [ ] Model compression

### Phase 4: Production
- [ ] Kubernetes deployment
- [ ] Prometheus metrics
- [ ] Web dashboard (React)
- [ ] Multi-GPU support
