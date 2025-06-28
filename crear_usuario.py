import mysql.connector
import bcrypt

# Conexión a MySQL
conn = mysql.connector.connect(
    host='192.168.4.2',       # Cambia si tu MySQL no está local
    user='root',            # Tu usuario MySQL
    password='#Domctrlinf', # Tu contraseña MySQL
    database='apps_devs'    # Tu base de datos
)

cursor = conn.cursor()

# Datos del usuario
employee_id = "LK-0022"
email = "josue.garcia@lkafieco.com"
password = "Logan2022*"

# Encriptar la contraseña
hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

# Insertar en la base de datos
cursor.execute("""
    INSERT INTO employee_auth (employee_id, email, password_hash)
    VALUES (%s, %s, %s)
""", (employee_id, email, hashed.decode('utf-8')))

conn.commit()
cursor.close()
conn.close()

print("✅ Usuario creado exitosamente en MySQL.")
