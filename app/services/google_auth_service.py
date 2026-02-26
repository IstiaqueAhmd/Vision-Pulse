from google.oauth2 import id_token
from google.auth.transport import requests
from fastapi import HTTPException
from app.core.config import settings

def verify_google_token(token: str) -> dict:
    """
    Verifies a Google ID token and returns the user's info if valid.
    Specifically checks the signature, audience (client ID), and expiration.
    """
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Google Client ID is not configured on the server")

    try:
        # id_token.verify_oauth2_token verifies the token's signature, the exp claim, 
        # and checking the aud claim against the CLIENT_ID we pass in.
        idinfo = id_token.verify_oauth2_token(
            token, 
            requests.Request(), 
            settings.GOOGLE_CLIENT_ID
        )

        # Confirm the issuer is indeed Google
        if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
            raise ValueError('Wrong issuer.')

        return {
            "email": idinfo.get("email"),
            "name": idinfo.get("name"),
            "picture": idinfo.get("picture")
        }
        
    except ValueError as e:
        # Invalid token
        raise HTTPException(status_code=400, detail=f"Invalid Google ID token: {str(e)}")
