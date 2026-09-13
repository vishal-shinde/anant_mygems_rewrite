from app.repositories.vendor_repository import VendorRepository


class VendorService:
    def __init__(self, repository: VendorRepository | None = None):
        self.repository = repository or VendorRepository()

    def list_vendors(self):
        return self.repository.list_vendors()

    def create_vendor(self, vendor_name: str, phone: str | None, email: str | None, address: str | None):
        if not vendor_name or not vendor_name.strip():
            raise ValueError("Vendor name is required.")
        return self.repository.create_vendor(
            vendor_name.strip(),
            phone,
            email,
            address,
            True,
        )
