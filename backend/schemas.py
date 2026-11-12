from typing import Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    password: str
    selected_role: str


class StudentSignup(BaseModel):
    """Student self-registration.

    Students enter their own institution and academic profile. Programme
    details are self-reported and do not depend on a central institution setup.
    """
    name: str = Field(min_length=2, max_length=120)
    index_number: str = Field(min_length=3, max_length=40)
    email: str
    password: str = Field(min_length=8, max_length=128)
    programme_id: Optional[int] = None
    institution_name: str = Field(min_length=2, max_length=180)
    faculty_name: str = Field(min_length=2, max_length=160)
    department_name: str = Field(min_length=2, max_length=160)
    programme_name: str = Field(min_length=2, max_length=180)
    academic_year: str = Field(min_length=4, max_length=40)
    level: Optional[int] = Field(default=100, ge=100, le=700)
    interests: Optional[str] = ""
    phone: str = Field(min_length=7, max_length=24)
    ghana_card_number: str = Field(min_length=10, max_length=24)
    registration_selfie: str = Field(min_length=100)
    biometric_method: str = Field(default="selfie", pattern="^(selfie|device_biometric)$")
    consent_biometrics: bool = False
