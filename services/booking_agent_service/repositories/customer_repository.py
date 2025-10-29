# services/booking_agent_service/repositories/customer_repository.py

"""
Customer Repository for customer data operations.
Staff Engineer principle: Domain-specific queries, optimized lookups.
"""

from typing import Optional, List
from datetime import datetime
from .base import BaseRepository, db
from ..models.customer import Customer
from ..utils.logger import get_logger

logger = get_logger(__name__)


class CustomerRepository(BaseRepository[Customer]):
    """
    Repository for Customer entity operations.

    Provides specialized queries for customer management:
    - Phone number lookup (primary use case)
    - Tier-based queries
    - Birthday lookups for campaigns
    - Loyalty point tracking
    """

    def __init__(self):
        """Initialize with shared database storage"""
        super().__init__()
        # Use shared in-memory database
        self._storage = db.get_customers()

    def _get_entity_id(self, entity: Customer) -> str:
        """Get customer ID from entity"""
        return entity.customer_id

    def find_by_phone(self, phone_number: str) -> Optional[Customer]:
        """
        Find customer by phone number.

        This is the most common lookup operation (for caller identification).

        Args:
            phone_number: Customer phone number

        Returns:
            Customer if found, None otherwise
        """
        for customer in self._storage.values():
            if customer.phone_number == phone_number:
                logger.debug(
                    "Customer found by phone",
                    phone=phone_number,
                    customer_id=customer.customer_id
                )
                return customer

        logger.debug("Customer not found by phone", phone=phone_number)
        return None

    def find_by_email(self, email: str) -> Optional[Customer]:
        """
        Find customer by email.

        Args:
            email: Customer email address

        Returns:
            Customer if found, None otherwise
        """
        for customer in self._storage.values():
            if customer.email and customer.email.lower() == email.lower():
                return customer
        return None

    def find_by_tier(self, tier: str) -> List[Customer]:
        """
        Find all customers by tier.

        Useful for targeted marketing campaigns.

        Args:
            tier: Customer tier (new, bronze, silver, gold, platinum, vip)

        Returns:
            List of customers in that tier
        """
        results = []
        for customer in self._storage.values():
            if customer.tier.value == tier:
                results.append(customer)
        return results

    def find_vip_customers(self) -> List[Customer]:
        """
        Find all VIP customers.

        Returns:
            List of VIP tier customers
        """
        return self.find_by_tier("vip")

    def find_birthdays_in_month(self, month: int) -> List[Customer]:
        """
        Find customers with birthdays in given month.

        Used for birthday campaign targeting.

        Args:
            month: Month number (1-12)

        Returns:
            List of customers with birthdays in that month
        """
        results = []
        for customer in self._storage.values():
            if customer.birth_date and customer.birth_date.month == month:
                results.append(customer)
        return results

    def find_by_total_spent_range(
        self,
        min_amount: float,
        max_amount: Optional[float] = None
    ) -> List[Customer]:
        """
        Find customers by total spent range.

        Useful for high-value customer identification.

        Args:
            min_amount: Minimum total spent
            max_amount: Maximum total spent (None = no limit)

        Returns:
            List of matching customers
        """
        results = []
        for customer in self._storage.values():
            if customer.total_spent >= min_amount:
                if max_amount is None or customer.total_spent <= max_amount:
                    results.append(customer)
        return results

    def find_high_value_customers(self, threshold: float = 5000.0) -> List[Customer]:
        """
        Find high-value customers (above spending threshold).

        Args:
            threshold: Minimum total spent to be considered high-value

        Returns:
            List of high-value customers
        """
        return self.find_by_total_spent_range(min_amount=threshold)

    def find_inactive_customers(self, days: int = 90) -> List[Customer]:
        """
        Find customers who haven't visited in X days.

        Useful for re-engagement campaigns.

        Args:
            days: Days since last visit

        Returns:
            List of inactive customers
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        results = []

        for customer in self._storage.values():
            if customer.last_visit:
                if customer.last_visit < cutoff_date:
                    results.append(customer)
            elif customer.total_appointments == 0:
                # Never visited
                results.append(customer)

        return results

    def find_with_marketing_consent(self) -> List[Customer]:
        """
        Find customers who have given marketing consent.

        GDPR/KVKK compliance - only market to consenting customers.

        Returns:
            List of customers with marketing consent
        """
        results = []
        for customer in self._storage.values():
            if customer.marketing_consent and customer.sms_consent:
                results.append(customer)
        return results

    def update_last_visit(self, customer_id: str) -> Optional[Customer]:
        """
        Update customer's last visit timestamp.

        Called after appointment completion.

        Args:
            customer_id: Customer ID

        Returns:
            Updated customer or None if not found
        """
        customer = self.get_by_id(customer_id)
        if customer:
            customer.last_visit = datetime.utcnow()
            customer.updated_at = datetime.utcnow()
            self.update(customer)
            logger.debug("Last visit updated", customer_id=customer_id)
        return customer

    def increment_appointment_count(
        self,
        customer_id: str,
        amount: float
    ) -> Optional[Customer]:
        """
        Increment customer's appointment count and total spent.

        Called after appointment completion.

        Args:
            customer_id: Customer ID
            amount: Appointment amount

        Returns:
            Updated customer or None if not found
        """
        customer = self.get_by_id(customer_id)
        if customer:
            customer.add_appointment(amount)
            self.update(customer)
            logger.info(
                "Customer stats updated",
                customer_id=customer_id,
                total_appointments=customer.total_appointments,
                tier=customer.tier.value
            )
        return customer

    def get_customer_stats(self) -> dict:
        """
        Get aggregate customer statistics.

        Useful for reporting and dashboard.

        Returns:
            Statistics dictionary
        """
        customers = self.list_all()

        if not customers:
            return {
                "total_customers": 0,
                "tier_distribution": {},
                "total_revenue": 0.0,
                "average_spent": 0.0
            }

        tier_dist = {}
        total_revenue = 0.0

        for customer in customers:
            tier = customer.tier.value
            tier_dist[tier] = tier_dist.get(tier, 0) + 1
            total_revenue += customer.total_spent

        return {
            "total_customers": len(customers),
            "tier_distribution": tier_dist,
            "total_revenue": total_revenue,
            "average_spent": total_revenue / len(customers) if customers else 0.0,
            "vip_count": tier_dist.get("vip", 0),
            "platinum_count": tier_dist.get("platinum", 0)
        }


# Global repository instance
customer_repository = CustomerRepository()


# Import timedelta for inactive customers calculation
from datetime import timedelta
