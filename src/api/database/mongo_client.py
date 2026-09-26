import os
from datetime import datetime, timezone
from pymongo import MongoClient
from pymongo.errors import PyMongoError

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "powerpredict")

client = MongoClient(MONGODB_URI)
db = client[MONGODB_DB_NAME]

# Collections
users_collection = db["users"]
alerts_collection = db["alerts"]
maintenance_logs_collection = db["maintenance_logs"]


def test_connection():
    """Pings the cluster - call this once at API startup to fail fast with a
    clear error if MONGODB_URI/credentials/network access are wrong, rather
    than discovering it later on the first real query."""
    try:
        client.admin.command("ping")
        return True
    except PyMongoError as e:
        print(f"MongoDB connection failed: {e}")
        return False


# --- Users ---

def get_user_by_email(email):
    return users_collection.find_one({"email": email})


def create_user(email, hashed_password, role="viewer", full_name=None):
    """role: 'admin' | 'engineer' | 'viewer' - expand as your auth design needs.
    Does NOT hash the password - pass an already-hashed value (e.g. via bcrypt),
    this module only handles storage, never plaintext credentials."""
    if get_user_by_email(email):
        raise ValueError(f"User with email {email} already exists")
    user_doc = {
        "email": email,
        "hashed_password": hashed_password,
        "role": role,
        "full_name": full_name,
        "created_at": datetime.now(timezone.utc),
    }
    result = users_collection.insert_one(user_doc)
    return str(result.inserted_id)


# --- Alerts ---

def log_alert(feeder_uid, zone_id, criticality_tier, alert_type, message, severity="info"):
    """severity: 'info' | 'warning' | 'critical' - used to decide which alerts
    trigger email notifications once that layer exists."""
    alert_doc = {
        "feeder_uid": feeder_uid,
        "zone_id": zone_id,
        "criticality_tier": criticality_tier,
        "alert_type": alert_type,  # e.g. "anomaly_detected", "maintenance_risk", "forecast_threshold"
        "message": message,
        "severity": severity,
        "created_at": datetime.now(timezone.utc),
        "acknowledged": False,
    }
    result = alerts_collection.insert_one(alert_doc)
    return str(result.inserted_id)


def get_recent_alerts(limit=50, severity=None):
    query = {"severity": severity} if severity else {}
    cursor = alerts_collection.find(query).sort("created_at", -1).limit(limit)
    return list(cursor)


def acknowledge_alert(alert_id):
    from bson import ObjectId
    result = alerts_collection.update_one(
        {"_id": ObjectId(alert_id)},
        {"$set": {"acknowledged": True, "acknowledged_at": datetime.now(timezone.utc)}}
    )
    return result.modified_count > 0


# --- Maintenance logs ---

def log_maintenance_diagnosis(transformer_id, zone_id, criticality_tier,
                                fault_type, recommendation, urgency):
    """Persists a diagnosis from maintenance_diagnosis.py so the history is
    queryable later (e.g. 'has T1 been flagged before, how often')."""
    log_doc = {
        "transformer_id": transformer_id,
        "zone_id": zone_id,
        "criticality_tier": criticality_tier,
        "fault_type": fault_type,
        "recommendation": recommendation,
        "urgency": urgency,
        "logged_at": datetime.now(timezone.utc),
        "resolved": False,
    }
    result = maintenance_logs_collection.insert_one(log_doc)
    return str(result.inserted_id)


def get_open_maintenance_logs(criticality_tier=None):
    query = {"resolved": False}
    if criticality_tier:
        query["criticality_tier"] = criticality_tier
    cursor = maintenance_logs_collection.find(query).sort("logged_at", -1)
    return list(cursor)


if __name__ == "__main__":
    # Quick manual connectivity check: python -m src.api.database.mongo_client
    if test_connection():
        print(f"Connected to MongoDB Atlas - database '{MONGODB_DB_NAME}'")
        print(f"Collections: {db.list_collection_names()}")
    else:
        print("Connection failed - check MONGODB_URI in .env")