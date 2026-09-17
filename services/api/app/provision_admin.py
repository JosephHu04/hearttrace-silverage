"""Provision an administrator locally after database migration, without default credentials."""
from getpass import getpass

from sqlalchemy import select

from app.core.security import hash_password
from app.db.models import User, uuid_string
from app.db.session import SessionLocal


def main() -> None:
    identifier = input("管理员手机号或邮箱：").strip().lower()
    name = input("管理员显示名：").strip()
    password = getpass("密码（至少 10 位）：")
    if len(identifier) < 3 or len(identifier) > 120 or len(name) < 2 or len(name) > 100 or not 10 <= len(password) <= 128:
        raise SystemExit("输入长度不符合要求")
    if password != getpass("再次输入密码："):
        raise SystemExit("两次密码不一致")
    with SessionLocal() as db:
        if db.scalar(select(User.id).where(User.login_identifier == identifier)):
            raise SystemExit("账号已存在，不会覆盖")
        db.add(User(id=f"admin-{uuid_string()}", display_name=name, role="admin", login_identifier=identifier, password_hash=hash_password(password)))
        db.commit()
    print("管理员账号已创建。")


if __name__ == "__main__":
    main()
