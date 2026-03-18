# Code Examples & API Reference

This document collects usage snippets for the current Python client. The examples are references and may need small adjustments to match local paths, model classes, and runtime state.

## Table of Contents

1. [Configuration Management](#configuration-management)
2. [Model Merging](#model-merging)
3. [Testing & Verification](#testing--verification)
4. [Networking](#networking)
5. [Advanced Usage](#advanced-usage)

---

## Configuration Management

These examples focus on creating, loading, and validating `MetadataConfig` instances.

### Create Metadata Programmatically

```python
from configs.metadata import MetadataConfig
from configs.paths import METADATA_PATH
import os
from datetime import datetime
from configs.config import DATEIME_FORMAT

# Create configuration
metadata = MetadataConfig(
    avg_count=1,
    merge_strategy="SLERP",
    dataset_path="/home/user/data",
    model_name="cifar_classifier",
    weights_path="/home/user/saved_models/model_1.pth",
    model_obj_path="/home/user/saved_models/model.pth",
    t=0.95,
    latest_updated=datetime.now().strftime(DATEIME_FORMAT),
    static_model_path=os.path.join(METADATA_PATH, "cifar_classifier_slerp.dill"),
    best_score=0.0
)

# Save to disk
metadata.save()
print(f"Saved to: {METADATA_PATH}/{metadata.model_name}_{metadata.merge_strategy.lower()}.json")
```

### Load Metadata from File

```python
from configs.metadata import MetadataConfig
from configs.paths import METADATA_PATH
import os

# Load from file
file_path = os.path.join(METADATA_PATH, "my_model_slerp.json")
metadata = MetadataConfig.parse_file(file_path)

# Access fields
print(f"Model: {metadata.model_name}")
print(f"Strategy: {metadata.merge_strategy}")
print(f"Best Score: {metadata.best_score}")
print(f"Weights Path: {metadata.weights_path}")
```

### Update Metadata After Training

```python
from configs.metadata import MetadataConfig
import os

# Load existing
metadata = MetadataConfig.parse_file("~/.convey/metadata/model.json")

# Update scores after testing
metadata.best_score = 82.5
metadata.latest_updated = "2026-03-17 15:30:00-123456"

# Add to history
metadata.timestamps.append(metadata.latest_updated)

# Save back
metadata.save()
```

### Validate Configuration

```python
from configs.metadata import MetadataConfig
from pydantic import ValidationError
import json

try:
    # This will raise ValidationError for invalid input
    metadata = MetadataConfig(
        avg_count=1,
        merge_strategy="INVALID_STRATEGY",  # Invalid value
        model_name="test",
        weights_path="./weights.pth",
        dataset_path="./data",
        t=1.5  # Out of range [0.0, 1.0]
    )
except ValidationError as e:
    print(f"Validation failed: {e}")
    # Print all errors
    for error in e.errors():
        print(f"  - {error['loc']}: {error['msg']}")
```

---

## Model Merging

These examples assume compatible PyTorch checkpoints and a working local dataset path.

### SLERP Merge Example

```python
import torch
from controllers.ml.pytorch.merge import TorchSLERP

# Load base and new weights
base_weights = torch.load("saved_models/model_1.pth")
new_weights = torch.load("saved_models/model_2.pth")

# Create SLERP merger with temperature
slerp = TorchSLERP(
    strategy_name="my_slerp",
    weights=base_weights,
    t=0.95  # Temperature: 0.95 means ~95% new, 5% old
)

# Merge
merged_weights = slerp.merge(new_weights)

# Save result
torch.save(merged_weights, "saved_models/merged_model.pth")
print(f"Merged weights saved. Shape: {merged_weights['layer1.weight'].shape}")
```

### GreedySoup (Running Average)

```python
import torch
from controllers.ml.pytorch.merge import TorchGreedySoup

# Create soup
soup = TorchGreedySoup(strategy_name="model_ensemble")

# Load multiple models
model_1 = torch.load("saved_models/model_1.pth")
model_2 = torch.load("saved_models/model_2.pth")
model_3 = torch.load("saved_models/model_3.pth")

# Add to soup (each merge averages)
soup.merge(model_1)    # avg = model_1
soup.merge(model_2)    # avg = (model_1 + model_2) / 2
soup.merge(model_3)    # avg = (model_1 + model_2 + model_3) / 3

# Get ensemble weights
final_weights = soup.weights
torch.save(final_weights, "saved_models/ensemble.pth")
```

### Complete Merge Workflow

This example shows the full local merge-and-verify path without the networking layer.

```python
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
import torchvision
import torchvision.transforms as transforms
from configs.metadata import MetadataConfig
from controllers.ml.pytorch.model import TorchModelStatic
import os

# Setup device
device = "cuda" if torch.cuda.is_available() else "cpu"

# 1. Load configuration
metadata = MetadataConfig.parse_file(
    os.path.expanduser("~/.convey/metadata/model.json")
)

# 2. Initialize model handler
model_handler = TorchModelStatic(metadata)

# 3. Load base model and weights
print("Loading base model...")
base_model = model_handler.load_model_obj()
base_weights = model_handler.load_weights(metadata.weights_path)
base_model.load_state_dict(base_weights)
base_model.to(device)

# 4. Load new weights to merge
print("Loading new weights...")
new_weights_path = "saved_models/model_2.pth"
new_weights = model_handler.load_weights(new_weights_path)

# 5. Apply merge strategy
print(f"Merging with {metadata.merge_strategy} (t={metadata.t})...")
from controllers.ml.pytorch.merge import TorchSLERP
merger = TorchSLERP(
    strategy_name=f"{metadata.model_name}_slerp",
    weights=base_weights,
    t=metadata.t
)
merged_weights = merger.merge(new_weights)

# 6. Create merged model
merged_model = model_handler.load_model_obj()
merged_model.load_state_dict(merged_weights)
merged_model.to(device)

# 7. Load test dataset
print("Loading test dataset...")
transform_test = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize(
        mean=(0.5071, 0.4867, 0.4408),
        std=(0.2675, 0.2565, 0.2761)
    ),
])
testset = torchvision.datasets.CIFAR100(
    root=metadata.dataset_path,
    train=False,
    download=True,
    transform=transform_test
)
testloader = DataLoader(testset, batch_size=128, shuffle=False, num_workers=4)

# 8. Test accuracy
print("Testing merged model...")
merged_model.eval()
correct = 0
total = 0

with torch.no_grad():
    for data, target in testloader:
        data, target = data.to(device), target.to(device)
        outputs = merged_model(data)
        _, predicted = torch.max(outputs.data, 1)
        total += target.size(0)
        correct += (predicted == target).sum().item()

new_accuracy = (correct / total) * 100
print(f"Merged Model Accuracy: {new_accuracy:.2f}%")
print(f"Previous Best: {metadata.best_score:.2f}%")

# 9. Verify improvement
is_improved = new_accuracy > metadata.best_score

if is_improved:
    print("Model improved. Saving...")
    
    # Save weights
    torch.save(merged_weights, "saved_models/merged.pth")
    
    # Update metadata
    metadata.best_score = new_accuracy
    from datetime import datetime
    from configs.config import DATEIME_FORMAT
    metadata.latest_updated = datetime.now().strftime(DATEIME_FORMAT)
    metadata.save()
    
    print("Metadata updated")
else:
    print("No improvement. Keeping original weights.")
```

### Custom Merge Strategy

```python
# File: controllers/ml/interface/merge.py
from abc import ABC, abstractmethod
from typing import Dict

class IStrategy(ABC):
    """Base class for all merge strategies."""
    
    @abstractmethod
    def merge(self, new_weights: Dict) -> Dict:
        """Merge new weights with base weights."""
        pass

class ICustomWeightedAverage(IStrategy):
    """Weighted average with dynamic weights."""
    
    def __init__(self, base_weights: Dict, w1: float = 0.6, w2: float = 0.4):
        self.base_weights = base_weights
        self.w1 = w1  # Weight for base
        self.w2 = w2  # Weight for new
    
    def merge(self, new_weights: Dict) -> Dict:
        merged = {}
        for key, base_val in self.base_weights.items():
            if key in new_weights:
                new_val = new_weights[key]
                # Weighted combination
                merged[key] = self.w1 * base_val + self.w2 * new_val
            else:
                merged[key] = base_val
        return merged

# File: controllers/ml/pytorch/merge.py
import torch
from controllers.ml.interface.merge import ICustomWeightedAverage

class TorchWeightedAverage(ICustomWeightedAverage):
    """PyTorch implementation of weighted averaging."""
    pass

# Usage:
weighted = TorchWeightedAverage(base_weights, w1=0.7, w2=0.3)
merged = weighted.merge(new_weights)
```

---

## Testing & Verification

These examples cover direct evaluation of checkpoints and the static-model verification path.

### Test Model Accuracy

```python
import torch
import torchvision
import torchvision.transforms as transforms
from torch.utils.data import DataLoader

# Load model
model = torch.load("saved_models/model.pth")
device = "cuda" if torch.cuda.is_available() else "cpu"
model.to(device)
model.eval()

# Load dataset
transform = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize((0.5071, 0.4867, 0.4408), (0.2675, 0.2565, 0.2761))
])

testset = torchvision.datasets.CIFAR100(
    root="./data",
    train=False,
    download=True,
    transform=transform
)
testloader = DataLoader(testset, batch_size=128, shuffle=False)

# Evaluate
correct = 0
total = 0

with torch.no_grad():
    for inputs, labels in testloader:
        inputs, labels = inputs.to(device), labels.to(device)
        outputs = model(inputs)
        _, predicted = torch.max(outputs.data, 1)
        total += labels.size(0)
        correct += (predicted == labels).sum().item()

accuracy = 100 * correct / total
print(f"Accuracy: {accuracy:.2f}%")
```

### Verify Using StaticModel

```python
from configs.metadata import MetadataConfig
from controllers.ml.interface.model import IStateVerifierModel
import os

# Load metadata
metadata = MetadataConfig.parse_file("~/.convey/metadata/model.json")

# Load serialized model (created by save_model_static())
verifier = IStateVerifierModel.load_model_static(
    metadata.static_model_path
)

# Test new weights
is_better = verifier.is_better_score("saved_models/new_weights.pth")

if is_better:
    print("New weights improved accuracy")
else:
    print("New weights did not improve")
```

### Serialize Model for Network Distribution

```python
from configs.metadata import MetadataConfig
from controllers.ml.pytorch.model import TorchModelStatic

# Load metadata
metadata = MetadataConfig.parse_file("~/.convey/metadata/model.json")

# Create handler
handler = TorchModelStatic(metadata)

# Serialize (creates .dill file)
handler.save_model_static()
print(f"Saved static model to: {metadata.static_model_path}")

# Remote peers can load it
from controllers.ml.interface.model import IStateVerifierModel
remote_verifier = IStateVerifierModel.load_model_static(
    metadata.static_model_path
)

# And use for verification
is_good = remote_verifier.is_better_score("weights.pth")
```

---

## Networking

These snippets show the lower-level networking APIs used by the terminal workflow.

### Manual Peer Connection

Use this only for debugging or direct experimentation. The normal entry point is the terminal menu.

```python
from controllers.networking.p2p import p2p_node
from controllers.networking.messages import P2PMessage
from models.clients import P2PMessagesTypes
import json

# Start P2P server
p2p_node.start_server()  # Runs in thread

# Connect to peer
peer_ip = "192.168.1.100"
p2p_node.connect_to_peer(peer_ip)

# Create and send message
msg = P2PMessage(
    msg_type=P2PMessagesTypes.IsLatest,
    hashed_metadata="abc123",
    message={"query": "latest"}
)

p2p_node.send_framed(json.dumps(msg.dict()).encode())

# Receive response
response = p2p_node.recv_framed()
print(f"Peer responded: {response}")
```

### Request-Reply Pattern

```python
from controllers.networking.req_rep import Requester, Replier
from controllers.networking.p2p import p2p_node
from configs.metadata import MetadataConfig
import os

# Load metadata
metadata = MetadataConfig.parse_file(
    os.path.expanduser("~/.convey/metadata/model.json")
)

# Initialize requester
requester = Requester(metadata, p2p_node)

# Ask peer for latest model info
hashed_metadata = metadata.hash_self()
requester.ask_is_latest(hashed_metadata, "2026-03-17 10:00:00-000000")

# Request weights
requester.sync_model_weights(hashed_metadata)

# Request full model
requester.ask_sync_model()

# Broadcast update
requester.update_new_weights()
```

### Manual WebSocket Subscription

```python
import asyncio
from controllers.networking.ws_client import server_ws_client
from controllers.networking.messages import send_msg_sender
from models.server import ServerMessage, MessagesTypes, SubscribeTopic
from configs.metadata import MetadataConfig
import os

async def main():
    # Load metadata
    metadata = MetadataConfig.parse_file(
        os.path.expanduser("~/.convey/metadata/model.json")
    )
    
    hashed = metadata.hash_self()
    
    # Start WebSocket client
    asyncio.create_task(server_ws_client())
    
    # Wait for connection
    await asyncio.sleep(2)
    
    # Send subscribe message
    await send_msg_sender(
        ServerMessage(
            msg_type=MessagesTypes.SUBSCRIBE.value,
            message=SubscribeTopic(hashed_metadata=hashed)
        )
    )
    
    print(f"Subscribed to {hashed}")
    
    # Keep running
    await asyncio.sleep(10)

asyncio.run(main())
```

### File Transfer

```python
from controllers.networking.p2p import p2p_node, P2PNode, TransferPathManager
from configs.metadata import MetadataConfig
from models.clients import FileType
import os

metadata = MetadataConfig.parse_file("~/.convey/metadata/model.json")

# Initialize P2P node
p2p_node.start_server()

# Transfer manager
transfer_mgr = TransferPathManager()

# Prepare file for transfer
file_path = metadata.weights_path
prepared = transfer_mgr.prepare_transfer_file(file_path)
print(f"File prepared: {prepared}")

# Get target path on recipient
target_path = transfer_mgr.get_target_path(metadata, FileType.WEIGHTS)
print(f"Will save to: {target_path}")

# Send to peer
peer_ip = "192.168.1.100"
p2p_node.connect_to_peer(peer_ip)
# ... send frames with prepared file ...
```

---

## Advanced Usage

These examples are useful for debugging and local experiments. They are not part of the standard runtime path.

### Batch Merge Multiple Models

```python
import torch
from configs.metadata import MetadataConfig
from controllers.ml.pytorch.merge import TorchSLERP
import os

# Load base
base_weights = torch.load("saved_models/base.pth")
metadata = MetadataConfig.parse_file("~/.convey/metadata/model.json")

# Create SLERP merger
slerp = TorchSLERP(
    strategy_name="batch_merge",
    weights=base_weights,
    t=metadata.t
)

# Progressively merge models
model_files = [
    "saved_models/model_2.pth",
    "saved_models/model_3.pth",
    "saved_models/model_4.pth",
]

for model_file in model_files:
    weights = torch.load(model_file)
    slerp.weights = slerp.merge(weights)  # Update for next iteration
    print(f"Merged {model_file}")

# Save final result
torch.save(slerp.weights, "saved_models/batch_merged.pth")
```

### Profile Merge Performance

```python
import torch
import time
from controllers.ml.pytorch.merge import TorchSLERP

# Create dummy weights
base = {f"layer{i}": torch.randn(1000, 1000) for i in range(10)}
new = {f"layer{i}": torch.randn(1000, 1000) for i in range(10)}

# Time SLERP
slerp = TorchSLERP("perf_test", weights=base, t=0.95)

start = time.time()
for _ in range(10):
    result = slerp.merge(new)
end = time.time()

avg_time = (end - start) / 10
print(f"Average merge time: {avg_time*1000:.2f}ms")
```

### Monitor Network Pool

```python
from controllers.networking.pool import (
    connection_pool,
    p2p_socket_peer_conn,
    verification_pool,
    updated_models_ips_pool
)
import json

# Check peer connections
print("Connected Peers by Model:")
for metadata_hash, ips in connection_pool.items():
    print(f"  {metadata_hash[:8]}...: {ips}")

# Check socket status
print("\nActive Sockets:")
for ip, sock in p2p_socket_peer_conn.items():
    print(f"  {ip}: {sock.fileno() if sock else 'CLOSED'}")

# Check verification cache
print("\nVerification Cache:")
for metadata_hash, data in verification_pool.items():
    print(f"  {metadata_hash[:8]}...: {data}")
```

### Debug Message Flow

```python
import logging
import sys

# Enable debug logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

# Specific module logging
logging.getLogger('controllers.networking.p2p').setLevel(logging.DEBUG)
logging.getLogger('controllers.networking.req_rep').setLevel(logging.DEBUG)
logging.getLogger('controllers.ml.pytorch.merge').setLevel(logging.DEBUG)

# Now run your code
from terminal_app import trigger_file_menu
import asyncio

asyncio.run(trigger_file_menu())
```

### Memory Profiling

```python
import tracemalloc
import torch
from controllers.ml.pytorch.merge import TorchSLERP

tracemalloc.start()

# Load large weights
base = torch.load("saved_models/large_model.pth")
new = torch.load("saved_models/large_model2.pth")

# Take snapshot before merge
snapshot1 = tracemalloc.take_snapshot()

# Merge
slerp = TorchSLERP("perf", weights=base, t=0.95)
result = slerp.merge(new)

# Take snapshot after merge
snapshot2 = tracemalloc.take_snapshot()

# Show top differences
top_stats = snapshot2.compare_to(snapshot1, 'lineno')
print("[ Top 3 Memory Consumers ]")
for stat in top_stats[:3]:
    print(stat)
```

### Handle Offline Scenarios

```python
from controllers.networking.messages_fallback import FallbacksManager
from models.fallback import StringMsg, FileMsg
from models.clients import FileType
from datetime import datetime

fallback = FallbacksManager()

# Create offline message
msg = StringMsg(
    msg='{"query": "is_latest"}',
    timestamp=datetime.now()
)

# Queue for later delivery
metadata_hash = "abc123"
fallback.save_fallback_message(metadata_hash, msg)

# Check pending
pending = fallback.fallback_messages.get(metadata_hash, [])
print(f"Pending messages for {metadata_hash}: {len(pending)}")

# Later, when peer comes online
# FallbacksManager will auto-retry every 60 seconds
```

---

## Complete Example: Full Workflow

This script combines metadata creation, model loading, optional networking startup, merge, and verification in one place.

```python
#!/usr/bin/env python3
"""
Complete Convey workflow: Create, merge, and verify model improvements.
"""

import asyncio
import os
import torch
from datetime import datetime
from configs.metadata import MetadataConfig, StrategyType
from configs.paths import METADATA_PATH
from configs.config import DATEIME_FORMAT
from controllers.ml.pytorch.model import TorchModelStatic
from controllers.networking.threads import start_threads

async def main():
    print("=== Convey Model Merge Workflow ===\n")
    
    # Step 1: Create metadata
    print("1. Creating metadata...")
    metadata = MetadataConfig(
        avg_count=1,
        merge_strategy="SLERP",
        dataset_path="./data",
        model_name="demo_model",
        weights_path="./saved_models/model_1.pth",
        t=0.95,
        latest_updated=datetime.now().strftime(DATEIME_FORMAT),
        static_model_path=os.path.join(
            METADATA_PATH,
            "demo_model_slerp.dill"
        ),
        best_score=75.0
    )
    metadata.save()
    print(f"   Saved to {METADATA_PATH}")
    
    # Step 2: Initialize ML system
    print("\n2. Initializing ML system...")
    model_handler = TorchModelStatic(metadata)
    
    # Step 3: Load base model
    print("3. Loading base model...")
    try:
        base_model = model_handler.load_model_obj()
        base_weights = model_handler.load_weights(metadata.weights_path)
        print("   Base model loaded")
    except Exception as e:
        print(f"   Error: {e}")
        return
    
    # Step 4: Initialize networking (optional)
    print("\n4. Starting networking threads...")
    try:
        start_threads()
        print("   P2P and WebSocket ready")
    except Exception as e:
        print(f"   Warning: {e}")
    
    # Step 5: Merge (if new model available)
    new_model_path = "./saved_models/model_2.pth"
    if os.path.exists(new_model_path):
        print(f"\n5. Merging with {os.path.basename(new_model_path)}...")
        
        new_weights = model_handler.load_weights(new_model_path)
        from controllers.ml.pytorch.merge import TorchSLERP
        
        slerp = TorchSLERP(
            strategy_name="demo_slerp",
            weights=base_weights,
            t=metadata.t
        )
        
        merged_weights = slerp.merge(new_weights)
        print("   Merge complete")
        
        # Step 6: Test merged model
        print("\n6. Testing merged model...")
        merged_model = model_handler.load_model_obj()
        merged_model.load_state_dict(merged_weights)
        
        try:
            from torch.utils.data import DataLoader
            import torchvision.transforms as transforms
            import torchvision.datasets as datasets
            
            device = "cuda" if torch.cuda.is_available() else "cpu"
            merged_model.to(device)
            merged_model.eval()
            
            transform = transforms.Compose([
                transforms.ToTensor(),
                transforms.Normalize(
                    (0.5071, 0.4867, 0.4408),
                    (0.2675, 0.2565, 0.2761)
                )
            ])
            
            testset = datasets.CIFAR100(
                root="./data",
                train=False,
                download=False,
                transform=transform
            )
            loader = DataLoader(testset, batch_size=128, shuffle=False)
            
            correct = total = 0
            with torch.no_grad():
                for inputs, labels in loader:
                    inputs, labels = inputs.to(device), labels.to(device)
                    outputs = merged_model(inputs)
                    _, preds = torch.max(outputs, 1)
                    total += labels.size(0)
                    correct += (preds == labels).sum().item()
            
            accuracy = 100 * correct / total
            print(f"   Accuracy: {accuracy:.2f}%")
            
            # Step 7: Verify improvement
            print("\n7. Verifying improvement...")
            if accuracy > metadata.best_score:
                print(f"   Improved from {metadata.best_score:.2f}% to {accuracy:.2f}%")
                metadata.best_score = accuracy
                metadata.latest_updated = datetime.now().strftime(DATEIME_FORMAT)
                metadata.save()
                torch.save(merged_weights, "./saved_models/best.pth")
                print("   Updates saved")
            else:
                print(f"   No improvement (still {metadata.best_score:.2f}%)")
        
        except FileNotFoundError:
            print("   Test dataset not available, skipping accuracy test")
    else:
        print(f"\n5. Skipping merge (no {new_model_path})")
    
    print("\n=== Workflow Complete ===")

if __name__ == "__main__":
    asyncio.run(main())
```

Save as `workflow_demo.py` and run:
```bash
python workflow_demo.py
```
