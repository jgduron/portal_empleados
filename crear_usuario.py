import pyodbc
import bcrypt

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

# Datos del usuario
employee_id = "LK-0022"
email = "josue.garcia@lkafieco.com"
password = "clave123"

# Encriptar la contraseña
hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

# Insertar en la base de datos
cursor.execute("""
    INSERT INTO employee_auth (employee_id, email, password_hash)
    VALUES (?, ?, ?)
""", (employee_id, email, hashed.decode('utf-8')))

conn.commit()
cursor.close()
conn.close()

print("✅ Usuario creado exitosamente.")
