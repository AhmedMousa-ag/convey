# Convey: Federated Learning System

Convey is a federated learning project for exchanging and merging model state between peers. The Python client handles model operations and peer-to-peer transfer. The Rust server is used for peer discovery over WebSocket.

This README covers setup, the main runtime flow, and the public interfaces exposed by the current codebase. More detailed implementation notes are in `ARCHITECTURE.md`, and example usage is in `API_EXAMPLES.md`.

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Model Merging](#model-merging)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Networking Protocol](#networking-protocol)
- [Verification System](#verification-system)
- [Troubleshooting](#troubleshooting)
- [Development](#development)

---

## Overview

The current implementation supports the following flow:

1. Train models locally
2. Discover peers through the coordination server
3. Exchange weights directly over P2P sockets
4. Merge candidate weights with a configured strategy
5. Evaluate merged weights before accepting an update

Several verification and dataset paths are still specific to PyTorch and CIFAR-100.

### Typical Uses

- Collaborative training across separate machines
- Sharing model weights without sharing raw data
- Comparing and merging independently trained checkpoints
- Experimenting with merge strategies in a distributed setting

### Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Backend Server** | Rust + WebSocket | Centralized coordination & topic subscription |
| **Client** | Python 3.9+ | Terminal UI, networking, ML operations |
| **ML Framework** | PyTorch | Model loading, weight manipulation, testing |
| **Network** | Custom P2P Protocol | Direct peer-to-peer file transfers |
| **Configuration** | Pydantic + JSON | Type-safe configuration management |
| **Serialization** | dill + PyTorch | Complex model serialization |

---

## Key Features

### Federated Architecture
- Direct P2P communication between clients
- WebSocket-based peer discovery
- Fallback queue for disconnected peers

### Advanced Model Merging
- SLERP with a configurable temperature parameter
- GreedySoup-style running average
- Strategy abstraction for additional merge implementations

### Quality Assurance
- Validation-based acceptance checks for merged weights
- Majority-based freshness checks across peers
- Basic tolerance for inconsistent peer responses

### File Management
- Length-prefixed authenticated transfers
- File routing by transfer type
- Directory zipping for transfer when needed

### High Availability
- Fallback behavior when the coordination server is unavailable
- WebSocket reconnect loop
- Retry queue for offline messages

---

## Architecture

### System Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Central WebSocket Server                  │
│          (wss://convey.ahmedkaremmousa.com/ws)               │
│                     Topic Coordination                        │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
    ┌───┴───┐    ┌───┴───┐    ┌──┴────┐
    │Client1│    │Client2│    │Client3│
    └───┬───┘    └───┬───┘    └──┬────┘
        │            │            │
        └─────────────┼────────────┘
           P2P Network (port 47987)
              (Weight & Data Sync)
```

### Component Layers

The codebase is split into configuration, networking, model operations, verification, and the terminal entry point.

#### **1. Configuration Layer** (`configs/`)
- **MetadataConfig**: Central configuration model defining strategy, paths, scores
- **paths.py**: Directory structure under `~/.convey/`
- **config.py**: Network endpoints, timeouts, formats

#### **2. Network Layer** (`controllers/networking/`)
- **P2PNode**: Raw socket-based server (port 47987) with secret-key authentication
- **WebSocket Client**: Subscribes to topics, receives peer lists
- **Request-Reply Pattern**: Requester/Replier for synchronized data exchange
- **Fallback Manager**: Queue for offline messages with retry mechanism

#### **3. ML Layer** (`controllers/ml/`)
- **Strategy Interface**: Abstract merge algorithms (SLERP, GreedySoup)
- **PyTorch Implementation**: Concrete torch-based mergers
- **Model Static Storage**: Serialize full model for verification on other peers

#### **4. Verification Layer** (`controllers/verifier/`)
- **DateVerifier**: Consensus on which peer has latest model
- **TestStaticModel**: Accuracy testing on CIFAR-100 validation set

#### **5. UI Layer** (`terminal_app.py`)
- **Async CLI Menu**: Main user interface for triggering operations
- **Metadata Management**: Create, upload, and manage model configurations

### Data Flow: Trigger File (Main Workflow)

This is the main client path used by the terminal application.

```
User Selects Metadata
        ↓
Validate & Setup Paths (~/.convey/)
        ↓
Connect WebSocket & Subscribe Topic
        ↓
Server Broadcasts Peer IPs
        ↓
P2P Connect to Peers (47987)
        ↓
Query Random Peer: "Is Your Model Latest?"
        ↓
DateVerifier Collects Timestamps
        ↓
Consensus Check (Majority)
        ↓
        ├─→ If Latest: Request weights from majority
        │
        └─→ If Outdated: Download & Merge
                    ↓
            Load Model + Weights
                    ↓
            Apply Merge Strategy (SLERP/Soup)
                    ↓
            Test on CIFAR-100
                    ↓
            Compare with Best Score
                    ↓
        ├─→ If Better: Update & Broadcast
        │
        └─→ If Worse: Revert
```

---

## Installation

### Prerequisites

- Python 3.9 or higher
- PyTorch 1.9+
- 2GB+ free disk space (for models and datasets)
- Network access to `wss://convey.ahmedkaremmousa.com`

### Setup Steps

#### 1. Clone and Navigate
```bash
cd ~/Work/University/convey
```

#### 2. Create Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

#### 3. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**Key Dependencies:**
- `torch` - Neural network framework
- `torchvision` - Vision dataset utilities
- `pydantic` - Data validation
- `websockets` - WebSocket asyncio support
- `dill` - Enhanced pickling for complex objects

#### 4. Verify Installation
```bash
python -c "import torch, torchvision, pydantic; print('Dependencies installed')"
```

#### 5. Directory Setup
The client creates `~/.convey/` on first use:
```
~/.convey/
├── models/              # Full model objects (.pth)
├── weights/             # Model weight state dicts (.pth)
├── datasets/test/       # Test datasets
├── metadata/            # Configuration files (.json)
├── static_modules/      # Serialized models (.dill)
└── zipped_files/        # Temporary file transfers
```

---

## Quick Start

### 1. Launch the Application

```bash
python terminal_app.py
```

### 2. Create Your First Metadata Configuration

**Menu Option: 3 (Create metadata)**

```
Fill in the fields below to create your MetadataConfig instance.
Average Count (integer, default=1): 1
Available Merge Strategies:
1. GREEDYSOUP
2. SLERP
3. SOUP
Select merge strategy (number): 2
Dataset Path (default=./data): ./data
Model Name (default=my_model): cifar_model
Weights Path (default=./saved_models/model_1.pth): ./saved_models/model_1.pth
Static Modules Path (default=...): [auto-generated]
T - Threshold/Temperature (0.0-1.0, default=0.95): 0.95
```

This writes a metadata file to `~/.convey/metadata/cifar_model_slerp.json`.

### 3. Prepare Model Files

Ensure you have:
```
./saved_models/
├── model_1.pth          # Your base model
├── model_2.pth          # Weights to merge
└── weights/
    └── model_*.pth      # Additional weight files
```

### 4. Trigger Model Sync & Merge

**Menu Option: 1 (Trigger file)**

```
Available files:
1. cifar_model_slerp.json
Select metadata file: 1
```

The client will:
1. Connect to WebSocket server
2. Discover peer clients
3. Query them for latest models
4. Download and merge weights
5. Test accuracy
6. Accept if improved

### 5. Monitor Progress

Typical terminal output includes:
- model connection success
- weights loaded
- model accuracy tests
- merge results

---

## Model Merging

### Merge Strategies Overview

#### **SLERP (Spherical Linear Interpolation)**

Use SLERP when you need a weighted interpolation between two compatible checkpoints.

**Algorithm**:
```
For each weight tensor in model:
  1. Normalize old_weights: v₀ = old / ||old||
  2. Normalize new_weights: v₁ = new / ||new||
  
  3. Calculate angle: θ = arccos(v₀ · v₁)
  
  4. Interpolate:
     merged = sin((1-t)θ)/sin(θ) * v₀ + sin(tθ)/sin(θ) * v₁
     
  5. Scale back: merged = merged * ||old||
```

**Temperature Parameter (`t`)**:
- `t = 0.0`: Keep only old weights
- `t = 0.5`: Midpoint between old and new
- `t = 1.0`: Use only new weights
- `t = 0.95`: Default (slightly favor new, smooth interpolation)

**Implementation Details**:

```python
from controllers.ml.pytorch.merge import TorchSLERP

# Initialize with first model
merger = TorchSLERP(
    strategy_name="my_strategy",
    weights=model_1_state_dict,
    t=0.95  # Temperature
)

# Merge new weights
merged_weights = merger.merge(model_2_state_dict)

# Load merged weights into model
model.load_state_dict(merged_weights)
```

**Notes**:
- Requires compatible parameter structure between the two weight sets
- Works best when the incoming model is a continuation of the base model
- Can become unstable when the parameter spaces differ too much

#### **GreedySoup (Stock of Unified Models)**

Use GreedySoup when you want a simple running average over multiple compatible checkpoints.

**Algorithm**:
```
running_sum = {}
count = 1

for each new_weights:
    running_sum = old_weights
    count++
    
merged = running_sum / count
```

**Implementation**:

```python
from controllers.ml.pytorch.merge import TorchGreedySoup

# Create soup
soup = TorchGreedySoup(strategy_name="my_soup")

# Add model weights sequentially
soup.merge(model_1_state_dict)
soup.merge(model_2_state_dict)
soup.merge(model_3_state_dict)

# Retrieve merged result
merged = soup.weights
```

**Notes**:
- Assumes all merged models share the same architecture
- Treats every merged model equally
- Easier to inspect and debug than SLERP

#### **SOUP (Stock of Unified Models - Reference)**

This option is listed in the configuration model but is not fully implemented.

### Complete Merge Example

**File**: `example.py`

```python
from configs.metadata import MetadataConfig
from controllers.ml.pytorch.model import TorchModelStatic
import torch

# 1. Create metadata
metadata = MetadataConfig(
    avg_count=1,
    merge_strategy="SLERP",
    model_name="cifar_classifier",
    t=0.95,
    weights_path="./saved_models/model_1.pth",
    dataset_path="./data",
    static_model_path="./static_modules/model.dill"
)

# 2. Initialize and load base model
model = TorchModelStatic(metadata)
model.load_model_obj()  # Load PyTorch model
model.test_model(test_loader, model_obj)  # Test accuracy

# 3. Apply merge with new weights
new_weights = torch.load("./saved_models/model_2.pth")
merged_weights = model.merge(new_weights)

# 4. Verify improvement
test_accuracy = model.test_model(test_loader, merged_model)
is_improved = test_accuracy > metadata.best_score

# 5. Save if improved
if is_improved:
    torch.save(merged_weights, "saved_models/merged.pth")
    metadata.best_score = test_accuracy
    metadata.save()
```

### Performance Tuning

The main tuning parameter currently exposed in the metadata is `t` for SLERP.

**Temperature Adjustment (`t` parameter)**:

| Value | Effect | Use Case |
|-------|--------|----------|
| 0.5 - 0.7 | More conservative | Preserve base model quality |
| 0.8 - 0.9 | Moderate blend | Balanced integration |
| 0.95 - 1.0 | Aggressive updates | Favor new improvements |

**Merge Strategy Selection**:

```python
# If adding small incremental updates → SLERP (t=0.95)
# If averaging 3+ diverse models → GreedySoup
# If ensemble needs equal weight → SOUP (future)
```

---

## Configuration

### MetadataConfig Overview

**Location**: `configs/metadata.py`

This model is the main configuration contract shared across training, transfer, and verification.

**Fields**:

```python
class MetadataConfig(BaseModel):
    avg_count: int                      # Merge iterations
    merge_strategy: StrategyType        # "SLERP", "GREEDYSOUP", "SOUP"
    dataset_path: str                   # Path to test dataset
    model_name: str                     # Human-readable name
    weights_path: str                   # Path to base weights
    model_obj_path: str = ""            # Optional: full model .pth
    t: float                            # Temperature for SLERP [0.0, 1.0]
    latest_updated: str = ""            # Last update timestamp
    static_model_path: str              # Path to serialized model .dill
    best_score: float = 0.0             # Best accuracy achieved
    timestamps: List[str] = []          # Hash history for consensus
```

### JSON Metadata File Format

**File**: `~/.convey/metadata/cifar_model_slerp.json`

```json
{
  "avg_count": 1,
  "merge_strategy": "SLERP",
  "dataset_path": "/home/user/data",
  "model_name": "cifar_model",
  "weights_path": "/home/user/saved_models/model_1.pth",
  "model_obj_path": "",
  "t": 0.95,
  "latest_updated": "2026-03-17 10:30:45-123456",
  "static_model_path": "~/.convey/static_modules/cifar_model_slerp.dill",
  "best_score": 78.5,
  "timestamps": [
    "2026-03-17 10:30:45-123456",
    "2026-03-17 11:15:30-654321"
  ]
}
```

### Network Configuration

**File**: `configs/config.py`

These constants control server endpoints, local bind settings, and retry intervals.

```python
# Server Endpoints
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 3000
SERVER_URL = "wss://convey.ahmedkaremmousa.com/ws"

# Client Settings
CLIENT_HOST = "0.0.0.0"
CLIENT_PORT = 47987                    # P2P listening port

# Timeouts
WS_CONNECTION_WAIT = 15                # WebSocket reconnect interval
FALLBACK_RETRY_INTERVAL = 60           # Offline message retry

# Format
CONVERY_FILE_EXT = ".json"
DATEIME_FORMAT = "%Y-%m-%H %M-%S-%f"
```

### Environment Configuration

**File**: `environment.yml` (for Conda users)

```yaml
name: convey
channels:
  - pytorch
  - defaults
dependencies:
  - python=3.9
  - pytorch::pytorch
  - pytorch::torchvision
  - pytorch::pytorch-cuda=11.8
  - pip
  - pip:
    - websockets>=12.0
    - pydantic>=2.0
    - dill>=0.3.7
```

**Install**:
```bash
conda env create -f environment.yml
conda activate convey
```

---

## API Reference

### Terminal Application (`terminal_app.py`)

The terminal application is the primary entry point for local use.

#### Main Menu Functions

**`trigger_file_menu()`**
- Purpose: load metadata, connect to peers, and run the sync-and-merge flow
- Menu Option: 1

**`upload_file_menu()`**
- Purpose: import metadata from an existing JSON file
- Menu Option: 2

**`create_metadata_menu()`**
- Purpose: create metadata interactively
- Menu Option: 3

**`update_others_weights_menu()`**
- Purpose: broadcast an updated model to peers
- Menu Option: 4

### Metadata Configuration (`configs/metadata.py`)

```python
# Load from file
metadata = MetadataConfig.parse_file("path/to/config.json")

# Create programmatically
metadata = MetadataConfig(
    avg_count=1,
    merge_strategy="SLERP",
    model_name="my_model",
    weights_path="./model.pth",
    t=0.95,
    dataset_path="./data",
    static_model_path="./static.dill"
)

# Save to file
metadata.save()

# Hash for network operations
hashed = metadata.hash_self()

# Get model name
name = metadata.get_model_name()
```

### ML Layer (`controllers/ml/`)

#### Pure Interface Classes

**`IModelStatic`** (Abstract Base)
```python
load_model_obj() → Module              # Load PyTorch model
load_weights(path) → Dict              # Load state_dict
save_weights(path, weights) → None     # Save state_dict
```

**`IVerifier`** (Abstract Base)
```python
load_data(path) → DataLoader           # Load test dataset
test_model(loader, model) → float      # Return accuracy %
is_better_score(weights_path) → bool   # Compare with best_score
```

**`IMergerManager`** (Abstract Base)
```python
get_merger(strategy) → IStrategy       # Factory for strategies
```

#### PyTorch Implementation

**`TorchModelStatic`** (Implements IModelStatic + IVerifier)

```python
model = TorchModelStatic(metadata)

# Load/Save
model_obj = model.load_model_obj()
weights = model.load_weights("path.pth")
model.save_weights("path.pth", weights)

# Test
accuracy = model.test_model(test_loader, model_obj)

# Serialize for network
model.save_model_static()  # → .dill file
loaded = IStateVerifierModel.load_model_static("path.dill")
```

**`TorchSLERP`** (Spherical Linear Interpolation)

```python
slerp = TorchSLERP(
    strategy_name="slerp_strategy",
    weights=base_weights,
    t=0.95
)

# Merge new weights
merged = slerp.merge(new_weights)
```

**`TorchGreedySoup`** (Running Average)

```python
soup = TorchGreedySoup(strategy_name="soup_strategy")

# Sequentially add weights
soup.merge(model_1.state_dict())
soup.merge(model_2.state_dict())
soup.merge(model_3.state_dict())

# Get result
result = soup.weights
```

**`TorchMergerManager`** (Strategy Factory)

```python
manager = TorchMergerManager(metadata)

# Get appropriate merger
merger = manager.get_merger()  # Returns based on metadata.merge_strategy
```

### Networking (`controllers/networking/`)

#### P2P Node

**`P2PNode`** (Singleton Socket Server)

```python
from controllers.networking.p2p import p2p_node

# Start server (runs in thread)
p2p_node.start_server()

# Connect to peer
p2p_node.connect_to_peer(ip_address)

# Raw framed send/receive (internal)
p2p_node.send_framed(data)
data = p2p_node.recv_framed()
```

#### Request-Reply Pattern

**`Requester`** (Client requesting data from peers)

```python
from controllers.networking.req_rep import Requester

requester = Requester(metadata, p2p_node)

# Query freshness
requester.ask_is_latest(hashed_metadata, current_date)

# Request files
requester.sync_model_weights(hashed_metadata)
requester.sync_dataset(hashed_metadata)
requester.sync_static_modules(hashed_metadata)
requester.ask_sync_model()

# Broadcast update
requester.update_new_weights()
```

**`Replier`** (Server responding to peer requests)

```python
from controllers.networking.req_rep import Replier

replier = Replier(metadata, p2p_node)

# Response handlers
replier.reply_is_latest(message)
replier.reply_sync_model(peer_address)
replier.reply_sync_model_weights(peer_address)
```

#### WebSocket Client

```python
from controllers.networking.ws_client import server_ws_client

# Runs in async thread
asyncio.create_task(server_ws_client())
```

#### Message Serialization

**Message Types** (`models/clients.py`):

| Type | Used For |
|------|----------|
| `IsLatest` | Query peer model freshness |
| `ResIsLatest` | Respond with timestamp |
| `SYNCModel` | Request full model |
| `SYNCModelWeights` | Request weights only |
| `SYNCDataset` | Request test dataset |
| `SYNCStaticModules` | Request serialized model |
| `UPDATE` | Broadcast improvements |

### Verification (`controllers/verifier/`)

**`DateVerifier`** (Consensus)

```python
from controllers.verifier.update_verifier import DateVerifier

verifier = DateVerifier()

# Check consensus on latest model
is_latest, source_ips = verifier.verify_latest_model(
    hashed_metadata,
    target_date,
    peer_address
)
```

**`ModelVerifier`** (Accuracy Check)

```python
from controllers.verifier.update_verifier import ModelVerifier

verifier = ModelVerifier(metadata)

# Check if new weights are better
is_better = verifier.is_better_model("path/to/new_weights.pth")
```

---

## Networking Protocol

The client uses two communication paths: WebSocket for peer discovery and raw socket connections for direct message and file exchange.

### P2P Wire Protocol

#### Frame Format

```
[4 bytes]         [variable]        [4 bytes]      [variable]
┌─────────────┬────────────────┬──────────────┬────────────────┐
│   LENGTH    │   PAYLOAD      │   LENGTH     │    PAYLOAD     │
│ (big-endian)│ (secret_key)   │ (big-endian) │  (message)     │
└─────────────┴────────────────┴──────────────┴────────────────┘
         4B           32B               4B          variable
```

**Authentication Handshake**:

```
Client                          Server (P2PNode)
  │                               │
  ├─── connect()─────────────────→│
  │                               │
  ├─ send_framed(secret_key)─────→│
  │                               │
  │ ←────── recv_framed()──────────┤ (verify key)
  │                               │
  │←────── Connection accepted─────│
  │                               │
  └──── send_framed(message)─────→│
```

#### Message Types (10-byte fixed header)

```
"MODEL     "  ← Full .pth file
"WEIGHTS   "  ← State dict only
"DATA      "  ← Dataset files
"STATIC_MOD"  ← Serialized .dill
"TEXT      "  ← JSON messages
```

### WebSocket Protocol

**Connection**:
```
wss://convey.ahmedkaremmousa.com/ws
```

**Message Types**:

1. **SUBSCRIBE** (Client → Server)
   ```json
   {
     "msg_type": "SUBSCRIBE",
     "message": {
       "hashed_metadata": "abc123def456..."
     }
   }
   ```

2. **ClientsIPAddresses** (Server → All Subscribers)
   ```json
   {
     "hashed_metadata": "abc123def456...",
     "ip": "192.168.1.100",
     "is_adding": true
   }
   ```

3. **ChangeSecret** (Server → Client)
   ```json
   {
     "msg_type": "ChangeSecret",
     "message": {
       "new_secret": "new_key_hash"
     }
   }
   ```

### Fallback Messaging

**Storage**: `~/.convey/.fallback_messages.json`

```json
{
  "metadata_hash_1": [
    {
      "message_type": "IsLatest",
      "target_ip": "192.168.1.1",
      "payload": {...}
    }
  ]
}
```

**Retry Logic**:
- Check every 60 seconds
- Attempt delivery to peers
- Remove on success
- Cap retry count to prevent infinite loops

---

## Verification System

### DateVerifier (Consensus Protocol)

Purpose: determine which peers appear to have the latest model version.

**Algorithm**:

```python
def verify_latest_model(metadata_hash, target_date, peer_addr):
    """
    Consensus-based freshness verification.
    
    Asks all known peers: "What's your last update time?"
    Collects responses and finds majority agreement.
    """
    
    # 1. Query all peers asynchronously
    responses = query_all_peers(metadata_hash, timeout=5)
    
    # 2. Extract timestamps from responses
    timestamps = [resp.timestamp for resp in responses]
    
    # 3. Find most common timestamp (majority)
    majority_timestamp = mode(timestamps)
    count_with_majority = timestamps.count(majority_timestamp)
    
    # 4. Consensus check
    if count_with_majority > len(responses) / 2:
        # Majority has this version
        source_ips = [resp.ip for resp in responses
                      if resp.timestamp == majority_timestamp]
        return True, source_ips  # Signal to sync
    else:
        # No consensus yet, wait
        return False, []
```

**Notes**:
- Requires > N/2 agreement
- Survives up to (N-1)/2 faulty nodes
- Example: 5 peers → requires 3+ agreement → tolerates 1 fault

### TestStaticModel (Accuracy Verification)

Purpose: accept a merge only when the candidate weights improve the tracked score.

**Implementation**:

```python
class TestStaticModel(IVerifier):
    """Verifies model improvements before accepting updates."""
    
    def is_better_score(self, new_weights_path: str) -> bool:
        """Test if new weights are better than current best."""
        
        # 1. Load new weights
        new_weights = self.load_weights(new_weights_path)
        
        # 2. Load model architecture
        model = self.load_model_obj()
        model.load_state_dict(new_weights)
        model.to(device)
        
        # 3. Load test dataset
        test_loader = self.load_data(self.metadata.dataset_path)
        
        # 4. Evaluate
        test_accuracy = self.test_model(test_loader, model)
        
        # 5. Compare with best known accuracy
        is_improved = test_accuracy > self.metadata.best_score
        
        if is_improved:
            self.metadata.best_score = test_accuracy
            
        return is_improved
```

**Dataset Format**:
- CIFAR-100 (currently hardcoded)
- Custom loaders can be added via subclassing

**Testing Flow**:

```
New Weights Received
         │
         ├─→ Load state_dict
         │
         ├─→ Load PyTorch model
         │
         ├─→ Load CIFAR-100 test set (10,000 images)
         │
         ├─→ Forward pass on all test images
         │
         ├─→ Calculate accuracy (correct / total)
         │
         ├─→ Compare with metadata.best_score
         │
         └─→ Accept if improved, Reject otherwise
```

---

## Troubleshooting

### Common Issues

This section lists common setup and runtime failures in the current implementation.

#### **"Connection refused: Cannot connect to WebSocket server"**

**Causes**:
- Server `wss://convey.ahmedkaremmousa.com` is down
- No internet connectivity
- Firewall blocking WebSocket

**Solutions**:
1. Check server status
2. Verify internet connection
3. Check firewall rules: `sudo ufw allow 443`
4. System falls back to P2P-only mode automatically

#### **"P2P Connection timeout: Port 47987 unreachable"**

**Causes**:
- Port 47987 blocked by firewall
- Peer offline
- Wrong IP address

**Solutions**:
1. Open port: `sudo ufw allow 47987`
2. Check peer online status
3. Verify IP from WebSocket peer list

#### **"FileNotFoundError: Model weights not found"**

**Causes**:
- Path not normalized correctly
- File moved after configuration

**Solutions**:
```python
from controllers.path_utils import normalize_path

# Normalize paths before saving
metadata.weights_path = normalize_path(metadata.weights_path)
metadata.save()s
```

#### **"Accuracy dropped after merge"**

**Causes**:
- Temperature `t` too high (over-weighted new model)
- Incompatible weight shapes
- Bad training on new model

**Solutions**:
1. Lower temperature: `t=0.7` (more conservative)
2. Verify model architecture compatibility
3. Pre-merge validation with debug info

```python
# Debug merge
slerp = TorchSLERP("debug", weights=old_w, t=0.95)
merged = slerp.merge(new_w)

# Test before committing
test_acc_before = test_model(loader, model_old)
test_acc_after = test_model(loader, model_merged)
print(f"Before: {test_acc_before}%, After: {test_acc_after}%")

if test_acc_after > test_acc_before:
    metadata.save()  # Commit
```

#### **"Secret key mismatch" - P2P Authentication Failed**

**Causes**:
- Metadata hashes don't match between peers
- Configuration modified after sync started

**Solutions**:
1. Restart application
2. Verify metadata JSON hasn't changed
3. Check network clock sync (NTP)

#### **"Dataset not downloaded automatically"**

**Causes**:
- CIFAR-100 download failed
- Disk space insufficient
- Network timeout during download

**Solutions**:
```bash
# Pre-download CIFAR-100
python -c "
import torchvision.datasets as datasets
datasets.CIFAR100(root='./data', train=False, download=True)
"
```

### Debug Mode

**Enable verbose logging**:

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('convey')
logger.setLevel(logging.DEBUG)
```

**Check fallback messages**:
```bash
cat ~/.convey/.fallback_messages.json | python -m json.tool
```

**Monitor P2P connections**:
```python
from controllers.networking.pool import (
    connection_pool,
    p2p_socket_peer_conn
)

print("Peers:", connection_pool)
print("Sockets:", p2p_socket_peer_conn)
```

---

## Development

### Project Structure

```
convey/
├── configs/                    # Configuration management
│   ├── config.py              # Network & deployment constants
│   ├── metadata.py            # MetadataConfig model
│   └── paths.py               # Directory structure
│
├── controllers/               # Core business logic
│   ├── path_utils.py          # Path normalization
│   ├── ml/                    # Machine learning
│   │   ├── interface/         # Abstract interfaces
│   │   │   ├── merge.py       # Merge strategies
│   │   │   └── model.py       # Model/verifier interfaces
│   │   └── pytorch/           # PyTorch implementations
│   │       ├── merge.py       # SLERP/Soup mergers
│   │       └── model.py       # Model loader/verifier
│   │
│   ├── networking/            # P2P & WebSocket
│   │   ├── p2p.py             # Raw socket server (47987)
│   │   ├── ws_client.py       # WebSocket subscriber
│   │   ├── req_rep.py         # Request-reply pattern
│   │   ├── pool.py            # Connection management
│   │   ├── serializer.py      # Message serialization
│   │   ├── messages.py        # Message models
│   │   ├── messages_fallback.py  # Offline queue
│   │   └── threads.py         # Thread management
│   │
│   ├── operations/            # Future: operation utilities
│   └── verifier/              # Verification system
│       └── update_verifier.py # Consensus & accuracy check
│
├── models/                    # Data models
│   ├── server.py              # Server message models
│   ├── clients.py             # P2P message models
│   └── fallback.py            # Offline message models
│
├── views/                     # Future: web UI
│
├── data/                      # Datasets (CIFAR-100)
├── saved_models/              # Trained models & weights
│
├── terminal_app.py            # Main CLI entry point
├── example.py                 # Complete merge example
├── draft.py                   # Experimental code
│
├── requirements.txt           # Python dependencies
├── environment.yml            # Conda environment
├── Dockerfile.test            # Test container
├── docker-compose.yml         # Docker stack definition
│
└── server/                    # Rust backend
    ├── Cargo.toml
    ├── src/
    │   ├── main.rs            # Server entry point
    │   ├── lib.rs
    │   ├── configs/           # Server configuration
    │   ├── controller/        # Request handlers
    │   └── models/            # Rust data models
    └── docker-compose-dev.yml
```

### Running Tests

**Unit Tests**:

```bash
# Pending: implement test suite
pytest tests/ -v
```

**Manual Integration Test**:

```python
# File: test_integration.py
from configs.metadata import MetadataConfig
from controllers.ml.pytorch.model import TorchModelStatic

metadata = MetadataConfig.parse_file("~/.convey/metadata/test.json")
model = TorchModelStatic(metadata)

# Load and test
model_obj = model.load_model_obj()
weights = model.load_weights(metadata.weights_path)
model_obj.load_state_dict(weights)

# Training/testing operations
print("Integration test passed")
```

### Building Docker Image

**Development (Hot-reload)**:
```bash
docker-compose -f server/docker-compose-dev.yml up --build
```

**Production (Slim)**:
```bash
docker-compose up --build -d
```

### Adding Custom Merge Strategies

To add a strategy, update the interface, the PyTorch implementation, and the strategy selection logic.

1. **Implement interface**:
```python
# File: controllers/ml/interface/merge.py
class ICustomMerge(IStrategy):
    def merge(self, new_weights: Dict) -> Dict:
        """Implement your strategy here."""
        pass
```

2. **Implement PyTorch version**:
```python
# File: controllers/ml/pytorch/merge.py
class TorchCustom(ICustomMerge):
    def __init__(self, strategy_name: str, weights: Dict, **kwargs):
        self.weights = weights
        # Custom init
    
    def merge(self, new_weights: Dict) -> Dict:
        # Your implementation
        return merged
```

3. **Register in MetadataConfig**:
```python
# File: configs/metadata.py
class StrategyType(str, Enum):
    GREEDYSOUP = "GREEDYSOUP"
    SLERP = "SLERP"
    SOUP = "SOUP"
    CUSTOM = "CUSTOM"  # Add here
```

4. **Add factory method**:
```python
# File: controllers/ml/pytorch/model.py
if metadata.merge_strategy == "CUSTOM":
    return TorchCustom(...)
```

---

## Additional Resources

### Key Papers

- **SLERP**: "Smoothly Interpolating Neural Networks" conceptually similar to [linear interpolation in latent spaces](https://arxiv.org/abs/1912.04951)
- **Model Soups**: [Model soups: averaging weights of multiple fine-tuned models improves accuracy without increasing inference time](https://arxiv.org/abs/2003.09888)
- **Federated Learning**: [Communication-Efficient Learning of Deep Networks from Decentralized Data](https://arxiv.org/abs/1602.05629)



---

## License

University of The People Capstone Project.

