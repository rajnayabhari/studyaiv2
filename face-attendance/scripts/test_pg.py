import psycopg2
passwords = ['postgres', '', 'root', 'admin', 'password', '123456', '1234', 'toor']
found = False
for p in passwords:
    try:
        conn = psycopg2.connect(dbname='postgres', user='postgres', password=p, host='localhost', port=5432)
        print(f"Success with password: '{p}'")
        conn.close()
        found = True
        break
    except Exception as e:
        pass
if not found:
    print("Failed all")
