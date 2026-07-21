#!/usr/bin/env python3
"""Run FastAPI with: python api_server.py  (or uvicorn app.api.main:app --reload)"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
