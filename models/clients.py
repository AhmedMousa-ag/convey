from pydantic import BaseModel
from enum import Enum
from datetime import datetime


class AuthenticationMessage(BaseModel):
    hashed_metadata: str
    secret_key: str


class IsLatestModel(BaseModel):
    current_date: datetime


class ResponseIsLatestModel(BaseModel):
    is_latest: bool
    last_update: datetime


class SyncLatestModel(BaseModel):
    pass


class SyncDataset(BaseModel):
    pass


class SyncStaticModules(BaseModel):
    pass


class UpdateOthersLatestModel(BaseModel):
    pass


class P2PMessagesTypes(Enum):
    IsLatest = "is_latest"
    ResIsLatest = "res_is_latest"
    SYNCModel = "sync_models"
    SYNCDataset = "sync_dataset"
    UPDATE = "update_model"
    SYNCStaticModules = "sync_static_modules"
    SYNCModelWeights = "sync_model_weights"


class P2PMessage(BaseModel):
    msg_type: P2PMessagesTypes
    hashed_metadata: str
    message: (
        IsLatestModel
        | ResponseIsLatestModel
        | SyncLatestModel
        | UpdateOthersLatestModel
        | SyncDataset
        | SyncStaticModules
    )


class FileType(Enum):
    MODEL = "MODEL"
    DATA = "DATA"
    STATIC_MOD = "STATIC_MOD"
    WEIGHTS = "MODEL_WEIG"
