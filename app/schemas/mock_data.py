from datetime import datetime

from pydantic import BaseModel, EmailStr


class MockDataGenerateResponse(BaseModel):
    email: EmailStr
    user_id: str
    generated_records: int
    start_date: datetime
    end_date: datetime
    frequency: int
