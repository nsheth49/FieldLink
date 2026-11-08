import hashlib
import hmac
import secrets
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from app.db import Session
from app.db.models import User, AuthSession, now

def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    return salt+':'+hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()

def verify(password, stored):
    return hmac.compare_digest(hash_password(password,stored.split(':')[0]),stored)

def database():
    with Session() as db:
        yield db

def current_user(request: Request, db=Depends(database)):
    token=request.cookies.get('fieldlink_session','')
    session=db.get(AuthSession,hashlib.sha256(token.encode()).hexdigest())
    if not session or session.expires<now(): raise HTTPException(401,'Sign in required')
    user=db.get(User,session.user_id)
    if not user: raise HTTPException(401,'Unknown user')
    return user

def supervisor(user=Depends(current_user)):
    if user.role!='supervisor': raise HTTPException(403,'Supervisor authorization required')
    return user

def operator(user=Depends(current_user)):
    if user.role not in ('supervisor','operator'): raise HTTPException(403,'Read-only account')
    return user
