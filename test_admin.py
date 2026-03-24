import asyncio
from db.db import connect_to_mongo, get_db

async def check():
    await connect_to_mongo()
    db = get_db()
    users = await db['admin_users'].find().to_list(10)
    print("-------------------------")
    print('Total admin users in DB:', len(users))
    for u in users:
        print("username:", u.get("username"))
        print("password_hash:", u.get("password"))
    print("-------------------------")
    
if __name__ == "__main__":
    asyncio.run(check())
