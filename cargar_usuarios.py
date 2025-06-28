import pandas as pd
import pyodbc
import bcrypt

# Leer Excel
archivo = 'usuarios.xlsx'  # Asegúrate de que esté en la misma carpeta
df = pd.read_excel(archivo)

# Validar columnas
if not {'employee_id', 'email', 'password'}.issubset(df.columns):
    raise Exception("❌ El Excel debe tener las columnas: employee_id, email, password")

# Conexión a SQL Server
conn = pyodbc.connect(
    'DRIVER={ODBC Driver 18 for SQL Server};'
    'SERVER=192.168.4.202;'
    'DATABASE=reportes_tiendas;'
    'UID=sa;'
    'PWD=#Domctrlinf;'
    'TrustServerCertificate=yes;'
)
cursor = conn.cursor()

# Insertar usuarios
for index, row in df.iterrows():
    employee_id = str(row['employee_id']).strip()
    email = str(row['email']).strip()
    password = str(row['password']).strip()

    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    cursor.execute("""
        INSERT INTO employee_auth (employee_id, email, password_hash)
        VALUES (?, ?, ?)
    """, (employee_id, email, hashed.decode('utf-8')))

    print(f"✅ Usuario {email} insertado.")

conn.commit()
cursor.close()
conn.close()

print("🚀 Todos los usuarios fueron cargados desde el Excel.")
