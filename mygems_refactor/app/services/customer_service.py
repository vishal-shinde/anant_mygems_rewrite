from app.repositories.customer_repository import CustomerRepository


class CustomerService:
    def __init__(self, repository: CustomerRepository | None = None):
        self.repository = repository or CustomerRepository()

    def list_customers(self):
        return self.repository.list_customers()

    def create_customer(self, customer_name: str, phone: str | None, email: str | None, address: str | None, city: str | None, gst_no: str | None):
        if not customer_name or not customer_name.strip():
            raise ValueError("Customer name is required.")
        return self.repository.create_customer(
            customer_name.strip(),
            phone,
            email,
            address,
            city,
            gst_no,
            True,
        )
