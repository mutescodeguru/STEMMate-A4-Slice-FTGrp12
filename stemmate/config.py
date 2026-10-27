# SETTINGS CENTRAL PLACE: anything that changes between machines 
# (sectrets, file paths, limits) read from environment vars here

import os
from datetime import timedelta

class Config:
    #Signs session cookie so users cant forge it. Set a real vlaue with
    #STEMMATE_SECRET_KEY environment var outside dev
    SECRET_KEY = os.environ.get("STEMMATE_SECRET_KEY", "dev-only-change-me")

    #Session cookie rules (SR-01)
    SESSION_COOKIE_HTTPONLY = True  #JS cannot read cookie
    SESSION_COOKIE_SAMESITE = "Strict"  #not sent on requests from other site
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)  #idle expiry (AC-6)
    
    #SHared Key Sync service sends to central store 
    SYNC_KEY = os.environ.get("STEMMATE_SYNC_KEY", "dev-sync-key")
    
    #50MB data budget (QR-01). env var used to test a tiny limit
    STORAGE_LIMIT_BYTES = int(
        os.environ.get("STEMMATE_STORAGE_LIMIT_BYTES", 50 * 1024 * 1024)
    )