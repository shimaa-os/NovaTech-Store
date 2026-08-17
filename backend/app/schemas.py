from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, EmailStr, Field, field_validator


def finite_decimal(value: object) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Invalid numeric value") from exc
    if not amount.is_finite():
        raise ValueError("Numeric value must be finite")
    return amount.quantize(Decimal("0.01"))


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    totp: str | None = Field(default=None, pattern=r"^\d{6}$")


class RegistrationRequest(BaseModel):
    user_name: str = Field(min_length=3, max_length=80)
    email: EmailStr
    password: str = Field(min_length=15, max_length=128)

    @field_validator("user_name")
    @classmethod
    def clean_username(cls, value: str) -> str:
        value = value.strip().lower()
        if not value.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username may contain letters, numbers, hyphens, and underscores")
        return value


class EmailRequest(BaseModel):
    email: EmailStr


class VerifyOtpRequest(EmailRequest):
    otp: str = Field(pattern=r"^\d{6}$")


class UsernameUpdateRequest(BaseModel):
    new_name: str = Field(min_length=3, max_length=80)

    @field_validator("new_name")
    @classmethod
    def clean_username(cls, value: str) -> str:
        value = value.strip().lower()
        if not value.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Invalid username")
        return value


class PasswordChangeRequest(BaseModel):
    old_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=15, max_length=128)


class DeleteAccountRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)


class CartMutationRequest(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(default=1, gt=0, le=999)


class QuantityRequest(BaseModel):
    quantity: int = Field(gt=0, le=999)


class WalletChargeRequest(BaseModel):
    user_name: str = Field(min_length=3, max_length=80)
    amount: Decimal

    @field_validator("amount", mode="before")
    @classmethod
    def validate_amount(cls, value: object) -> Decimal:
        amount = finite_decimal(value)
        if amount <= 0:
            raise ValueError("Amount must be greater than zero")
        return amount


class ImagePayload(BaseModel):
    name: str = Field(default="image.jpg", max_length=100)
    data_url: str = Field(max_length=12_000_000)


class ProductCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=100)
    price: Decimal
    quantity: int = Field(ge=0, le=10_000_000)
    brand: str = Field(default="Nova", max_length=100)
    description: str = Field(default="", max_length=5000)
    rating: Decimal = Decimal("4.5")
    badge: str = Field(default="", max_length=50)
    image: ImagePayload | None = None

    @field_validator("price", mode="before")
    @classmethod
    def validate_price(cls, value: object) -> Decimal:
        price = finite_decimal(value)
        if price <= 0:
            raise ValueError("Price must be greater than zero")
        return price

    @field_validator("rating", mode="before")
    @classmethod
    def validate_rating(cls, value: object) -> Decimal:
        rating = finite_decimal(value)
        if rating < 0 or rating > 5:
            raise ValueError("Rating must be between zero and five")
        return rating.quantize(Decimal("0.1"))


class ProductUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    category: str | None = Field(default=None, min_length=1, max_length=100)
    price: Decimal | None = None
    quantity: int | None = Field(default=None, ge=0, le=10_000_000)
    brand: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=5000)
    rating: Decimal | None = None
    badge: str | None = Field(default=None, max_length=50)

    @field_validator("price", mode="before")
    @classmethod
    def validate_price(cls, value: object) -> Decimal | None:
        if value is None:
            return None
        price = finite_decimal(value)
        if price <= 0:
            raise ValueError("Price must be greater than zero")
        return price

    @field_validator("rating", mode="before")
    @classmethod
    def validate_rating(cls, value: object) -> Decimal | None:
        if value is None:
            return None
        rating = finite_decimal(value)
        if rating < 0 or rating > 5:
            raise ValueError("Rating must be between zero and five")
        return rating.quantize(Decimal("0.1"))

