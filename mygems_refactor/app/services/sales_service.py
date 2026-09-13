from app.repositories.sales_repository import SalesRepository


class SalesService:
    def __init__(self, repo: SalesRepository | None = None):
        self.repo = repo or SalesRepository()

    def get_pending_orders(self):
        try:
            return self.repo.get_pending_orders()
        except Exception:
            return []

    def get_order_items(self, order_id: int):
        try:
            return self.repo.get_order_items(order_id)
        except Exception:
            return []

    def get_available_stock(self):
        try:
            return self.repo.get_inventory_available()
        except Exception:
            return []

    def create_sale(self, customer_id: int, items):
        total_amount = sum(float(item["sold_amount"]) for item in items)
        total_paid = sum(float(item["paid_amount"]) for item in items)
        total_balance = total_amount - total_paid

        order_id = self.repo.save_order(customer_id, total_amount, total_paid, total_balance)
        if order_id is None:
            raise RuntimeError("Unable to create sales order")

        # order_id may be a cursor result; support both tuple/row style access consistently.
        if isinstance(order_id, tuple):
            order_id = order_id[0]

        for item in items:
            self.repo.save_order_item(
                order_id=order_id,
                item_code=item.get("item_code", ""),
                lot_no=item.get("lot_no", ""),
                sold_amount=float(item.get("sold_amount", 0)),
                paid_amount=float(item.get("paid_amount", 0)),
                balance_amount=float(item.get("balance_amount", 0)),
                item_status=item.get("item_status", "PENDING_STOCK"),
            )

        return order_id
