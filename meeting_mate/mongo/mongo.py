import base64
from dotenv import dotenv_values
from pymongo import MongoClient
from pymongo.encryption_options import AutoEncryptionOpts
from bson.binary import Binary, UUID_SUBTYPE
import os
from meeting_mate.mongo.setup_encryption import key_vault_namespace, get_or_create_vault_entry

# Load the .env file and access the parsed values
env_values = dotenv_values()

# Access the values as a dictionary
mongo_uri = env_values.get("mongo_uri")
mongo_db = env_values.get("mongo_db","rag")

mongo_crypt_shared_path = env_values.get("mongo_crypt_shared_path")

path = "master.key"
if not os.path.exists(path):
    raise Exception(f"Master key file not found at {path}")

with open(path, "rb") as f:
    local_master_key = f.read()
    kms_providers = {
        "local": {
            "key": local_master_key  # local_master_key variable from the previous step
        },
}

encryptionInfo = get_or_create_vault_entry()
json_schema = {
    "bsonType": "object",
    "encryptMetadata": {"keyId": [encryptionInfo.binary]},
    "properties": {
        "tokens": {
            "bsonType": "object",
            "properties": {
                "access_token": {
                    "encrypt": {
                        "bsonType": "string",
                        "algorithm": "AEAD_AES_256_CBC_HMAC_SHA_512-Random",
                    }
                },
                "refresh_token": {
                    "encrypt": {
                        "bsonType": "string",
                        "algorithm": "AEAD_AES_256_CBC_HMAC_SHA_512-Random",
                    }
                },
            }
        }
    }
}

user_schema = {f"{mongo_db}.users": json_schema}
extra_options = {"crypt_shared_lib_path": mongo_crypt_shared_path}
fle_opts = AutoEncryptionOpts(
    kms_providers, key_vault_namespace, schema_map=user_schema, **extra_options
)

class MongoDB:
    def __init__(self, encryption_opts=None):
        self.client = MongoClient(mongo_uri, auto_encryption_opts=encryption_opts)
        self.db = self.client[mongo_db]

    def get_db(self):
        return self.db
    
    def store_user(self, user_data):
        user_data["key-id"] = encryptionInfo.keyName
        result = self.db.users.update_one({"sub": user_data["sub"]}, {"$set": user_data}, upsert=True)
        if result.modified_count == 1 or result.upserted_id:
            return True
        else:
            raise Exception("Failed to store user data")

INSTANCE = MongoDB(fle_opts)
PLAIN_INSTANCE = MongoDB()

def test_connection():
    return INSTANCE.client.topology_description

if __name__ == "__main__":
    print(test_connection())