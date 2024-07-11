import base64
import os
from bson.codec_options import CodecOptions
from pydantic import BaseModel, ConfigDict
from pymongo.encryption import ClientEncryption
from pymongo import ASCENDING, MongoClient
from dotenv import dotenv_values
from bson.binary import STANDARD, Binary
import socket
import bson

env_values = dotenv_values()
hostname = socket.gethostname()

mongo_uri = env_values.get("mongo_uri")
mongo_db = env_values.get("mongo_db","rag")

key_vault_coll = "__keyVault"
key_vault_db = "encryption"
key_vault_namespace = f"{key_vault_db}.{key_vault_coll}"

def ensure_index_exists(key_vault_client:MongoClient):
    indexes = list(key_vault_client[key_vault_db][key_vault_coll].list_indexes())
    # create index if it doesn't exist
    if not any(index["name"] == "keyAltNames" for index in indexes):
        key_vault_client[key_vault_db][key_vault_coll].create_index(
            [("keyAltNames", ASCENDING)],
            unique=True,
            partialFilterExpression={"keyAltNames": {"$exists": True}},
            name="keyAltNames"
        )

def get_kms_provider():
    # skip if master.key exists already
    if not os.path.exists("master.key"):
        with open("master.key", "wb") as f:
            local_master_key = os.urandom(96)
            f.write(local_master_key)
            return {
            "local": {
                "key": local_master_key  # local_master_key variable from the previous step
            }
        }
    else:
        with open("master.key", "rb") as f:
            local_master_key = f.read()
            return {
            "local": {
                "key": local_master_key  # local_master_key variable from the previous step
            }
        }

class EncryptionInfo(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    binary: Binary
    keyName: str

    def as_base64(self):
        return base64.b64encode(self.binary)
    

def get_or_create_vault_entry()->EncryptionInfo:
    with MongoClient(mongo_uri) as key_vault_client:
        ensure_index_exists(key_vault_client)
        kms_providers = get_kms_provider()

        client_encryption = ClientEncryption(
            kms_providers,  # pass in the kms_providers variable from the previous step
            key_vault_namespace,
            key_vault_client,
            CodecOptions(uuid_representation=STANDARD),
        )

        keyDoc = client_encryption.get_key_by_alt_name(hostname)
        if keyDoc is not None:
            # key exists already
            keyDoc = bson.decode(keyDoc.raw)
            data_key_id = keyDoc["_id"]
            return EncryptionInfo(binary=data_key_id, keyName=hostname)
        else:
            data_key_id = client_encryption.create_data_key(
                "local", key_alt_names=[hostname]
            )
            return EncryptionInfo(binary=data_key_id, keyName=hostname)
if __name__ == "__main__":
    info = get_or_create_vault_entry()
    print("DataKeyId [base64]: ", info.as_base64())