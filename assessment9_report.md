# Assessment 9 – Project Phase 2
## Campus Equipment Management System

### 1. Data Population (2 Marks)
The provided Oracle SQL*Plus DML script populates the 12 normalized project tables:
DEPARTMENT, STUDENT, EQUIPMENT_CATEGORY, EQUIPMENT, BORROWING,
BORROWING_ITEM, RESERVATION, APPROVAL, CONDITION_HISTORY, MAINTENANCE,
FINE and PAYMENT.

The DML is executed after the Assessment 8 DDL and follows foreign-key dependency
order. It includes verification queries and expected row counts.

### 2. Front-End Design (2 Marks)
`app.py` provides a Tkinter graphical user interface with:
- Dashboard
- Student registration
- Equipment inventory/status view
- Borrow/return operations
- Overdue and unpaid-fine reports
- Oracle connection test

### 3. Business Logic Implementation (3 Marks)
Implemented rules include:
1. Student name and email validation.
2. Borrowing duration restricted to 1–30 days.
3. Only AVAILABLE equipment may be issued.
4. Equipment is row-locked with `FOR UPDATE` during issue/return transactions.
5. Issue updates BORROWING, BORROWING_ITEM, EQUIPMENT and CONDITION_HISTORY.
6. Return updates item/equipment condition and creates a condition-history record.
7. Late fine = Rs. 50 per overdue day.
8. DAMAGED/UNUSABLE equipment attracts Rs. 1500 damage fee.
9. Fine payment updates FINE and creates PAYMENT.

### 4. Database Connectivity (3 Marks)
Python connects to Oracle using `python-oracledb` in Thin mode.
The DSN is:
`host:port/service`

Environment variables:
- ORA_HOST
- ORA_PORT
- ORA_SERVICE
- ORA_USER
- ORA_PASSWORD

### Execution
1. Run Assessment 8 DDL in SQL*Plus.
2. Run the supplied Assessment 9 DML in SQL*Plus.
3. Verify row counts using `schema_verify.sql`.
4. Install Python dependency:
   `python -m pip install oracledb`
5. Configure Oracle environment variables.
6. Test:
   `python db_connection.py`
7. Run:
   `python app.py`

### Screenshot Evidence to Capture
1. SQL*Plus DML execution / row counts.
2. Successful Oracle connection message in GUI.
3. Dashboard showing populated counts.
4. Student registration success.
5. Equipment list.
6. Successful equipment issue.
7. Equipment status changing to BORROWED.
8. Successful return.
9. Fine generated for overdue/damaged return.
10. Overdue/unpaid-fine report.

### Important
The Python connection is to the Oracle database service, not to SQL*Plus itself.
SQL*Plus is used to execute/verify Oracle SQL. Python uses `python-oracledb`
to connect directly to the same Oracle service.
