from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


# TODO написать обработку файла
async def process_file(file_path: Path, doc: Dict[str, Any]) -> Dict[str, Any]:
    st = file_path.stat()
    return {
        "status": "ok",
        "file_name": file_path.name,
        "file_size": st.st_size,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "doc_id": str(doc["_id"]),
    }
