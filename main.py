from datetime import datetime
import sqlite3
import flet as ft
import sys
import os

# مسار قاعدة البيانات: على الموبايل (أندرويد/iOS) لازم نخزن الملف في مجلد
# بيانات التطبيق الدائم (FLET_APP_STORAGE_DATA) عشان يفضل موجود بعد إغلاق
# التطبيق وبعد التحديثات. على الكمبيوتر وقت التطوير المتغير ده مش موجود
# فبيرجع المسار النسبي زي ما كان.
def get_db_path():
    data_dir = os.environ.get("FLET_APP_STORAGE_DATA")
    if data_dir:
        # المجلد ده لازم يكون موجود فعليًا قبل ما نفتح ملف جواه، وإلا sqlite
        # هيرفض الاتصال بصمت ويوقع التطبيق قبل ما تظهر أي واجهة
        os.makedirs(data_dir, exist_ok=True)
        return os.path.join(data_dir, "students.db")
    return "students.db"

DB_PATH = get_db_path()

# ============================================================
# 1. قاعدة البيانات
# ============================================================
class Database:
    @staticmethod
    def init_db():
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # جدول الطلاب
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS students (
                code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                phone TEXT,
                whatsapp TEXT,
                grade TEXT NOT NULL,
                group_days TEXT NOT NULL,
                lesson_time TEXT NOT NULL,
                location TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # جدول المدفوعات
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_code TEXT,
                month TEXT NOT NULL,
                year INTEGER NOT NULL,
                amount REAL NOT NULL,
                paid BOOLEAN DEFAULT 0,
                payment_date TIMESTAMP,
                notes TEXT,
                FOREIGN KEY (student_code) REFERENCES students(code),
                UNIQUE(student_code, month, year)
            )
        """)

        # جدول الحضور والانصراف
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_code TEXT NOT NULL,
                date TEXT NOT NULL,
                status TEXT NOT NULL,
                time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_code) REFERENCES students(code),
                UNIQUE(student_code, date)
            )
        """)
        
        conn.commit()
        conn.close()

# ============================================================
# 2. التطبيق الرئيسي
# ============================================================
def main(page: ft.Page):
    # بننشئ جداول قاعدة البيانات هنا (جوه main) مش في أعلى الملف، عشان لو
    # حصل أي خطأ، فليت يقدر يعرضه كرسالة على الشاشة بدل ما يقفل التطبيق
    # بصمت وتفضل شاشة بيضا فاضية
    try:
        Database.init_db()
    except Exception as err:
        page.add(ft.Text(f"خطأ في تجهيز قاعدة البيانات: {err}", color="red", size=16))
        page.update()
        return

    page.title = "Hosam_Lecons"
    page.rtl = True
    page.bgcolor = "#0A0A0F"
    page.padding = 15
    page.theme_mode = ft.ThemeMode.DARK  # تحديد الوضع الافتراضي صراحة حتى يعمل زر التبديل من أول ضغطة

    # دعم النسختين القديمة والحديثة من Flet لأبعاد النافذة
    try:
        page.window.width = 1000
        page.window.height = 750
    except Exception:
        page.window_width = 1000
        page.window_height = 750

    page.scroll = ft.ScrollMode.ALWAYS # تفعيل التمرير العام للتطبيق بكامله
    
    current_screen = "main"
    
    COLORS = {
        'gold': '#D4AF37',
        'gold_light': '#F0D060',
        'primary': '#1A1A2E',
        'primary_light': '#2A2A4E',
        'secondary': '#8B0000',
        'secondary_light': '#CC0000',
        'text': '#D4AF37',
        'text_secondary': '#C0A060',
        'text_muted': '#8A7A4A',
        'background': '#0A0A0F',
        'card': '#1A1A2E',
        'success': '#2ECC71',
        'danger': '#E74C3C',
    }

    # خريطة أيام الأسبوع -> المجموعة، مشتركة بين شاشة الجدول وشاشة الحضور
    # (Monday=0 ... Sunday=6 حسب weekday() في بايثون)
    DAY_TO_GROUP = {
        0: "الإثنين والخميس",   # الإثنين
        1: "السبت والثلاثاء",   # الثلاثاء
        2: "الأحد والأربعاء",   # الأربعاء
        3: "الإثنين والخميس",   # الخميس
        5: "السبت والثلاثاء",   # السبت
        6: "الأحد والأربعاء",   # الأحد
        # الجمعة (4) غير موجودة = لا توجد دروس
    }
    GROUP_OPTIONS = ["السبت والثلاثاء", "الأحد والأربعاء", "الإثنين والخميس"]

    MONTHS_AR = {
        "01": "يناير", "02": "فبراير", "03": "مارس", "04": "أبريل",
        "05": "مايو", "06": "يونيو", "07": "يوليو", "08": "أغسطس",
        "09": "سبتمبر", "10": "أكتوبر", "11": "نوفمبر", "12": "ديسمبر"
    }

    def get_group_for_date(date_str):
        """يرجع اسم المجموعة المفروض إنها بتاخد درس في هذا التاريخ، أو رسالة لو مفيش دروس."""
        try:
            dt = datetime.strptime((date_str or "").strip(), "%Y-%m-%d")
        except ValueError:
            dt = datetime.now()
        return DAY_TO_GROUP.get(dt.weekday(), "لا توجد دروس في هذا اليوم")
    
    is_edit_mode = False
    current_code = ""
    current_profile_code = ""
    
    def open_dialog_safe(dialog):
        try:
            page.open(dialog)
        except Exception:
            page.dialog = dialog
            dialog.open = True
            page.update()

    def close_dialog_safe(dialog):
        try:
            page.close(dialog)
        except Exception:
            dialog.open = False
            page.update()

    def create_dropdown_option(key_val, text_val):
        return ft.dropdown.Option(
            key=key_val,
            content=ft.Text(text_val, color=COLORS['gold'], size=15, weight=ft.FontWeight.BOLD)
        )
    
    def show_snackbar(message, is_error=False):
        snack_bar = ft.SnackBar(
            content=ft.Text(message, color="#FFFFFF" if is_error else COLORS['gold']),
            bgcolor=COLORS['secondary'] if is_error else COLORS['primary'],
            duration=3000,
        )
        try:
            page.open(snack_bar)
        except Exception:
            page.snack_bar = snack_bar
            page.snack_bar.open = True
            page.update()
    
    def exit_app(e):
        def confirm_exit(confirm_e):
            close_dialog_safe(dialog)
            if confirm_e == "yes":
                try:
                    page.window.close()
                except Exception:
                    try:
                        page.window_close()
                    except Exception:
                        try:
                            page.window.destroy()
                        except Exception:
                            sys.exit(0)
        
        dialog = ft.AlertDialog(
            title=ft.Text("تأكيد الخروج", color=COLORS['gold']),
            content=ft.Text("هل أنت متأكد من الخروج من التطبيق؟", color=COLORS['text']),
            actions=[
                ft.TextButton("نعم", on_click=lambda e: confirm_exit("yes")),
                ft.TextButton("لا", on_click=lambda e: confirm_exit("no")),
            ],
            bgcolor=COLORS['card'],
        )
        open_dialog_safe(dialog)
    
    # ============================================================
    # 3. الشاشة الرئيسية
    # ============================================================
    def show_main(e=None):
        nonlocal current_screen
        current_screen = "main"
        page.controls.clear()
        
        logo = ft.Column([
            ft.Text(
                "Hosam_Lecons",
                size=50,
                weight=ft.FontWeight.BOLD,
                color=COLORS['gold'],
                text_align=ft.TextAlign.CENTER,
            ),
            ft.Container(
                width=280,
                height=3,
                bgcolor=COLORS['gold'],
                margin=ft.margin.only(top=5, bottom=5),
            ),
            ft.Text(
                "نظام إدارة الطلاب والدروس والمدفوعات والحضور",
                size=16,
                color=COLORS['text_secondary'],
                text_align=ft.TextAlign.CENTER,
            ),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=5)
        
        def create_main_btn(text, color, click_func):
            return ft.Container(
                content=ft.Text(text, size=22, weight=ft.FontWeight.BOLD, color=COLORS['gold']),
                width=380,
                height=55,
                alignment=ft.alignment.center,
                bgcolor=color,
                border=ft.border.all(2, COLORS['gold']),
                border_radius=12,
                on_click=click_func,
                ink=True,
            )
        
        btn_students = create_main_btn("إدارة الطلاب", COLORS['primary'], lambda e: show_students())
        btn_attendance = create_main_btn("تسجيل الحضور والغياب", COLORS['primary'], lambda e: show_attendance())
        btn_schedule = create_main_btn("جدول الدروس", COLORS['primary'], lambda e: show_schedule())
        btn_payments = create_main_btn("المدفوعات الشهرية", COLORS['primary'], lambda e: show_payments())

        main_buttons = [btn_students, btn_attendance, btn_schedule, btn_payments]

        # زرار "خروج" مالوش معنى على الموبايل (مفيش مفهوم "إغلاق نافذة" زي سطح المكتب)
        is_mobile_platform = str(getattr(page, "platform", "")).lower() in ("android", "ios")
        if not is_mobile_platform:
            btn_exit = create_main_btn("خروج", COLORS['secondary'], exit_app)
            main_buttons.append(btn_exit)
        
        theme_btn = ft.Container(
            content=ft.Text("◐", size=28, color=COLORS['gold']),
            on_click=lambda e: toggle_theme(),
            padding=10,
            tooltip="تبديل الوضع",
        )
        
        page.add(
            ft.Container(
                content=ft.Column([
                    ft.Row([theme_btn], alignment=ft.MainAxisAlignment.END),
                    logo,
                    ft.Container(height=15),
                    *main_buttons,
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=12),
                padding=20,
            )
        )
        page.update()
    
    # ============================================================
    # 4. شاشة إدارة الطلاب (مع تعديل العرض والتمرير)
    # ============================================================
    def show_students():
        nonlocal is_edit_mode, current_code, current_screen
        current_screen = "students"
        is_edit_mode = False
        current_code = ""
        
        page.controls.clear()
        
        back_btn = ft.Container(
            content=ft.Text("العودة", size=18, weight=ft.FontWeight.BOLD, color=COLORS['gold']),
            padding=ft.padding.symmetric(horizontal=20, vertical=10),
            bgcolor=COLORS['primary'],
            border=ft.border.all(2, COLORS['gold']),
            border_radius=8,
            on_click=lambda e: show_main(),
            ink=True,
        )
        
        title = ft.Text("إدارة الطلاب", size=30, weight=ft.FontWeight.BOLD, color=COLORS['gold'])
        
        input_style = {
            "border_color": COLORS['gold'],
            "focused_border_color": COLORS['gold_light'],
            "border_radius": 10,
            "bgcolor": COLORS['primary'],
            "text_size": 15,
            "color": COLORS['gold'],
            "focused_color": COLORS['gold_light'],
            "label_style": ft.TextStyle(color=COLORS['text_secondary']),
        }
        
        code = ft.TextField(label="كود الطالب", expand=True, max_length=10, **input_style)
        name = ft.TextField(label="اسم الطالب", expand=True, max_length=50, **input_style)
        phone = ft.TextField(label="رقم الموبايل", expand=True, max_length=15, **input_style)
        whatsapp = ft.TextField(label="رقم الواتساب", expand=True, max_length=15, **input_style)
        
        grade_options = ["3 ب", "4 ب", "5 ب", "6 ب", "أولى ع", "ثانية ع", "ثالثة ع", "أولى ثانوي"]
        grade = ft.Dropdown(
            label="الصف الدراسي",
            options=[create_dropdown_option(g, g) for g in grade_options],
            expand=True,
            **input_style
        )
        
        group_options = ["السبت والثلاثاء", "الأحد والأربعاء", "الإثنين والخميس"]
        group = ft.Dropdown(
            label="المجموعة",
            options=[create_dropdown_option(g, g) for g in group_options],
            expand=True,
            **input_style
        )
        
        time_options = ["03:00 مساءً", "04:00 مساءً", "05:00 مساءً", "06:00 مساءً", "07:00 مساءً", "08:00 مساءً"]
        lesson_time = ft.Dropdown(
            label="الساعة",
            options=[create_dropdown_option(t, t) for t in time_options],
            expand=True,
            **input_style
        )
        
        location = ft.TextField(label="المكان", expand=True, max_length=50, **input_style)
        
        search_input = ft.TextField(
            label="بحث بالكود أو الاسم",
            expand=True,
            on_change=lambda e: load_students(),
            **input_style
        )
        
        students_table = ft.DataTable(
            heading_row_color=COLORS['primary_light'],
            heading_text_style=ft.TextStyle(weight=ft.FontWeight.BOLD, color=COLORS['gold']),
            columns=[
                ft.DataColumn(ft.Text("الكود", color=COLORS['gold'])),
                ft.DataColumn(ft.Text("الاسم", color=COLORS['gold'])),
                ft.DataColumn(ft.Text("الهاتف", color=COLORS['gold'])),
                ft.DataColumn(ft.Text("الصف", color=COLORS['gold'])),
                ft.DataColumn(ft.Text("المجموعة", color=COLORS['gold'])),
                ft.DataColumn(ft.Text("الساعة", color=COLORS['gold'])),
                ft.DataColumn(ft.Text("المكان", color=COLORS['gold'])),
                ft.DataColumn(ft.Text("الملف", color=COLORS['gold'])),
                ft.DataColumn(ft.Text("تعديل", color=COLORS['gold'])),
                ft.DataColumn(ft.Text("حذف", color=COLORS['gold'])),
            ],
            rows=[],
            column_spacing=15,
            expand=True,
            heading_row_height=45,
            border=ft.border.all(1, COLORS['gold']),
        )
        
        def load_students():
            students_table.rows.clear()
            search = search_input.value.strip() if search_input.value else ""

            try:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()

                if search:
                    cursor.execute("""
                        SELECT code, name, phone, whatsapp, grade, group_days, lesson_time, location, created_at
                        FROM students 
                        WHERE code LIKE ? OR name LIKE ? 
                        ORDER BY name ASC
                    """, (f"%{search}%", f"%{search}%"))
                else:
                    cursor.execute("""
                        SELECT code, name, phone, whatsapp, grade, group_days, lesson_time, location, created_at
                        FROM students ORDER BY name ASC
                    """)

                records = cursor.fetchall()
            except Exception as err:
                show_snackbar(f"خطأ أثناء تحميل بيانات الطلاب: {err}", is_error=True)
                page.update()
                return
            finally:
                conn.close()

            for r in records:
                profile_btn = ft.OutlinedButton(
                    content=ft.Text("عرض الملف", size=13, color=COLORS['gold']),
                    style=ft.ButtonStyle(
                        bgcolor=COLORS['primary'],
                        side=ft.BorderSide(1, COLORS['gold']),
                        shape=ft.RoundedRectangleBorder(radius=5),
                    ),
                    on_click=lambda e, code=r[0]: show_student_profile(code),
                )

                edit_btn = ft.OutlinedButton(
                    content=ft.Text("تعديل", size=13, color=COLORS['gold']),
                    style=ft.ButtonStyle(
                        bgcolor=COLORS['primary'],
                        side=ft.BorderSide(1, COLORS['gold']),
                        shape=ft.RoundedRectangleBorder(radius=5),
                    ),
                    on_click=lambda e, row=r: select_student(row),
                )
                
                delete_btn = ft.OutlinedButton(
                    content=ft.Text("حذف", size=13, color=COLORS['gold']),
                    style=ft.ButtonStyle(
                        bgcolor=COLORS['secondary'],
                        side=ft.BorderSide(1, COLORS['gold']),
                        shape=ft.RoundedRectangleBorder(radius=5),
                    ),
                    on_click=lambda e, code=r[0]: delete_student(code),
                )
                
                students_table.rows.append(
                    ft.DataRow(cells=[
                        ft.DataCell(ft.Text(str(r[0]), color=COLORS['text'])),
                        ft.DataCell(ft.Text(str(r[1]), color=COLORS['text'])),
                        ft.DataCell(ft.Text(str(r[2]) if r[2] else "-", color=COLORS['text_secondary'])),
                        ft.DataCell(ft.Text(str(r[4]), color=COLORS['text'])),
                        ft.DataCell(ft.Text(str(r[5]), color=COLORS['text'])),
                        ft.DataCell(ft.Text(str(r[6]), color=COLORS['text'])),
                        ft.DataCell(ft.Text(str(r[7]), color=COLORS['text'])),
                        ft.DataCell(profile_btn),
                        ft.DataCell(edit_btn),
                        ft.DataCell(delete_btn),
                    ])
                )
            page.update()
        
        def clear_fields():
            nonlocal is_edit_mode, current_code
            code.value = ""
            name.value = ""
            phone.value = ""
            whatsapp.value = ""
            grade.value = None
            group.value = None
            lesson_time.value = None
            location.value = ""
            code.disabled = False
            is_edit_mode = False
            current_code = ""
            page.update()
        
        def select_student(row):
            nonlocal is_edit_mode, current_code
            code.value = str(row[0])
            name.value = str(row[1])
            phone.value = str(row[2]) if row[2] else ""
            whatsapp.value = str(row[3]) if row[3] else ""
            grade.value = str(row[4])
            group.value = str(row[5])
            lesson_time.value = str(row[6])
            location.value = str(row[7])
            code.disabled = True
            is_edit_mode = True
            current_code = str(row[0])
            page.update()
        
        def delete_student(student_code):
            def confirm_del(confirm_e):
                close_dialog_safe(dialog)
                if confirm_e == "yes":
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM students WHERE code = ?", (student_code,))
                    cursor.execute("DELETE FROM payments WHERE student_code = ?", (student_code,))
                    cursor.execute("DELETE FROM attendance WHERE student_code = ?", (student_code,))
                    conn.commit()
                    conn.close()
                    show_snackbar("تم حذف الطالب بنجاح")
                    clear_fields()
                    load_students()
            
            dialog = ft.AlertDialog(
                title=ft.Text("تأكيد الحذف", color=COLORS['gold']),
                content=ft.Text("هل أنت متأكد من حذف الطالب؟", color=COLORS['text']),
                actions=[
                    ft.TextButton("نعم", on_click=lambda e: confirm_del("yes")),
                    ft.TextButton("لا", on_click=lambda e: confirm_del("no")),
                ],
                bgcolor=COLORS['card'],
            )
            open_dialog_safe(dialog)
        
        def save_student(e):
            nonlocal is_edit_mode, current_code
            if not all([code.value, name.value, grade.value, group.value, lesson_time.value, location.value]):
                show_snackbar("يرجى ملء جميع الحقول المطلوبة!", is_error=True)
                return
            
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            try:
                if is_edit_mode:
                    cursor.execute("""
                        UPDATE students 
                        SET name=?, phone=?, whatsapp=?, grade=?, 
                            group_days=?, lesson_time=?, location=?
                        WHERE code=?
                    """, (
                        name.value.strip(),
                        phone.value.strip() if phone.value else "",
                        whatsapp.value.strip() if whatsapp.value else "",
                        grade.value,
                        group.value,
                        lesson_time.value,
                        location.value.strip(),
                        current_code
                    ))
                    show_snackbar("تم تحديث بيانات الطالب بنجاح")
                else:
                    cursor.execute("""
                        INSERT INTO students 
                        (code, name, phone, whatsapp, grade, group_days, lesson_time, location)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        code.value.strip(),
                        name.value.strip(),
                        phone.value.strip() if phone.value else "",
                        whatsapp.value.strip() if whatsapp.value else "",
                        grade.value,
                        group.value,
                        lesson_time.value,
                        location.value.strip()
                    ))
                    show_snackbar("تم إضافة الطالب بنجاح")
                
                conn.commit()
                clear_fields()
                load_students()
            except sqlite3.IntegrityError:
                show_snackbar("كود الطالب موجود مسبقاً!", is_error=True)
            except Exception as err:
                show_snackbar(f"خطأ: {err}", is_error=True)
            finally:
                conn.close()
        
        def create_action_btn(text, color, click_func):
            return ft.Container(
                content=ft.Text(text, size=18, weight=ft.FontWeight.BOLD, color=COLORS['gold']),
                padding=ft.padding.symmetric(horizontal=25, vertical=12),
                bgcolor=color,
                border=ft.border.all(2, COLORS['gold']),
                border_radius=8,
                on_click=click_func,
                ink=True,
            )
        
        btn_clear = create_action_btn("مسح الحقول", COLORS['primary'], lambda e: clear_fields())
        btn_save = create_action_btn("حفظ", COLORS['primary'], save_student)
        
        btn_refresh = ft.Container(
            content=ft.Text("⟳", size=24, color=COLORS['gold']),
            padding=10,
            on_click=lambda e: load_students(),
            tooltip="تحديث",
        )
        
        content = ft.Column([
            ft.Row([back_btn, title], alignment=ft.MainAxisAlignment.START, spacing=15),
            ft.Divider(color=COLORS['gold']),
            ft.Row([code, name], spacing=10),
            ft.Row([phone, whatsapp], spacing=10),
            ft.Row([grade, group], spacing=10),
            ft.Row([lesson_time, location], spacing=10),
            ft.Row([btn_clear, btn_save], alignment=ft.MainAxisAlignment.CENTER, spacing=15),
            ft.Divider(color=COLORS['gold']),
            ft.Row([search_input, btn_refresh], spacing=5),
            ft.Container(
                content=ft.Row([students_table], scroll=ft.ScrollMode.AUTO),
                bgcolor=COLORS['card'],
                padding=10,
                border_radius=10,
                border=ft.border.all(1, COLORS['gold']),
            ),
        ], spacing=12)
        
        page.add(content)
        page.update()
        load_students()

    # ============================================================
    # 4.5 ملف الطالب (بيانات + سجل حضور + سجل مدفوعات في مكان واحد)
    # ============================================================
    def show_student_profile(student_code):
        nonlocal current_screen, current_profile_code
        current_screen = "profile"
        current_profile_code = student_code
        page.controls.clear()

        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT code, name, phone, whatsapp, grade, group_days, lesson_time, location
                FROM students WHERE code = ?
            """, (student_code,))
            student = cursor.fetchone()

            cursor.execute("""
                SELECT date, status FROM attendance
                WHERE student_code = ?
                ORDER BY date DESC
            """, (student_code,))
            attendance_records = cursor.fetchall()

            cursor.execute("""
                SELECT month, year, amount, paid, payment_date, notes
                FROM payments
                WHERE student_code = ?
                ORDER BY year DESC, month DESC
            """, (student_code,))
            payment_records = cursor.fetchall()
        except Exception as err:
            show_snackbar(f"خطأ أثناء تحميل ملف الطالب: {err}", is_error=True)
            show_students()
            return
        finally:
            conn.close()

        if not student:
            show_snackbar("الطالب غير موجود!", is_error=True)
            show_students()
            return

        s_code, s_name, s_phone, s_whatsapp, s_grade, s_group, s_time, s_location = student

        back_btn = ft.Container(
            content=ft.Text("العودة لإدارة الطلاب", size=18, weight=ft.FontWeight.BOLD, color=COLORS['gold']),
            padding=ft.padding.symmetric(horizontal=20, vertical=10),
            bgcolor=COLORS['primary'],
            border=ft.border.all(2, COLORS['gold']),
            border_radius=8,
            on_click=lambda e: show_students(),
            ink=True,
        )

        title = ft.Text(f"ملف الطالب: {s_name}", size=28, weight=ft.FontWeight.BOLD, color=COLORS['gold'])

        def info_row(label, value):
            return ft.Row([
                ft.Text(f"{label}:", size=15, color=COLORS['text_secondary'], weight=ft.FontWeight.BOLD),
                ft.Text(value if value else "-", size=15, color=COLORS['text']),
            ], spacing=8)

        info_card = ft.Container(
            content=ft.Column([
                info_row("الكود", s_code),
                info_row("الاسم", s_name),
                info_row("رقم الموبايل", s_phone),
                info_row("رقم الواتساب", s_whatsapp),
                info_row("الصف الدراسي", s_grade),
                info_row("المجموعة", s_group),
                info_row("ساعة الدرس", s_time),
                info_row("المكان", s_location),
            ], spacing=8),
            padding=15,
            bgcolor=COLORS['card'],
            border_radius=10,
            border=ft.border.all(1, COLORS['gold']),
        )

        # إحصائيات الحضور
        present_count = sum(1 for r in attendance_records if r[1] == "حاضر")
        absent_count = sum(1 for r in attendance_records if r[1] == "غائب")
        total_att = len(attendance_records)
        attendance_rate = (present_count / total_att * 100) if total_att > 0 else 0

        # إحصائيات المدفوعات
        paid_months = [p for p in payment_records if p[3]]
        unpaid_months = [p for p in payment_records if not p[3]]
        total_paid_amount = sum(p[2] for p in paid_months) if paid_months else 0

        def stat_box(label, value, color):
            return ft.Container(
                content=ft.Column([
                    ft.Text(str(value), size=22, weight=ft.FontWeight.BOLD, color=color),
                    ft.Text(label, size=13, color=COLORS['text_secondary']),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                padding=12,
                bgcolor=COLORS['card'],
                border_radius=10,
                border=ft.border.all(1, COLORS['gold']),
                width=150,
                alignment=ft.alignment.center,
            )

        stats_row = ft.Row([
            stat_box("أيام حضور", present_count, COLORS['success']),
            stat_box("أيام غياب", absent_count, COLORS['danger']),
            stat_box("نسبة الحضور", f"{attendance_rate:.0f}%", COLORS['gold']),
            stat_box("إجمالي المدفوع", f"{total_paid_amount:.0f} ج.م", COLORS['gold']),
            stat_box("شهور مدفوعة", len(paid_months), COLORS['success']),
            stat_box("شهور غير مدفوعة", len(unpaid_months), COLORS['danger']),
        ], spacing=10, wrap=True)

        # جدول سجل الحضور
        attendance_history_table = ft.DataTable(
            heading_row_color=COLORS['primary_light'],
            heading_text_style=ft.TextStyle(weight=ft.FontWeight.BOLD, color=COLORS['gold']),
            columns=[
                ft.DataColumn(ft.Text("التاريخ", color=COLORS['gold'])),
                ft.DataColumn(ft.Text("الحالة", color=COLORS['gold'])),
            ],
            rows=[],
            column_spacing=15,
            heading_row_height=40,
            border=ft.border.all(1, COLORS['gold']),
        )

        for date_val, status_val in attendance_records:
            status_color = COLORS['success'] if status_val == "حاضر" else (COLORS['danger'] if status_val == "غائب" else COLORS['text_secondary'])
            attendance_history_table.rows.append(
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(str(date_val), color=COLORS['text'])),
                    ft.DataCell(ft.Text(str(status_val), color=status_color, weight=ft.FontWeight.BOLD)),
                ])
            )

        # جدول سجل المدفوعات
        payments_history_table = ft.DataTable(
            heading_row_color=COLORS['primary_light'],
            heading_text_style=ft.TextStyle(weight=ft.FontWeight.BOLD, color=COLORS['gold']),
            columns=[
                ft.DataColumn(ft.Text("الشهر", color=COLORS['gold'])),
                ft.DataColumn(ft.Text("المبلغ (ج.م)", color=COLORS['gold'])),
                ft.DataColumn(ft.Text("الحالة", color=COLORS['gold'])),
                ft.DataColumn(ft.Text("تاريخ الدفع", color=COLORS['gold'])),
            ],
            rows=[],
            column_spacing=15,
            heading_row_height=40,
            border=ft.border.all(1, COLORS['gold']),
        )

        for p_month, p_year, p_amount, p_paid, p_date, p_notes in payment_records:
            status_badge = ft.Container(
                content=ft.Text("مدفوع", size=12, color="white", weight=ft.FontWeight.BOLD),
                bgcolor=COLORS['success'], padding=ft.padding.symmetric(horizontal=10, vertical=4), border_radius=5
            ) if p_paid else ft.Container(
                content=ft.Text("لم يدفع", size=12, color="white", weight=ft.FontWeight.BOLD),
                bgcolor=COLORS['danger'], padding=ft.padding.symmetric(horizontal=10, vertical=4), border_radius=5
            )
            month_label = f"{MONTHS_AR.get(p_month, p_month)} {p_year}"
            paid_date_str = str(p_date)[:10] if p_date else "-"

            payments_history_table.rows.append(
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(month_label, color=COLORS['text'])),
                    ft.DataCell(ft.Text(f"{p_amount:.0f}", color=COLORS['gold'], weight=ft.FontWeight.BOLD)),
                    ft.DataCell(status_badge),
                    ft.DataCell(ft.Text(paid_date_str, color=COLORS['text_secondary'])),
                ])
            )

        no_attendance_msg = ft.Text("لا يوجد سجل حضور بعد لهذا الطالب.", color=COLORS['text_muted'], italic=True)
        no_payments_msg = ft.Text("لا يوجد سجل مدفوعات بعد لهذا الطالب.", color=COLORS['text_muted'], italic=True)

        attendance_section = ft.Column([
            ft.Text("سجل الحضور والغياب", size=20, weight=ft.FontWeight.BOLD, color=COLORS['gold']),
            ft.Container(
                content=ft.Row([attendance_history_table], scroll=ft.ScrollMode.AUTO) if attendance_records else no_attendance_msg,
                padding=10,
                bgcolor=COLORS['card'],
                border_radius=10,
                border=ft.border.all(1, COLORS['gold']),
            ),
        ], spacing=10)

        payments_section = ft.Column([
            ft.Text("سجل المدفوعات", size=20, weight=ft.FontWeight.BOLD, color=COLORS['gold']),
            ft.Container(
                content=ft.Row([payments_history_table], scroll=ft.ScrollMode.AUTO) if payment_records else no_payments_msg,
                padding=10,
                bgcolor=COLORS['card'],
                border_radius=10,
                border=ft.border.all(1, COLORS['gold']),
            ),
        ], spacing=10)

        content = ft.Column([
            ft.Row([back_btn, title], alignment=ft.MainAxisAlignment.START, spacing=15),
            ft.Divider(color=COLORS['gold']),
            info_card,
            ft.Container(height=5),
            stats_row,
            ft.Divider(color=COLORS['gold']),
            attendance_section,
            ft.Container(height=10),
            payments_section,
        ], spacing=12)

        page.add(content)
        page.update()

    # ============================================================
    # 5. شاشة الحضور والانصراف (الميزة الجديدة)
    # ============================================================
    def show_attendance():
        nonlocal current_screen
        current_screen = "attendance"
        page.controls.clear()

        back_btn = ft.Container(
            content=ft.Text("العودة", size=18, weight=ft.FontWeight.BOLD, color=COLORS['gold']),
            padding=ft.padding.symmetric(horizontal=20, vertical=10),
            bgcolor=COLORS['primary'],
            border=ft.border.all(2, COLORS['gold']),
            border_radius=8,
            on_click=lambda e: show_main(),
            ink=True,
        )

        title = ft.Text("تسجيل الحضور والانصراف", size=30, weight=ft.FontWeight.BOLD, color=COLORS['gold'])

        input_style = {
            "border_color": COLORS['gold'],
            "focused_border_color": COLORS['gold_light'],
            "border_radius": 10,
            "bgcolor": COLORS['primary'],
            "text_size": 15,
            "color": COLORS['gold'],
            "focused_color": COLORS['gold_light'],
            "label_style": ft.TextStyle(color=COLORS['text_secondary']),
        }

        today_date = datetime.now().strftime("%Y-%m-%d")

        date_picker_field = ft.TextField(
            label="التاريخ",
            value=today_date,
            width=180,
            on_change=lambda e: on_date_changed(),
            **input_style
        )

        # المجموعة الافتراضية بتتحدد تلقائيًا حسب يوم التاريخ المختار (نفس فكرة شاشة الجدول)
        default_group = get_group_for_date(today_date)
        initial_group_value = default_group if default_group in GROUP_OPTIONS else "الكل"

        group_filter = ft.Dropdown(
            label="المجموعة المعروضة",
            options=[create_dropdown_option("الكل", "الكل")] + [create_dropdown_option(g, g) for g in GROUP_OPTIONS],
            value=initial_group_value,
            width=220,
            on_change=lambda e: load_attendance(),
            **input_style
        )

        group_info = ft.Text(
            f"مجموعة اليوم المحدد تلقائيًا: {default_group}",
            size=14,
            color=COLORS['text_secondary'],
        )

        def on_date_changed():
            # كل ما يتغير التاريخ، نعيد حساب مجموعة اليوم المفروضة تلقائيًا
            new_group = get_group_for_date(date_picker_field.value)
            group_info.value = f"مجموعة اليوم المحدد تلقائيًا: {new_group}"
            group_filter.value = new_group if new_group in GROUP_OPTIONS else "الكل"
            page.update()
            load_attendance()

        quick_code_input = ft.TextField(
            label="مسح الباروكود أو كتابة الكود ثم الضغط Enter",
            expand=True,
            autofocus=True,
            on_submit=lambda e: mark_quick_attendance(),
            **input_style
        )

        attendance_table = ft.DataTable(
            heading_row_color=COLORS['primary_light'],
            heading_text_style=ft.TextStyle(weight=ft.FontWeight.BOLD, color=COLORS['gold']),
            columns=[
                ft.DataColumn(ft.Text("الكود", color=COLORS['gold'])),
                ft.DataColumn(ft.Text("الاسم", color=COLORS['gold'])),
                ft.DataColumn(ft.Text("المجموعة", color=COLORS['gold'])),
                ft.DataColumn(ft.Text("حالة الدفع بالشهر", color=COLORS['gold'])),
                ft.DataColumn(ft.Text("حالة الحضور", color=COLORS['gold'])),
                ft.DataColumn(ft.Text("تسجيل سريع", color=COLORS['gold'])),
            ],
            rows=[],
            column_spacing=15,
            expand=True,
            heading_row_height=45,
            border=ft.border.all(1, COLORS['gold']),
        )

        def mark_quick_attendance():
            c_code = quick_code_input.value.strip()
            if not c_code:
                return

            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM students WHERE code = ?", (c_code,))
            res = cursor.fetchone()

            if res:
                cursor.execute("""
                    INSERT INTO attendance (student_code, date, status)
                    VALUES (?, ?, ?)
                    ON CONFLICT(student_code, date) DO UPDATE SET status='حاضر'
                """, (c_code, date_picker_field.value.strip(), 'حاضر'))
                conn.commit()
                show_snackbar(f"تم تسجيل حضور الطالب: {res[0]}")
                quick_code_input.value = ""
                quick_code_input.focus()
            else:
                show_snackbar("كود الطالب غير موجود!", is_error=True)
            
            conn.close()
            load_attendance()

        def set_status(student_code, status_val):
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO attendance (student_code, date, status)
                VALUES (?, ?, ?)
                ON CONFLICT(student_code, date) DO UPDATE SET status=?
            """, (student_code, date_picker_field.value.strip(), status_val, status_val))
            conn.commit()
            conn.close()
            load_attendance()

        def load_attendance():
            attendance_table.rows.clear()
            sel_date = date_picker_field.value.strip()
            selected_group = group_filter.value if group_filter.value and group_filter.value != "الكل" else None

            # حساب الشهر والسنة بناءً على التاريخ المختار (وليس شهر اليوم دائمًا)
            try:
                sel_dt = datetime.strptime(sel_date, "%Y-%m-%d")
            except ValueError:
                sel_dt = datetime.now()
            sel_month = sel_dt.strftime("%m")
            sel_year = sel_dt.year

            try:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()

                base_query = """
                    SELECT s.code, s.name, s.group_days, a.status, p.paid
                    FROM students s
                    LEFT JOIN attendance a ON s.code = a.student_code AND a.date = ?
                    LEFT JOIN payments p ON s.code = p.student_code AND p.month = ? AND p.year = ?
                """
                params = [sel_date, sel_month, sel_year]

                if selected_group:
                    base_query += " WHERE s.group_days = ? "
                    params.append(selected_group)

                base_query += " ORDER BY s.name ASC"

                cursor.execute(base_query, params)
                records = cursor.fetchall()
            except Exception as err:
                show_snackbar(f"خطأ أثناء تحميل بيانات الحضور: {err}", is_error=True)
                page.update()
                return
            finally:
                conn.close()

            for r in records:
                st_code, st_name, st_group, st_att, st_paid = r
                
                # حالة الدفع
                pay_badge = ft.Container(
                    content=ft.Text("خالص", size=12, color="white", weight=ft.FontWeight.BOLD),
                    bgcolor=COLORS['success'], padding=ft.padding.symmetric(horizontal=8, vertical=3), border_radius=5
                ) if st_paid else ft.Container(
                    content=ft.Text("غير خالص", size=12, color="white", weight=ft.FontWeight.BOLD),
                    bgcolor=COLORS['danger'], padding=ft.padding.symmetric(horizontal=8, vertical=3), border_radius=5
                )

                # حالة الحضور النصية
                att_status_str = st_att if st_att else "غير مسجل"
                att_color = COLORS['success'] if st_att == "حاضر" else (COLORS['danger'] if st_att == "غائب" else COLORS['text_secondary'])

                # أزرار الإجراء السريع
                btn_present = ft.OutlinedButton(
                    content=ft.Text("حاضر", size=12, color=COLORS['gold']),
                    style=ft.ButtonStyle(bgcolor=COLORS['primary']),
                    on_click=lambda e, c=st_code: set_status(c, "حاضر")
                )
                btn_absent = ft.OutlinedButton(
                    content=ft.Text("غائب", size=12, color=COLORS['secondary']),
                    style=ft.ButtonStyle(bgcolor=COLORS['primary']),
                    on_click=lambda e, c=st_code: set_status(c, "غائب")
                )

                attendance_table.rows.append(
                    ft.DataRow(cells=[
                        ft.DataCell(ft.Text(str(st_code), color=COLORS['text'])),
                        ft.DataCell(ft.Text(str(st_name), color=COLORS['text'])),
                        ft.DataCell(ft.Text(str(st_group), color=COLORS['text_secondary'])),
                        ft.DataCell(pay_badge),
                        ft.DataCell(ft.Text(att_status_str, color=att_color, weight=ft.FontWeight.BOLD)),
                        ft.DataCell(ft.Row([btn_present, btn_absent], spacing=5)),
                    ])
                )

            page.update()

        content = ft.Column([
            ft.Row([back_btn, title], alignment=ft.MainAxisAlignment.START, spacing=15),
            ft.Divider(color=COLORS['gold']),
            ft.Row([date_picker_field, group_filter], spacing=10),
            group_info,
            quick_code_input,
            ft.Divider(color=COLORS['gold']),
            ft.Container(
                content=ft.Row([attendance_table], scroll=ft.ScrollMode.AUTO),
                bgcolor=COLORS['card'],
                padding=10,
                border_radius=10,
                border=ft.border.all(1, COLORS['gold']),
            ),
        ], spacing=12)

        page.add(content)
        page.update()
        load_attendance()

    # ============================================================
    # 6. شاشة جدول الدروس
    # ============================================================
    def show_schedule():
        nonlocal current_screen
        current_screen = "schedule"
        page.controls.clear()
        
        back_btn = ft.Container(
            content=ft.Text("العودة", size=18, weight=ft.FontWeight.BOLD, color=COLORS['gold']),
            padding=ft.padding.symmetric(horizontal=20, vertical=10),
            bgcolor=COLORS['primary'],
            border=ft.border.all(2, COLORS['gold']),
            border_radius=8,
            on_click=lambda e: show_main(),
            ink=True,
        )
        
        title = ft.Text("جدول الدروس اليومي", size=30, weight=ft.FontWeight.BOLD, color=COLORS['gold'])
        
        current_group = get_group_for_date(datetime.now().strftime("%Y-%m-%d"))
        
        day_info = ft.Text(
            f"مجموعة اليوم تلقائياً: {current_group}",
            size=18,
            weight=ft.FontWeight.BOLD,
            color=COLORS['gold'],
        )
        
        schedule_table = ft.DataTable(
            heading_row_color=COLORS['primary_light'],
            heading_text_style=ft.TextStyle(weight=ft.FontWeight.BOLD, color=COLORS['gold']),
            columns=[
                ft.DataColumn(ft.Text("الكود", color=COLORS['gold'])),
                ft.DataColumn(ft.Text("الاسم", color=COLORS['gold'])),
                ft.DataColumn(ft.Text("الصف", color=COLORS['gold'])),
                ft.DataColumn(ft.Text("الساعة", color=COLORS['gold'])),
                ft.DataColumn(ft.Text("المكان", color=COLORS['gold'])),
                ft.DataColumn(ft.Text("اتصال", color=COLORS['gold'])),
                ft.DataColumn(ft.Text("واتساب", color=COLORS['gold'])),
            ],
            rows=[],
            column_spacing=15,
            expand=True,
            heading_row_height=45,
            border=ft.border.all(1, COLORS['gold']),
        )
        
        def open_link(url):
            try:
                page.launch_url(url)
            except Exception as err:
                show_snackbar(f"تعذر فتح الرابط: {err}", is_error=True)

        def load_schedule():
            schedule_table.rows.clear()

            try:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT code, name, phone, whatsapp, grade, lesson_time, location
                    FROM students 
                    WHERE group_days = ?
                    ORDER BY lesson_time ASC
                """, (current_group,))
                records = cursor.fetchall()
            except Exception as err:
                show_snackbar(f"خطأ أثناء تحميل جدول الدروس: {err}", is_error=True)
                page.update()
                return
            finally:
                conn.close()

            for r in records:
                p_num = str(r[2]).strip() if r[2] else ""
                w_num = str(r[3]).strip() if r[3] else ""
                
                w_num_formatted = "2" + w_num if w_num.startswith("0") else w_num

                call_btn = ft.OutlinedButton(
                    content=ft.Text("اتصال", size=13, color=COLORS['gold']),
                    style=ft.ButtonStyle(bgcolor=COLORS['primary']),
                    on_click=lambda e, p=p_num: open_link(f"tel:{p}"),
                ) if p_num else ft.Text("-", color=COLORS['text_muted'])
                
                wa_btn = ft.OutlinedButton(
                    content=ft.Text("واتساب", size=13, color=COLORS['gold']),
                    style=ft.ButtonStyle(bgcolor=COLORS['primary']),
                    on_click=lambda e, w=w_num_formatted: open_link(f"https://wa.me/{w}"),
                ) if w_num else ft.Text("-", color=COLORS['text_muted'])
                
                schedule_table.rows.append(
                    ft.DataRow(cells=[
                        ft.DataCell(ft.Text(str(r[0]), color=COLORS['text'])),
                        ft.DataCell(ft.Text(str(r[1]), color=COLORS['text'])),
                        ft.DataCell(ft.Text(str(r[4]), color=COLORS['text'])),
                        ft.DataCell(ft.Text(str(r[5]), color=COLORS['text'])),
                        ft.DataCell(ft.Text(str(r[6]), color=COLORS['text'])),
                        ft.DataCell(call_btn),
                        ft.DataCell(wa_btn),
                    ])
                )
            page.update()
        
        content = ft.Column([
            ft.Row([back_btn, title], alignment=ft.MainAxisAlignment.START, spacing=15),
            ft.Divider(color=COLORS['gold']),
            day_info,
            ft.Divider(color=COLORS['gold']),
            ft.Container(
                content=ft.Row([schedule_table], scroll=ft.ScrollMode.AUTO),
                padding=10,
                bgcolor=COLORS['card'],
                border_radius=10,
                border=ft.border.all(1, COLORS['gold']),
            ),
        ], spacing=15)
        
        page.add(content)
        page.update()
        load_schedule()

    # ============================================================
    # 7. شاشة المدفوعات الشهرية
    # ============================================================
    def show_payments():
        nonlocal current_screen
        current_screen = "payments"
        page.controls.clear()
        
        back_btn = ft.Container(
            content=ft.Text("العودة", size=18, weight=ft.FontWeight.BOLD, color=COLORS['gold']),
            padding=ft.padding.symmetric(horizontal=20, vertical=10),
            bgcolor=COLORS['primary'],
            border=ft.border.all(2, COLORS['gold']),
            border_radius=8,
            on_click=lambda e: show_main(),
            ink=True,
        )
        
        title = ft.Text("المدفوعات الشهرية", size=30, weight=ft.FontWeight.BOLD, color=COLORS['gold'])
        
        input_style = {
            "border_color": COLORS['gold'],
            "focused_border_color": COLORS['gold_light'],
            "border_radius": 10,
            "bgcolor": COLORS['primary'],
            "text_size": 15,
            "color": COLORS['gold'],
            "focused_color": COLORS['gold_light'],
            "label_style": ft.TextStyle(color=COLORS['text_secondary']),
        }
        
        months = MONTHS_AR
        
        current_month = datetime.now().strftime("%m")
        current_year = datetime.now().year
        
        month_filter = ft.Dropdown(
            label="شهر الدفع المستهدف",
            options=[create_dropdown_option(m, label) for m, label in months.items()],
            value=current_month,
            width=180,
            on_change=lambda e: load_payments(),
            **input_style
        )
        
        year_filter = ft.Dropdown(
            label="السنة",
            options=[create_dropdown_option(str(y), str(y)) for y in range(2024, 2028)],
            value=str(current_year),
            width=120,
            on_change=lambda e: load_payments(),
            **input_style
        )
        
        group_filter = ft.Dropdown(
            label="المجموعة",
            options=[
                create_dropdown_option("الكل", "الكل"),
                create_dropdown_option("السبت والثلاثاء", "السبت والثلاثاء"),
                create_dropdown_option("الأحد والأربعاء", "الأحد والأربعاء"),
                create_dropdown_option("الإثنين والخميس", "الإثنين والخميس"),
            ],
            value="الكل",
            width=180,
            on_change=lambda e: load_payments(),
            **input_style
        )
        
        payments_table = ft.DataTable(
            heading_row_color=COLORS['primary_light'],
            heading_text_style=ft.TextStyle(weight=ft.FontWeight.BOLD, color=COLORS['gold']),
            columns=[
                ft.DataColumn(ft.Text("الكود", color=COLORS['gold'])),
                ft.DataColumn(ft.Text("اسم الطالب", color=COLORS['gold'])),
                ft.DataColumn(ft.Text("المجموعة", color=COLORS['gold'])),
                ft.DataColumn(ft.Text("المبلغ (ج.م)", color=COLORS['gold'])),
                ft.DataColumn(ft.Text("الحالة", color=COLORS['gold'])),
                ft.DataColumn(ft.Text("تاريخ التسجيل", color=COLORS['gold'])),
                ft.DataColumn(ft.Text("تسجيل الدفع", color=COLORS['gold'])),
            ],
            rows=[],
            column_spacing=15,
            expand=True,
            heading_row_height=45,
            border=ft.border.all(1, COLORS['gold']),
        )
        
        summary_text = ft.Text("", size=16, color=COLORS['gold'], weight=ft.FontWeight.BOLD)
        
        def load_payments():
            payments_table.rows.clear()
            
            month = month_filter.value
            year = int(year_filter.value)
            group = group_filter.value if group_filter.value != "الكل" else None

            try:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()

                if group:
                    cursor.execute("SELECT code, name, group_days FROM students WHERE group_days = ?", (group,))
                else:
                    cursor.execute("SELECT code, name, group_days FROM students")
                students = cursor.fetchall()

                cursor.execute("""
                    SELECT student_code, amount, paid, payment_date, notes 
                    FROM payments 
                    WHERE month = ? AND year = ?
                """, (month, year))
                payments = {r[0]: r for r in cursor.fetchall()}
            except Exception as err:
                show_snackbar(f"خطأ أثناء تحميل بيانات المدفوعات: {err}", is_error=True)
                page.update()
                return
            finally:
                conn.close()

            total_collected = 0
            paid_count = 0
            
            for s in students:
                payment = payments.get(s[0])
                amount = payment[1] if payment else 0.0
                paid = payment[2] if payment else 0
                paid_date = str(payment[3])[:10] if payment and payment[3] else "-"
                
                if paid:
                    total_collected += amount
                    paid_count += 1
                
                status = ft.Container(
                    content=ft.Text("مدفوع", size=12, color="white", weight=ft.FontWeight.BOLD),
                    bgcolor=COLORS['success'], padding=ft.padding.symmetric(horizontal=10, vertical=4), border_radius=5
                ) if paid else ft.Container(
                    content=ft.Text("لم يدفع", size=12, color="white", weight=ft.FontWeight.BOLD),
                    bgcolor=COLORS['danger'], padding=ft.padding.symmetric(horizontal=10, vertical=4), border_radius=5
                )
                
                edit_btn = ft.OutlinedButton(
                    content=ft.Text("إدخال المبلغ / الدفع", size=13, color=COLORS['gold']),
                    style=ft.ButtonStyle(bgcolor=COLORS['primary']),
                    on_click=lambda e, student_data=s, payment_data=payment: show_payment_dialog(student_data, payment_data),
                )
                
                payments_table.rows.append(
                    ft.DataRow(cells=[
                        ft.DataCell(ft.Text(str(s[0]), color=COLORS['text'])),
                        ft.DataCell(ft.Text(str(s[1]), color=COLORS['text'])),
                        ft.DataCell(ft.Text(str(s[2]), color=COLORS['text_secondary'])),
                        ft.DataCell(ft.Text(f"{amount:.0f} ج.م", color=COLORS['gold'], weight=ft.FontWeight.BOLD)),
                        ft.DataCell(status),
                        ft.DataCell(ft.Text(paid_date, color=COLORS['text_secondary'])),
                        ft.DataCell(edit_btn),
                    ])
                )
            
            summary_text.value = f"إجمالي المحصل لشهر ({months.get(month, month)}): {total_collected:.0f} ج.م | عدد المدفوعين: {paid_count} من {len(students)}"
            page.update()
        
        def show_payment_dialog(student, payment):
            dialog = None
            def close_dialog(e=None):
                if dialog: close_dialog_safe(dialog)

            def save_payment(e):
                try:
                    amount = float(amount_field.value) if amount_field.value else 0.0
                    paid = paid_checkbox.value
                    
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO payments (student_code, month, year, amount, paid, payment_date)
                        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        ON CONFLICT(student_code, month, year) DO UPDATE SET
                            amount=excluded.amount,
                            paid=excluded.paid,
                            payment_date=CURRENT_TIMESTAMP
                    """, (student[0], month_filter.value, int(year_filter.value), amount, 1 if paid else 0))
                    conn.commit()
                    conn.close()
                    
                    close_dialog()
                    show_snackbar("تم حفظ بيانات الدفعة بنجاح")
                    load_payments()
                except ValueError:
                    show_snackbar("يرجى إدخال مبلغ صحيح!", is_error=True)
            
            # نعرض المبلغ كما هو (بدون قطع الكسور العشرية بـ int())
            if payment and payment[1] is not None:
                amt = payment[1]
                current_amount_val = str(int(amt)) if float(amt).is_integer() else f"{amt:.2f}"
            else:
                current_amount_val = "0"

            # الافتراضي لدفعة جديدة يجب أن يكون "لم يُدفع" وليس "مدفوع"
            is_paid_val = bool(payment[2]) if (payment and payment[2] is not None) else False
            
            amount_field = ft.TextField(label="المبلغ المدفوع (ج.م)", value=current_amount_val, keyboard_type=ft.KeyboardType.NUMBER, **input_style)
            paid_checkbox = ft.Checkbox(label="تأكيد تحصيل المبلغ", value=is_paid_val, fill_color=COLORS['gold'])
            
            dialog = ft.AlertDialog(
                title=ft.Text(f"تسجيل دفعة: {student[1]}", color=COLORS['gold']),
                content=ft.Column([
                    ft.Text(f"كود الطالب: {student[0]}", color=COLORS['text_secondary']),
                    amount_field, paid_checkbox,
                ], spacing=12, width=350),
                actions=[
                    ft.TextButton("إلغاء", on_click=close_dialog),
                    ft.TextButton("حفظ", on_click=save_payment),
                ],
                bgcolor=COLORS['card'],
            )
            open_dialog_safe(dialog)
        
        btn_refresh = ft.Container(
            content=ft.Text("⟳", size=24, color=COLORS['gold']),
            padding=10,
            on_click=lambda e: load_payments(),
            tooltip="تحديث",
        )
        
        content = ft.Column([
            ft.Row([back_btn, title], alignment=ft.MainAxisAlignment.START, spacing=15),
            ft.Divider(color=COLORS['gold']),
            ft.Row([month_filter, year_filter, group_filter, btn_refresh], spacing=10),
            summary_text,
            ft.Divider(color=COLORS['gold']),
            ft.Container(
                content=ft.Row([payments_table], scroll=ft.ScrollMode.AUTO),
                padding=10,
                bgcolor=COLORS['card'],
                border_radius=10,
                border=ft.border.all(1, COLORS['gold']),
            ),
        ], spacing=12)
        
        page.add(content)
        page.update()
        load_payments()

    # ============================================================
    # 8. تبديل الوضع (Dark / Light)
    # ============================================================
    def toggle_theme():
        nonlocal current_screen
        if page.theme_mode == ft.ThemeMode.DARK:
            page.theme_mode = ft.ThemeMode.LIGHT
            page.bgcolor = "#F5F0E8"
            COLORS.update({
                'background': '#F5F0E8',
                'card': '#FFFFFF',
                'primary': '#2C1810',
                'primary_light': '#3D2415',
                'text': '#1A1A2E',
                'text_secondary': '#5C4A2A',
                'text_muted': '#8A7A6A',
            })
        else:
            page.theme_mode = ft.ThemeMode.DARK
            page.bgcolor = "#0A0A0F"
            COLORS.update({
                'background': '#0A0A0F',
                'card': '#1A1A2E',
                'primary': '#1A1A2E',
                'primary_light': '#2A2A4E',
                'text': '#D4AF37',
                'text_secondary': '#C0A060',
                'text_muted': '#8A7A4A',
            })
        
        if current_screen == "students":
            show_students()
        elif current_screen == "attendance":
            show_attendance()
        elif current_screen == "schedule":
            show_schedule()
        elif current_screen == "payments":
            show_payments()
        elif current_screen == "profile":
            show_student_profile(current_profile_code)
        else:
            show_main()
            
    show_main()

if __name__ == "__main__":
    ft.app(target=main, port=8550)