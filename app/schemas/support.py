from pydantic import BaseModel

class ContactSupportRequest(BaseModel):
    fullname : str
    email: str
    subject: str 
    topic: str
    message: str

class ContactSupportResponse(BaseModel):
    succss: bool
    inquiry: ContactSupportRequest
