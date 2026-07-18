import json
import uuid
from datetime import datetime, date, timezone


class EventSerializer:
    """Serializes payloads into JSON compliant structures."""

    @staticmethod
    def serialize(payload: dict) -> dict:
        """Converts UUID and datetime fields inside a dictionary to strings."""
        if not payload:
            return {}

        def default_encoder(obj):
            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            if isinstance(obj, uuid.UUID):
                return str(obj)
            raise TypeError(f"Type {type(obj)} not serializable")

        # Encode and decode back to get a JSON-compliant dict
        json_str = json.dumps(payload, default=default_encoder)
        return json.loads(json_str)
