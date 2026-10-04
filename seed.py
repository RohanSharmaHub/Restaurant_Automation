"""Populate the database with sample data.

Run:  python seed.py
"""
from app import create_app
from app.extensions import db
from app.models import Category, MenuItem, Role, Table, User


SAMPLE_CATEGORIES = [
    ("Starters", "Light bites to begin", 1),
    ("Mains", "Hearty main courses", 2),
    ("Breads", "Freshly baked", 3),
    ("Desserts", "Sweet endings", 4),
    ("Beverages", "Hot and cold drinks", 5),
]

SAMPLE_ITEMS = {
    "Starters": [
        ("Veg Spring Rolls", "Crispy rolls with sweet chili sauce", 220, True, 12),
        ("Paneer Tikka", "Marinated cottage cheese, tandoor-grilled", 280, True, 15),
        ("Chicken Lollipop", "Spicy fried chicken wings", 320, False, 18),
    ],
    "Mains": [
        ("Veg Biryani", "Fragrant basmati rice with vegetables", 320, True, 20),
        ("Chicken Biryani", "Hyderabadi-style chicken biryani", 420, False, 25),
        ("Paneer Butter Masala", "Rich, creamy tomato gravy", 360, True, 18),
        ("Dal Makhani", "Slow-cooked black lentils", 280, True, 15),
    ],
    "Breads": [
        ("Butter Naan", "Tandoor-fresh", 60, True, 5),
        ("Garlic Naan", "With garlic and coriander", 80, True, 5),
        ("Tandoori Roti", "Whole-wheat", 50, True, 5),
    ],
    "Desserts": [
        ("Gulab Jamun", "Two pieces in sugar syrup", 120, True, 3),
        ("Ice Cream", "Vanilla, chocolate, or strawberry", 150, True, 3),
    ],
    "Beverages": [
        ("Masala Chai", "Spiced Indian tea", 60, True, 5),
        ("Cold Coffee", "Blended with ice cream", 180, True, 7),
        ("Fresh Lime Soda", "Sweet or salted", 90, True, 4),
    ],
}

SAMPLE_USERS = [
    ("admin", "admin@resto.test", "admin123", Role.ADMIN.value),
    ("manager", "manager@resto.test", "manager123", Role.MANAGER.value),
    ("waiter", "waiter@resto.test", "waiter123", Role.WAITER.value),
    ("chef", "chef@resto.test", "chef123", Role.CHEF.value),
]


def seed():
    app = create_app()
    with app.app_context():
        print("Dropping & recreating tables...")
        db.drop_all()
        db.create_all()

        print("Seeding users...")
        for username, email, password, role in SAMPLE_USERS:
            u = User(username=username, email=email, role=role)
            u.set_password(password)
            db.session.add(u)

        print("Seeding categories & menu items...")
        cat_map: dict[str, Category] = {}
        for name, desc, order in SAMPLE_CATEGORIES:
            c = Category(name=name, description=desc, display_order=order)
            db.session.add(c)
            cat_map[name] = c
        db.session.flush()  # get IDs

        for cat_name, items in SAMPLE_ITEMS.items():
            cat = cat_map[cat_name]
            for name, desc, price, veg, prep in items:
                db.session.add(
                    MenuItem(
                        name=name,
                        description=desc,
                        price=price,
                        is_vegetarian=veg,
                        prep_time_minutes=prep,
                        category_id=cat.id,
                    )
                )

        print("Seeding tables...")
        for n in range(1, 11):
            db.session.add(
                Table(
                    number=n,
                    capacity=4 if n % 2 else 6,
                    location="Window" if n <= 4 else ("Patio" if n >= 9 else "Indoor"),
                )
            )

        db.session.commit()
        print("Done.")
        print("Login at  http://127.0.0.1:5000/auth/login  with admin / admin123")


if __name__ == "__main__":
    seed()
