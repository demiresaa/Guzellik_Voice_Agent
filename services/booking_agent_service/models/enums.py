# services/booking_agent_service/models/enums.py

"""
Enum definitions for type safety and business logic.
Staff Engineer principle: Use enums to prevent invalid states.
"""

from enum import Enum


class AppointmentStatus(str, Enum):
    """Appointment lifecycle states"""
    PENDING = "pending"                # Awaiting confirmation
    CONFIRMED = "confirmed"            # Confirmed by customer
    CANCELLED = "cancelled"            # Cancelled by customer or system
    COMPLETED = "completed"            # Service completed
    NO_SHOW = "no_show"               # Customer didn't show up
    RESCHEDULED = "rescheduled"       # Moved to different time


class ServiceCategory(str, Enum):
    """Service categories for the salon"""
    HAIR = "hair"                      # Saç hizmetleri
    NAILS = "nails"                    # Tırnak bakımı
    SKINCARE = "skincare"              # Cilt bakımı
    MAKEUP = "makeup"                  # Makyaj
    MASSAGE = "massage"                # Masaj
    WAXING = "waxing"                  # Ağda
    OTHER = "other"                    # Diğer


class PaymentStatus(str, Enum):
    """Payment status for appointments"""
    NOT_REQUIRED = "not_required"      # Ön ödeme gerekmiyor
    PENDING = "pending"                # Ödeme bekleniyor
    PARTIAL = "partial"                # Kapora alındı
    PAID = "paid"                      # Tam ödendi
    REFUNDED = "refunded"              # İade edildi


class NotificationType(str, Enum):
    """Types of notifications sent to customers"""
    APPOINTMENT_CONFIRMATION = "appointment_confirmation"
    APPOINTMENT_REMINDER = "appointment_reminder"
    APPOINTMENT_CANCELLED = "appointment_cancelled"
    PAYMENT_REQUEST = "payment_request"
    FEEDBACK_REQUEST = "feedback_request"
    PROMOTIONAL = "promotional"
    BIRTHDAY = "birthday"


class CampaignType(str, Enum):
    """Types of marketing campaigns"""
    BIRTHDAY = "birthday"              # Doğum günü indirimi
    LOYALTY = "loyalty"                # Sadakat programı
    SEASONAL = "seasonal"              # Sezonluk kampanya
    FIRST_TIME = "first_time"          # İlk müşteri indirimi
    REFERRAL = "referral"              # Tavsiye indirimi
    BUNDLE = "bundle"                  # Paket hizmet indirimi


class CustomerTier(str, Enum):
    """Customer loyalty tiers"""
    NEW = "new"                        # Yeni müşteri
    BRONZE = "bronze"                  # 1-5 randevu
    SILVER = "silver"                  # 6-15 randevu
    GOLD = "gold"                      # 16-30 randevu
    PLATINUM = "platinum"              # 31+ randevu
    VIP = "vip"                        # Özel müşteri


class SpecialistRole(str, Enum):
    """Specialist roles in the salon"""
    HAIR_STYLIST = "hair_stylist"      # Kuaför
    NAIL_TECHNICIAN = "nail_technician" # Tırnakçı
    BEAUTICIAN = "beautician"          # Güzellik uzmanı
    MAKEUP_ARTIST = "makeup_artist"    # Makyöz
    MASSEUSE = "masseuse"              # Masöz
    MANAGER = "manager"                # Salon müdürü
