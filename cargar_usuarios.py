import pandas as pd
import mysql.connector
import bcrypt

# Leer Excel
archivo = 'usuarios.xlsx'  # Asegúrate de que esté en la misma carpeta
df = pd.read_excel(archivo)

# Validar columnas necesarias
if not {'employee_id', 'email', 'password'}.issubset(df.columns):
    raise Exception("❌ El Excel debe tener las columnas: employee_id, email, password")

# Conexión a MySQL
conn = mysql.connector.connect(
    host='192.168.4.2',       # Cambia si es otro host
    user='root',            # Usuario MySQL
    password='#Domctrlinf', # Contraseña MySQL
    database='apps_devs'    # Base de datos
)
cursor = conn.cursor()

# Insertar usuarios
for index, row in df.iterrows():
    employee_id = str(row['employee_id']).strip()
    email = str(row['email']).strip()
    password = str(row['password']).strip()

    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    try:
        cursor.execute("""
            INSERT INTO employee_auth (employee_id, email, password_hash)
            VALUES (%s, %s, %s)
        """, (employee_id, email, hashed.decode('utf-8')))
        print(f"✅ Usuario {email} insertado.")
    except mysql.connector.Error as err:
        print(f"❌ Error con {email}: {err}")

# Confirmar cambios
conn.commit()
cursor.close()
conn.close()

print("🚀 Todos los usuarios fueron cargados desde el Excel.")
