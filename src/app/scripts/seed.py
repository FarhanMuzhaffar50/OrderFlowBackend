import asyncio

from sqlalchemy import select

from app.core.security import hash_password
from app.db.models import Cart, Inventory, Product, Role, User
from app.db.session import SessionLocal


async def seed() -> None:
    async with SessionLocal() as session:
        accounts = [
            ("admin@orderflow.local", "AdminDemo123!", Role.ADMIN),
            ("customer@orderflow.local", "CustomerDemo123!", Role.CUSTOMER),
        ]
        for email, password, role in accounts:
            if not await session.scalar(select(User).where(User.email == email)):
                user = User(email=email, password_hash=hash_password(password), role=role)
                session.add(user)
                await session.flush()
                session.add(Cart(user_id=user.id))
        products = [
            ("COFFEE-001", "House Coffee", "Whole bean coffee", 1299, 50),
            ("MUG-001", "OrderFlow Mug", "Ceramic mug", 1599, 25),
            ("TEE-001", "OrderFlow T-Shirt", "Cotton shirt", 2499, 15),
        ]
        for sku, name, description, price, quantity in products:
            if not await session.scalar(select(Product).where(Product.sku == sku)):
                product = Product(
                    sku=sku, name=name, description=description, unit_price_minor=price
                )
                session.add(product)
                await session.flush()
                session.add(Inventory(product_id=product.id, available_quantity=quantity))
        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
