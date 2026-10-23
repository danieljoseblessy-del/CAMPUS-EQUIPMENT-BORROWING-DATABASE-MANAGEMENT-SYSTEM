"""
equipment_db.py
Business/data-access layer for Campus Equipment Management System.

All user-controlled values are passed as Oracle bind variables.
"""

from datetime import date, datetime, timedelta
import re
import oracledb
from db_connection import get_connection, get_cursor

FINE_PER_DAY = 50.00
DAMAGE_FEE = 1500.00


def _rows(cur):
    columns = [d[0].lower() for d in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


def get_dashboard_counts():
    with get_cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM STUDENT")
        students = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM EQUIPMENT")
        equipment = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*) FROM EQUIPMENT
            WHERE availability_status = 'AVAILABLE'
        """)
        available = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*) FROM BORROWING_ITEM
            WHERE item_status = 'ISSUED'
        """)
        issued = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*) FROM BORROWING_ITEM
            WHERE item_status = 'ISSUED'
              AND due_date < TRUNC(SYSDATE)
        """)
        overdue = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*) FROM FINE
            WHERE payment_status = 'UNPAID'
        """)
        unpaid_fines = cur.fetchone()[0]

    return {
        "students": students,
        "equipment": equipment,
        "available": available,
        "issued": issued,
        "overdue": overdue,
        "unpaid_fines": unpaid_fines,
    }


def get_departments():
    with get_cursor() as cur:
        cur.execute("""
            SELECT department_id, department_name
            FROM DEPARTMENT
            ORDER BY department_id
        """)
        return _rows(cur)


def get_students():
    with get_cursor() as cur:
        cur.execute("""
            SELECT s.student_id, s.student_name, s.email, s.phone,
                   d.department_name
            FROM STUDENT s
            JOIN DEPARTMENT d ON d.department_id = s.department_id
            ORDER BY s.student_id
        """)
        return _rows(cur)


def insert_student(name, email, phone, department_id):
    name = name.strip()
    email = email.strip()
    phone = phone.strip() or None

    if not name:
        raise ValueError("Student name is required.")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise ValueError("Enter a valid email address.")
    if not department_id:
        raise ValueError("Select a department.")

    with get_cursor(commit=True) as cur:
        out_id = cur.var(oracledb.NUMBER)
        cur.execute("""
            INSERT INTO STUDENT
                (student_name, email, phone, department_id)
            VALUES
                (:name, :email, :phone, :department_id)
            RETURNING student_id INTO :out_id
        """, {
            "name": name,
            "email": email,
            "phone": phone,
            "department_id": int(department_id),
            "out_id": out_id
        })
        return int(out_id.getvalue()[0])


def get_equipment(status="ALL"):
    sql = """
        SELECT e.equipment_id, e.equipment_name, c.category_name,
               e.asset_tag, e.serial_no, e.availability_status,
               e.current_condition
        FROM EQUIPMENT e
        JOIN EQUIPMENT_CATEGORY c ON c.category_id = e.category_id
    """
    params = {}
    if status and status.upper() != "ALL":
        sql += " WHERE e.availability_status = :status"
        params["status"] = status.upper()
    sql += " ORDER BY e.equipment_id"

    with get_cursor() as cur:
        cur.execute(sql, params)
        return _rows(cur)


def get_available_equipment():
    return get_equipment("AVAILABLE")

def update_equipment_condition(
        equipment_id,
        condition_status,
        notes="",
        recorded_by="System Admin"
):
    """
    Update the current condition of an equipment item.

    Allowed conditions:
        EXCELLENT
        GOOD
        FAIR
        DAMAGED
        UNUSABLE

    The change is also recorded in CONDITION_HISTORY.
    """

    allowed = {
        "EXCELLENT",
        "GOOD",
        "FAIR",
        "DAMAGED",
        "UNUSABLE"
    }

    condition_status = condition_status.strip().upper()

    if condition_status not in allowed:
        raise ValueError(
            "Invalid condition. Choose EXCELLENT, GOOD, FAIR, "
            "DAMAGED or UNUSABLE."
        )

    conn = get_connection()
    cur = conn.cursor()

    try:
        # Lock the equipment row before updating it
        cur.execute("""
            SELECT equipment_id,
                   equipment_name,
                   availability_status,
                   current_condition
            FROM EQUIPMENT
            WHERE equipment_id = :equipment_id
            FOR UPDATE
        """, {
            "equipment_id": int(equipment_id)
        })

        row = cur.fetchone()

        if row is None:
            raise ValueError("Equipment ID does not exist.")

        equipment_id_db = row[0]
        equipment_name = row[1]
        old_status = row[2]
        old_condition = row[3]

        # Determine the new availability status
        #
        # DAMAGED / UNUSABLE equipment cannot be available.
        # If a previously DAMAGED item is repaired and given
        # a healthy condition, it becomes AVAILABLE.
        if condition_status in {"DAMAGED", "UNUSABLE"}:
            new_status = "DAMAGED"

        elif old_status == "DAMAGED":
            new_status = "AVAILABLE"

        else:
            # Preserve the existing operational status
            # for BORROWED, RESERVED, MAINTENANCE, etc.
            new_status = old_status

        # Update EQUIPMENT
        cur.execute("""
            UPDATE EQUIPMENT
            SET current_condition = :condition_status,
                availability_status = :availability_status
            WHERE equipment_id = :equipment_id
        """, {
            "condition_status": condition_status,
            "availability_status": new_status,
            "equipment_id": equipment_id_db
        })

        # Record the change in CONDITION_HISTORY
        cur.execute("""
            INSERT INTO CONDITION_HISTORY
                (
                    equipment_id,
                    borrowing_item_id,
                    condition_status,
                    condition_notes,
                    recorded_at,
                    recorded_by
                )
            VALUES
                (
                    :equipment_id,
                    NULL,
                    :condition_status,
                    :condition_notes,
                    SYSTIMESTAMP,
                    :recorded_by
                )
        """, {
            "equipment_id": equipment_id_db,
            "condition_status": condition_status,
            "condition_notes": (
                notes.strip()
                if notes.strip()
                else f"Condition changed from {old_condition} "
                     f"to {condition_status}"
            ),
            "recorded_by": recorded_by
        })

        conn.commit()

        return {
            "equipment_id": equipment_id_db,
            "equipment_name": equipment_name,
            "old_condition": old_condition,
            "new_condition": condition_status,
            "old_status": old_status,
            "new_status": new_status
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()

def get_issued_items():
    with get_cursor() as cur:
        cur.execute("""
            SELECT bi.borrowing_item_id,
                   s.student_name,
                   e.equipment_name,
                   bi.issue_date,
                   bi.due_date,
                   bi.item_status
            FROM BORROWING_ITEM bi
            JOIN BORROWING b ON b.borrowing_id = bi.borrowing_id
            JOIN STUDENT s ON s.student_id = b.student_id
            JOIN EQUIPMENT e ON e.equipment_id = bi.equipment_id
            WHERE bi.item_status = 'ISSUED'
            ORDER BY bi.due_date, bi.borrowing_item_id
        """)
        return _rows(cur)


def issue_equipment(student_id, equipment_id, purpose, days, recorded_by="System Admin"):
    """
    Business rules:
    1. Student must exist.
    2. Purpose is mandatory.
    3. Borrowing duration is 1-30 days.
    4. Equipment must be AVAILABLE.
    5. The equipment row is locked during the transaction.
    6. BORROWING + BORROWING_ITEM + EQUIPMENT status are changed atomically.
    7. A condition-history record is created.
    """
    if not purpose.strip():
        raise ValueError("Borrowing purpose is required.")
    try:
        days = int(days)
    except (TypeError, ValueError):
        raise ValueError("Borrowing days must be an integer.")
    if not 1 <= days <= 30:
        raise ValueError("Borrowing duration must be between 1 and 30 days.")

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT student_id FROM STUDENT WHERE student_id = :id",
            {"id": int(student_id)}
        )
        if cur.fetchone() is None:
            raise ValueError("Student ID does not exist.")

        cur.execute("""
            SELECT equipment_id, availability_status, current_condition
            FROM EQUIPMENT
            WHERE equipment_id = :id
            FOR UPDATE
        """, {"id": int(equipment_id)})
        equipment = cur.fetchone()

        if equipment is None:
            raise ValueError("Equipment ID does not exist.")
        if equipment[1] != "AVAILABLE":
            raise ValueError(
                f"Equipment is not available. Current status: {equipment[1]}."
            )
        if equipment[2] == "UNUSABLE":
            raise ValueError("Unusable equipment cannot be issued.")

        borrowing_out = cur.var(oracledb.NUMBER)
        cur.execute("""
            INSERT INTO BORROWING
                (student_id, request_date, purpose, status)
            VALUES
                (:student_id, SYSDATE, :purpose, 'ISSUED')
            RETURNING borrowing_id INTO :out_id
        """, {
            "student_id": int(student_id),
            "purpose": purpose.strip(),
            "out_id": borrowing_out
        })
        borrowing_id = int(borrowing_out.getvalue()[0])

        due = date.today() + timedelta(days=days)
        item_out = cur.var(oracledb.NUMBER)
        cur.execute("""
            INSERT INTO BORROWING_ITEM
                (borrowing_id, equipment_id, issue_date, due_date, item_status)
            VALUES
                (:borrowing_id, :equipment_id, TRUNC(SYSDATE), :due_date, 'ISSUED')
            RETURNING borrowing_item_id INTO :out_item
        """, {
            "borrowing_id": borrowing_id,
            "equipment_id": int(equipment_id),
            "due_date": due,
            "out_item": item_out
        })
        borrowing_item_id = int(item_out.getvalue()[0])

        cur.execute("""
            UPDATE EQUIPMENT
            SET availability_status = 'BORROWED'
            WHERE equipment_id = :equipment_id
        """, {"equipment_id": int(equipment_id)})

        cur.execute("""
            INSERT INTO CONDITION_HISTORY
                (equipment_id, borrowing_item_id, condition_status,
                 condition_notes, recorded_at, recorded_by)
            SELECT equipment_id, :item_id, current_condition,
                   'Condition recorded at issue',
                   SYSTIMESTAMP, :recorded_by
            FROM EQUIPMENT
            WHERE equipment_id = :equipment_id
        """, {
            "equipment_id": int(equipment_id),
            "item_id": borrowing_item_id,
            "recorded_by": recorded_by
        })

        conn.commit()
        return borrowing_id, borrowing_item_id, due
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def return_equipment(borrowing_item_id, condition_status, notes="",
                     recorded_by="System Admin"):
    """
    Return business rules:
    - Item must exist and be ISSUED.
    - Return date is set to SYSDATE.
    - Equipment becomes AVAILABLE unless condition is DAMAGED/UNUSABLE.
    - Late fine = number of overdue days * Rs.50.
    - Damage/unusable equipment gets Rs.1500 damage fine.
    - A condition history entry is recorded.
    """
    allowed = {"EXCELLENT", "GOOD", "FAIR", "DAMAGED", "UNUSABLE"}
    condition_status = condition_status.upper()
    if condition_status not in allowed:
        raise ValueError("Invalid condition status.")

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT bi.borrowing_item_id, bi.borrowing_id, bi.equipment_id,
                   bi.due_date, bi.item_status
            FROM BORROWING_ITEM bi
            WHERE bi.borrowing_item_id = :item_id
            FOR UPDATE
        """, {"item_id": int(borrowing_item_id)})
        row = cur.fetchone()

        if row is None:
            raise ValueError("Borrowing item does not exist.")
        if row[4] != "ISSUED":
            raise ValueError(f"Item cannot be returned because its status is {row[4]}.")

        item_id, borrowing_id, equipment_id, due_date, _ = row
        today = date.today()
        due_date = due_date.date() if isinstance(due_date, datetime) else due_date
        overdue_days = max((today - due_date).days, 0)

        item_status = "DAMAGED" if condition_status in {"DAMAGED", "UNUSABLE"} else "RETURNED"

        cur.execute("""
            UPDATE BORROWING_ITEM
            SET return_date = SYSDATE,
                item_status = :item_status
            WHERE borrowing_item_id = :item_id
        """, {"item_status": item_status, "item_id": int(item_id)})

        equipment_status = (
            "DAMAGED" if condition_status in {"DAMAGED", "UNUSABLE"}
            else "AVAILABLE"
        )
        cur.execute("""
            UPDATE EQUIPMENT
            SET availability_status = :status,
                current_condition = :condition
            WHERE equipment_id = :equipment_id
        """, {
            "status": equipment_status,
            "condition": condition_status,
            "equipment_id": int(equipment_id)
        })

        cur.execute("""
            INSERT INTO CONDITION_HISTORY
                (equipment_id, borrowing_item_id, condition_status,
                 condition_notes, recorded_at, recorded_by)
            VALUES
                (:equipment_id, :item_id, :condition_status,
                 :notes, SYSTIMESTAMP, :recorded_by)
        """, {
            "equipment_id": int(equipment_id),
            "item_id": int(item_id),
            "condition_status": condition_status,
            "notes": notes.strip() or "Condition recorded at return",
            "recorded_by": recorded_by
        })

        fine_amount = 0.0
        fine_reasons = []

        if overdue_days > 0:
            fine_amount += overdue_days * FINE_PER_DAY
            fine_reasons.append(
                f"Late return by {overdue_days} day(s) at Rs. {FINE_PER_DAY:.0f} per day"
            )

        if condition_status in {"DAMAGED", "UNUSABLE"}:
            fine_amount += DAMAGE_FEE
            fine_reasons.append(f"Damage fee Rs. {DAMAGE_FEE:.0f}")

        fine_id = None
        if fine_amount > 0:
            fine_out = cur.var(oracledb.NUMBER)
            cur.execute("""
                INSERT INTO FINE
                    (borrowing_item_id, amount, reason, assessed_date, payment_status)
                VALUES
                    (:item_id, :amount, :reason, SYSDATE, 'UNPAID')
                RETURNING fine_id INTO :out_id
            """, {
                "item_id": int(item_id),
                "amount": fine_amount,
                "reason": "; ".join(fine_reasons),
                "out_id": fine_out
            })
            fine_id = int(fine_out.getvalue()[0])

        cur.execute("""
            SELECT COUNT(*)
            FROM BORROWING_ITEM
            WHERE borrowing_id = :borrowing_id
              AND item_status = 'ISSUED'
        """, {"borrowing_id": int(borrowing_id)})
        remaining = cur.fetchone()[0]

        if remaining == 0:
            cur.execute("""
                UPDATE BORROWING
                SET status = 'RETURNED'
                WHERE borrowing_id = :borrowing_id
            """, {"borrowing_id": int(borrowing_id)})

        conn.commit()
        return {
            "overdue_days": overdue_days,
            "fine_amount": fine_amount,
            "fine_id": fine_id,
            "equipment_status": equipment_status,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def get_overdue_items():
    with get_cursor() as cur:
        cur.execute("""
            SELECT bi.borrowing_item_id, s.student_name,
                   e.equipment_name, bi.due_date,
                   TRUNC(SYSDATE) - bi.due_date AS days_overdue
            FROM BORROWING_ITEM bi
            JOIN BORROWING b ON b.borrowing_id = bi.borrowing_id
            JOIN STUDENT s ON s.student_id = b.student_id
            JOIN EQUIPMENT e ON e.equipment_id = bi.equipment_id
            WHERE bi.item_status = 'ISSUED'
              AND bi.due_date < TRUNC(SYSDATE)
            ORDER BY bi.due_date
        """)
        return _rows(cur)


def get_fines(status=None):
    """Return fines. status = 'UNPAID', 'PAID', 'WAIVED' or None for all."""
    sql = """
        SELECT f.fine_id, s.student_name, e.equipment_name,
               f.amount, f.reason, f.payment_status
        FROM FINE f
        JOIN BORROWING_ITEM bi ON bi.borrowing_item_id = f.borrowing_item_id
        JOIN BORROWING b ON b.borrowing_id = bi.borrowing_id
        JOIN STUDENT s ON s.student_id = b.student_id
        JOIN EQUIPMENT e ON e.equipment_id = bi.equipment_id
    """
    params = {}
    if status:
        sql += " WHERE f.payment_status = :status"
        params["status"] = status.upper()
    sql += " ORDER BY f.fine_id"
    with get_cursor() as cur:
        cur.execute(sql, params)
        return _rows(cur)


def get_unpaid_fines():
    return get_fines("UNPAID")


def get_all_fines():
    return get_fines(None)


def pay_fine(fine_id, payment_method):
    method = payment_method.upper()
    if method not in {"CASH", "CARD", "UPI", "ONLINE"}:
        raise ValueError("Payment method must be CASH, CARD, UPI or ONLINE.")

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT fine_id, amount, payment_status
            FROM FINE
            WHERE fine_id = :fine_id
            FOR UPDATE
        """, {"fine_id": int(fine_id)})
        fine = cur.fetchone()

        if fine is None:
            raise ValueError("Fine ID does not exist.")
        if fine[2] != "UNPAID":
            raise ValueError(f"Fine is already {fine[2]}.")

        cur.execute("""
            INSERT INTO PAYMENT
                (fine_id, amount, payment_date, payment_method)
            VALUES
                (:fine_id, :amount, SYSDATE, :method)
        """, {
            "fine_id": int(fine[0]),
            "amount": float(fine[1]),
            "method": method
        })

        cur.execute("""
            UPDATE FINE
            SET payment_status = 'PAID'
            WHERE fine_id = :fine_id
        """, {"fine_id": int(fine_id)})

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


# ------------------------------------------------------------
# Student deletion
# ------------------------------------------------------------
_STUDENT_ITEMS = """
    SELECT bi.borrowing_item_id
    FROM BORROWING_ITEM bi
    JOIN BORROWING b ON b.borrowing_id = bi.borrowing_id
    WHERE b.student_id = :sid
"""


def get_student_delete_info(student_id):
    """Summarise what deleting a student would affect."""
    with get_cursor() as cur:
        cur.execute("""
            SELECT s.student_name,
                   (SELECT COUNT(*) FROM BORROWING b
                     WHERE b.student_id = s.student_id),
                   (SELECT COUNT(*) FROM BORROWING_ITEM bi
                      JOIN BORROWING b ON b.borrowing_id = bi.borrowing_id
                     WHERE b.student_id = s.student_id),
                   (SELECT COUNT(*) FROM BORROWING_ITEM bi
                      JOIN BORROWING b ON b.borrowing_id = bi.borrowing_id
                     WHERE b.student_id = s.student_id
                       AND bi.item_status IN ('RESERVED', 'ISSUED')),
                   (SELECT COUNT(*) FROM FINE f
                      JOIN BORROWING_ITEM bi
                        ON bi.borrowing_item_id = f.borrowing_item_id
                      JOIN BORROWING b ON b.borrowing_id = bi.borrowing_id
                     WHERE b.student_id = s.student_id
                       AND f.payment_status = 'UNPAID'),
                   (SELECT COUNT(*) FROM RESERVATION r
                     WHERE r.student_id = s.student_id)
            FROM STUDENT s
            WHERE s.student_id = :sid
        """, {"sid": int(student_id)})
        row = cur.fetchone()

    if row is None:
        raise ValueError("Student ID does not exist.")
    return {
        "name": row[0],
        "borrowings": row[1],
        "items": row[2],
        "active_items": row[3],
        "unpaid_fines": row[4],
        "reservations": row[5],
    }


def delete_student(student_id):
    """
    Delete a student and all of their records in one transaction.

    Blocked when the student still holds equipment or owes an unpaid fine.
    Equipment condition history is kept; only its link to the deleted
    borrowing item is cleared.
    """
    sid = {"sid": int(student_id)}
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT student_name FROM STUDENT WHERE student_id = :sid FOR UPDATE",
            sid
        )
        if cur.fetchone() is None:
            raise ValueError("Student ID does not exist.")

        cur.execute(f"""
            SELECT COUNT(*) FROM BORROWING_ITEM
            WHERE borrowing_item_id IN ({_STUDENT_ITEMS})
              AND item_status IN ('RESERVED', 'ISSUED')
        """, sid)
        if cur.fetchone()[0] > 0:
            raise ValueError(
                "This student still has equipment issued. "
                "Return it before deleting the student."
            )

        cur.execute(f"""
            SELECT COUNT(*) FROM FINE
            WHERE payment_status = 'UNPAID'
              AND borrowing_item_id IN ({_STUDENT_ITEMS})
        """, sid)
        if cur.fetchone()[0] > 0:
            raise ValueError(
                "This student has unpaid fines. "
                "Mark them as paid before deleting the student."
            )

        counts = {}

        cur.execute(f"""
            DELETE FROM PAYMENT WHERE fine_id IN (
                SELECT fine_id FROM FINE
                WHERE borrowing_item_id IN ({_STUDENT_ITEMS}))
        """, sid)
        counts["payments"] = cur.rowcount

        cur.execute(f"""
            DELETE FROM FINE
            WHERE borrowing_item_id IN ({_STUDENT_ITEMS})
        """, sid)
        counts["fines"] = cur.rowcount

        cur.execute(f"""
            UPDATE CONDITION_HISTORY SET borrowing_item_id = NULL
            WHERE borrowing_item_id IN ({_STUDENT_ITEMS})
        """, sid)

        cur.execute(f"""
            DELETE FROM BORROWING_ITEM
            WHERE borrowing_item_id IN ({_STUDENT_ITEMS})
        """, sid)
        counts["items"] = cur.rowcount

        cur.execute("""
            DELETE FROM APPROVAL WHERE borrowing_id IN (
                SELECT borrowing_id FROM BORROWING WHERE student_id = :sid)
        """, sid)

        cur.execute("DELETE FROM BORROWING WHERE student_id = :sid", sid)
        counts["borrowings"] = cur.rowcount

        cur.execute("DELETE FROM RESERVATION WHERE student_id = :sid", sid)
        counts["reservations"] = cur.rowcount

        cur.execute("DELETE FROM STUDENT WHERE student_id = :sid", sid)

        conn.commit()
        return counts
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
