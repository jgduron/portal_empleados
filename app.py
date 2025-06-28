from flask import Flask, render_template, request, redirect, session, url_for, make_response, jsonify
import mysql.connector
import bcrypt
from xhtml2pdf import pisa
from io import BytesIO
import json
from datetime import datetime
import base64
import os
from PyPDF2 import PdfReader, PdfWriter
import uuid
from collections import defaultdict
from dotenv import load_dotenv

app = Flask(__name__)
app.secret_key = 'clave_super_secreta'  # Cambia esto por una clave segura

# Carga variables de entorno .env (opcional)
load_dotenv()

# Configuración MySQL ERPNext
mysql_config_erpnext = {
    'host': '192.168.4.2',
    'user': 'root',
    'password': '#Domctrlinf',
    'database': 'test_erpnext'
}

# Configuración MySQL apps_devs (auth y constancias)
mysql_config_apps_devs = {
    'host': '192.168.4.2',
    'user': 'root',
    'password': '#Domctrlinf',
    'database': 'apps_devs'
}

def get_mysql_conn_erpnext():
    return mysql.connector.connect(**mysql_config_erpnext)

def get_mysql_conn_apps_devs():
    return mysql.connector.connect(**mysql_config_apps_devs)

def combinar_pdf_con_membrete(membrete_path, pdf_contenido):
    plantilla = PdfReader(membrete_path)
    contenido = PdfReader(BytesIO(pdf_contenido))
    output = PdfWriter()
    page_background = plantilla.pages[0]
    page_overlay = contenido.pages[0]
    page_background.merge_page(page_overlay)
    output.add_page(page_background)
    output_buffer = BytesIO()
    output.write(output_buffer)
    return output_buffer.getvalue()

import yagmail
def enviar_correo(destinatario, asunto, cuerpo):
    try:
        cuerpo = str(cuerpo).encode('utf-8').decode('utf-8')
        yag = yagmail.SMTP(user='erpnext.noreply@gmail.com', password='npvl ulkr qqpw jukh')
        yag.send(to=destinatario, subject=asunto, contents=[cuerpo])
        print(f"Correo enviado a {destinatario}")
    except Exception as e:
        print("Error al enviar el correo:", e)

@app.route('/', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password'].encode('utf-8')

        conn = get_mysql_conn_apps_devs()  # Cambiado a apps_devs
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT employee_id, password_hash FROM employee_auth WHERE email = %s", (email,))
        row = cursor.fetchone()
        conn.close()

        if row and bcrypt.checkpw(password, row['password_hash'].encode('utf-8')):
            session['employee_id'] = row['employee_id']
            return redirect(url_for('dashboard'))
        else:
            error = 'Credenciales incorrectas.'

    return render_template('login.html', error=error)

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    message = None
    if request.method == 'POST':
        email = request.form['email']
        conn = get_mysql_conn_apps_devs()  # apps_devs
        cursor = conn.cursor()
        cursor.execute("SELECT employee_id FROM employee_auth WHERE email = %s", (email,))
        row = cursor.fetchone()

        if row:
            token = str(uuid.uuid4())
            cursor.execute("UPDATE employee_auth SET reset_token = %s WHERE email = %s", (token, email))
            conn.commit()
            conn.close()

            reset_link = url_for('reset_password', token=token, _external=True)
            enviar_correo(
                destinatario=email,
                asunto="Recuperación de contraseña",
                cuerpo=f"Hola,\n\nPara restablecer tu contraseña, haz clic en el siguiente enlace:\n\n{reset_link}\n\nSi no solicitaste este cambio, ignora este mensaje."
            )

        message = "Si tu correo está registrado, recibirás instrucciones pronto."
    
    return render_template('forgot_password.html', message=message)

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    conn = get_mysql_conn_apps_devs()  # apps_devs
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT email FROM employee_auth WHERE reset_token = %s", (token,))
    user = cursor.fetchone()

    if not user:
        return render_template("reset_password.html", error="El enlace de recuperación es inválido o ha expirado.")

    if request.method == 'POST':
        new_password = request.form['new_password']
        hashed = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        cursor.execute("UPDATE employee_auth SET password_hash = %s, reset_token = NULL WHERE reset_token = %s", (hashed, token))
        conn.commit()
        conn.close()

        return render_template("reset_password.html", success="Tu contraseña ha sido restablecida exitosamente.")

    return render_template("reset_password.html")

@app.route('/dashboard')
def dashboard():
    if 'employee_id' not in session:
        return redirect(url_for('login'))

    employee_id = session['employee_id']
    conn_mysql = get_mysql_conn_erpnext()  # test_erpnext
    cursor_mysql = conn_mysql.cursor(dictionary=True)

    cursor_mysql.execute("""
        SELECT name AS slip_id, start_date, employee_name, end_date, net_pay
        FROM `tabSalary Slip`
        WHERE employee = %s AND docstatus = 1
        ORDER BY start_date DESC
    """, (employee_id,))
    recibos = cursor_mysql.fetchall()

    nombre_empleado = recibos[0]['employee_name'] if recibos else 'Empleado no encontrado'

    cursor_mysql.execute("""
        SELECT
            IFNULL(SUM(la.total_leaves_allocated), 0) AS dias_asignados_total,
            IFNULL(SUM(
                (SELECT IFNULL(SUM(lap.total_leave_days), 0)
                 FROM `tabLeave Application` lap
                 WHERE lap.employee = la.employee
                   AND lap.leave_type = la.leave_type
                   AND lap.docstatus = 1
                   AND lap.from_date >= la.from_date
                   AND lap.to_date <= la.to_date
                )
            ), 0) AS dias_usados_total,
            IFNULL(SUM(la.total_leaves_allocated), 0) - IFNULL(SUM(
                (SELECT IFNULL(SUM(lap.total_leave_days), 0)
                 FROM `tabLeave Application` lap
                 WHERE lap.employee = la.employee
                   AND lap.leave_type = la.leave_type
                   AND lap.docstatus = 1
                   AND lap.from_date >= la.from_date
                   AND lap.to_date <= la.to_date
                )
            ), 0) AS dias_disponibles_total
        FROM `tabLeave Allocation` la
        WHERE la.docstatus = 1
          AND la.leave_type = 'Vacaciones'
          AND la.employee = %s
    """, (employee_id,))
    resultado_vac = cursor_mysql.fetchone()

    dias_vac_asignados = float(resultado_vac['dias_asignados_total'] or 0)
    dias_vac_usados = float(resultado_vac['dias_usados_total'] or 0)
    dias_vac_disponibles = float(resultado_vac['dias_disponibles_total'] or 0)

    cursor_mysql.execute("""
        SELECT from_date, to_date, total_leave_days, description
        FROM `tabLeave Application`
        WHERE employee = %s AND leave_type = 'Vacaciones' AND docstatus = 1
        ORDER BY from_date DESC
    """, (employee_id,))
    vacaciones_tomadas = cursor_mysql.fetchall()

    # Ahora constancias desde apps_devs
    conn_apps = get_mysql_conn_apps_devs()
    cursor_apps = conn_apps.cursor(dictionary=True)
    cursor_apps.execute("""
        SELECT id, fecha_emision, salario, cargo
        FROM constancias
        WHERE employee_id = %s
        ORDER BY fecha_emision DESC
    """, (employee_id,))
    constancias_raw = cursor_apps.fetchall()
    conn_apps.close()

    constancias = [{
        'id': c['id'],
        'fecha_emision': c['fecha_emision'].strftime('%d/%m/%Y') if c['fecha_emision'] else '',
        'salario': float(c['salario']) if c['salario'] is not None else 0,
        'cargo': c['cargo']
    } for c in constancias_raw]

    conn_mysql.close()

    return render_template('dashboard.html',
                           recibos=recibos,
                           employee_id=employee_id,
                           nombre_empleado=nombre_empleado,
                           constancias=constancias,
                           portal_nombre=os.getenv("PORTAL_NOMBRE", "Mi Portal por Defecto"),
                           vacaciones_asignados=dias_vac_asignados,
                           vacaciones_usados=dias_vac_usados,
                           vacaciones_disponibles=dias_vac_disponibles,
                           vacaciones_tomadas=vacaciones_tomadas)
    
    
    # Envia los datos al recibo_detalle

@app.route('/recibo/<path:slip_id>')
def ver_recibo(slip_id):
    if 'employee_id' not in session:
        return redirect(url_for('login'))

    conn = get_mysql_conn_erpnext()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT name, start_date, end_date, net_pay, employee_name, employee, department, designation, branch, leave_without_pay,
               payment_days, bank_name, bank_account_no
        FROM `tabSalary Slip`
        WHERE name = %s
    """, (slip_id,))
    recibo = cursor.fetchone()

    if not recibo:
        conn.close()
        return "Recibo no encontrado", 404

    cursor.execute("SELECT image FROM `tabEmployee` WHERE name = %s", (recibo['employee'],))
    foto = cursor.fetchone()
    recibo['image'] = foto['image'] if foto and 'image' in foto else None

    cursor.execute("SELECT date_of_joining FROM `tabEmployee` WHERE name = %s", (recibo['employee'],))
    fecha = cursor.fetchone()
    recibo['date_of_joining'] = fecha['date_of_joining'] if fecha and 'date_of_joining' in fecha else None

    cursor.execute("""
        SELECT sd.salary_component, sd.amount, sd.parentfield
        FROM `tabSalary Detail` sd
        WHERE sd.parent = %s
    """, (slip_id,))
    filas = cursor.fetchall()
    conn.close()

    exclude_components = ['INFOP', 'IHSS-PATRONAL-QUINCENAL', 'RAP-RESERVA-QUINCENAL', 'RAP-PAT']

    ingresos_filtrados = [f for f in filas if f['parentfield'] == 'earnings' and f['salary_component'] not in exclude_components]
    deducciones = [f for f in filas if f['parentfield'] == 'deductions']

    total_ingresos_filtrados = sum(float(f['amount']) for f in ingresos_filtrados)

    return render_template('recibo_detalle.html',
                           recibo=recibo,
                           ingresos=ingresos_filtrados,
                           deducciones=deducciones,
                           total_ingresos=total_ingresos_filtrados)

# Similar cambios para las rutas que usen constancias y employee_auth:

@app.route('/api/verificar_limite_constancias', methods=['POST'])
def verificar_limite_constancias():
    if 'employee_id' not in session:
        return jsonify({"permitido": False, "mensaje": "No autenticado"}), 401

    employee_id = session['employee_id']

    conn = get_mysql_conn_apps_devs()  # apps_devs
    cursor = conn.cursor()

    hoy = datetime.now()
    primer_dia_mes = hoy.replace(day=1)

    cursor.execute("""
        SELECT COUNT(*) FROM constancias
        WHERE employee_id = %s AND fecha_emision >= %s AND fecha_emision <= %s
    """, (employee_id, primer_dia_mes, hoy))

    count = cursor.fetchone()[0]
    conn.close()

    if count >= 2:
        return jsonify({"permitido": False, "mensaje": "Ha alcanzado el límite de 2 constancias mensuales."})
    else:
        return jsonify({"permitido": True})

@app.route('/constancia/<path:slip_id>')
def generar_constancia(slip_id):
    if 'employee_id' not in session:
        return redirect(url_for('login'))

    empleado_id = session['employee_id']

    # Verificar límite mensual de constancias
    conn = get_mysql_conn_apps_devs()  # apps_devs
    cursor = conn.cursor()
    hoy = datetime.now()
    primer_dia_mes = hoy.replace(day=1)
    cursor.execute("""
        SELECT COUNT(*) FROM constancias
        WHERE employee_id = %s AND fecha_emision >= %s AND fecha_emision <= %s
    """, (empleado_id, primer_dia_mes, hoy))
    constancias_mes = cursor.fetchone()[0]

    if constancias_mes >= 2:
        conn.close()
        return "Límite de 2 constancias mensuales alcanzado.", 403

    # Obtener datos del recibo y empleado desde ERPNext
    conn_erp = get_mysql_conn_erpnext()  # test_erpnext
    cursor_erp = conn_erp.cursor()
    cursor_erp.execute("""
        SELECT ss.name, ss.start_date, ss.end_date, ss.employee_name, ss.employee, ss.designation
        FROM `tabSalary Slip` ss
        WHERE ss.name = %s
    """, (slip_id,))
    recibo = cursor_erp.fetchone()

    if not recibo:
        conn_erp.close()
        conn.close()
        return "Recibo no encontrado", 404

    cursor_erp.execute("SELECT date_of_joining, tax_id FROM `tabEmployee` WHERE name = %s", (recibo[4],))
    emp_data = cursor_erp.fetchone()
    fecha_ingreso = emp_data[0] if emp_data and emp_data[0] else None
    identidad = emp_data[1] if emp_data and emp_data[1] else "No registrado"

    # Descomponer fecha_ingreso en día, mes y año
    if fecha_ingreso:
        dia_ingreso = fecha_ingreso.day
        meses_es = {
            1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
            5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
            9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
        }
        mes_ingreso = meses_es[fecha_ingreso.month]
        anio_ingreso = fecha_ingreso.year
    else:
        dia_ingreso = None
        mes_ingreso = None
        anio_ingreso = None

    cursor_erp.execute("""
        SELECT amount
        FROM `tabSalary Detail`
        WHERE parent = %s AND parentfield = 'earnings' AND salary_component = 'Base'
    """, (slip_id,))
    salario_row = cursor_erp.fetchone()
    salario = float(salario_row[0]) if salario_row and salario_row[0] else 0

    cursor_erp.execute("""
        SELECT salary_component, amount
        FROM `tabSalary Detail`
        WHERE parent = %s AND parentfield = 'deductions'
    """, (slip_id,))
    deducciones = cursor_erp.fetchall()
    conn_erp.close()

    componentes_a_omitir = ['IHSS_PROV_Q', 'INFOP PROVISIONES', 'RAP-EMP', 'RAP-PAT-PROVISION', 'RAP-PROVISION-QUINCENAL']
    deducciones_filtradas = [
        {'salary_component': d[0], 'amount': float(d[1]) if d[1] else 0}
        for d in deducciones if d[0] not in componentes_a_omitir
    ]
    total_deducciones = sum(d['amount'] for d in deducciones_filtradas)

    # Leer logo base64
    logo_path = os.path.join(app.root_path, 'static', 'image', 'logo_lk.png')
    with open(logo_path, "rb") as image_file:
        logo_base64 = base64.b64encode(image_file.read()).decode('utf-8')

    # Leer firma base64
    firma_path = os.path.join(app.root_path, 'static', 'image', 'firma.png')
    with open(firma_path, "rb") as firma_file:
        firma_base64 = base64.b64encode(firma_file.read()).decode('utf-8')

    fecha_actual = datetime.now()
    dia = fecha_actual.day
    meses_es = {
        1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
        5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
        9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
    }
    mes = meses_es[fecha_actual.month]
    anio = fecha_actual.year

    html = render_template(
        "constancia.html",
        nombre=recibo[3],
        identidad=identidad,
        fecha_ingreso=fecha_ingreso.strftime('%d/%m/%Y') if fecha_ingreso else '',
        dia_ingreso=dia_ingreso,
        mes_ingreso=mes_ingreso,
        anio_ingreso=anio_ingreso,
        salario=salario,
        cargo=recibo[5],
        deducciones=deducciones_filtradas,
        total_deducciones=total_deducciones,
        fecha_emision=datetime.now().strftime('%d/%m/%Y'),
        dia=dia,
        mes=mes,
        anio=anio,
        logo_base64=logo_base64,
        firma_base64=firma_base64
    )

    pdf_buffer = BytesIO()
    resultado = pisa.CreatePDF(html, dest=pdf_buffer)
    if resultado.err:
        return "Error al generar PDF", 500
    pdf_buffer.seek(0)
    pdf_contenido = pdf_buffer.getvalue()

    membrete_path = os.path.join(app.root_path, 'static', 'membrete.pdf')
    pdf_final = combinar_pdf_con_membrete(membrete_path, pdf_contenido)

    # Guardar constancia en apps_devs
    cursor.execute("""
        INSERT INTO constancias (
            employee_id, fecha_ingreso, cargo, salario, deducciones, fecha_emision, pdf
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (
        empleado_id,
        fecha_ingreso,
        recibo[5],
        salario,
        json.dumps(deducciones_filtradas, ensure_ascii=False),
        datetime.now().date(),
        pdf_final
    ))
    conn.commit()
    conn.close()

    response = make_response(pdf_final)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=constancia_{slip_id}.pdf'
    return response

@app.route('/descargar_constancia/<int:constancia_id>')
def descargar_constancia(constancia_id):
    if 'employee_id' not in session:
        return redirect(url_for('login'))

    conn = get_mysql_conn_apps_devs()  # apps_devs
    cursor = conn.cursor()
    cursor.execute("""
        SELECT pdf
        FROM constancias
        WHERE id = %s AND employee_id = %s
    """, (constancia_id, session['employee_id']))
    fila = cursor.fetchone()
    conn.close()

    if not fila:
        return "Constancia no encontrada", 404

    pdf_data = fila[0]
    response = make_response(pdf_data)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=constancia_{constancia_id}.pdf'
    return response

@app.route('/vacaciones')
def vacaciones():
    if 'employee_id' not in session:
        return redirect(url_for('login'))

    employee_id = session['employee_id']
    conn = get_mysql_conn_erpnext()  # test_erpnext
    cursor = conn.cursor(dictionary=True)

    query_detalle = """
        SELECT 
            employee_name AS empleado,
            leave_type AS tipo,
            from_date AS fecha_inicio,
            to_date AS fecha_final,
            total_leave_days AS dias_tomados
        FROM `tabLeave Application`
        WHERE employee = %s
        ORDER BY from_date ASC
    """

    cursor.execute(query_detalle, (employee_id,))
    detalle_vacaciones = cursor.fetchall()

    for d in detalle_vacaciones:
        d['fecha_inicio'] = datetime.strptime(str(d['fecha_inicio']), "%Y-%m-%d")
        d['fecha_final'] = datetime.strptime(str(d['fecha_final']), "%Y-%m-%d")
        try:
            d['dias_tomados'] = float(d['dias_tomados'])
        except (TypeError, ValueError):
            d['dias_tomados'] = 0.0

    agrupado_por_anio = defaultdict(lambda: {'registros': [], 'total_dias': 0.0})

    for d in detalle_vacaciones:
        anio = d['fecha_inicio'].year
        agrupado_por_anio[anio]['registros'].append(d)
        agrupado_por_anio[anio]['total_dias'] += d['dias_tomados']

    conn.close()

    return render_template('vacaciones.html', agrupado_por_anio=agrupado_por_anio)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

