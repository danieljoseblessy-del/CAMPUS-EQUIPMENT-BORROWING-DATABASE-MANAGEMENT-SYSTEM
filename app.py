"""
app.py
Graphical front-end for Campus Equipment Management System.

Run:
    python app.py
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date

import equipment_db as db
from db_connection import test_connection


class CampusEquipmentApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.dept_lookup = {}

        self.title("Campus Equipment Management System")
        self.geometry("1250x760")
        self.minsize(1050, 650)

        self.style = ttk.Style(self)
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass

        self.style.configure("Title.TLabel", font=("Segoe UI", 22, "bold"))
        self.style.configure("Section.TLabel", font=("Segoe UI", 13, "bold"))
        self.style.configure("CardValue.TLabel", font=("Segoe UI", 22, "bold"))
        self.style.configure("Treeview", rowheight=28, font=("Segoe UI", 10))
        self.style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))

        self.container = ttk.Frame(self, padding=14)
        self.container.pack(fill="both", expand=True)

        self.build_header()
        self.build_notebook()

        self.refresh_all()

    def build_header(self):
        header = ttk.Frame(self.container)
        header.pack(fill="x", pady=(0, 12))

        ttk.Label(
            header,
            text="CAMPUS EQUIPMENT MANAGEMENT SYSTEM",
            style="Title.TLabel"
        ).pack(side="left")

        ttk.Button(
            header,
            text="Test Oracle Connection",
            command=self.test_db
        ).pack(side="right")

    def build_notebook(self):
        self.nb = ttk.Notebook(self.container)
        self.nb.pack(fill="both", expand=True)

        self.dashboard_tab = ttk.Frame(self.nb, padding=12)
        self.student_tab = ttk.Frame(self.nb, padding=12)
        self.equipment_tab = ttk.Frame(self.nb, padding=12)
        self.borrow_tab = ttk.Frame(self.nb, padding=12)
        self.reports_tab = ttk.Frame(self.nb, padding=12)

        self.nb.add(self.dashboard_tab, text="Dashboard")
        self.nb.add(self.student_tab, text="Students")
        self.nb.add(self.equipment_tab, text="Equipment")
        self.nb.add(self.borrow_tab, text="Borrow / Return")
        self.nb.add(self.reports_tab, text="Reports")

        self.build_dashboard()
        self.build_students()
        self.build_equipment()
        self.build_borrow_return()
        self.build_reports()

    def build_dashboard(self):
        self.dashboard_cards = {}
        cards = [
            ("Students", "students"),
            ("Equipment", "equipment"),
            ("Available", "available"),
            ("Issued", "issued"),
            ("Overdue", "overdue"),
            ("Unpaid Fines", "unpaid_fines"),
        ]

        grid = ttk.Frame(self.dashboard_tab)
        grid.pack(fill="x")

        for i, (label, key) in enumerate(cards):
            card = ttk.LabelFrame(grid, text=label, padding=18)
            card.grid(row=0, column=i, padx=5, sticky="nsew")
            grid.columnconfigure(i, weight=1)
            value = ttk.Label(card, text="0", style="CardValue.TLabel")
            value.pack()
            self.dashboard_cards[key] = value

        info = ttk.LabelFrame(
            self.dashboard_tab,
            text="Assessment 9 Business Rules",
            padding=16
        )
        info.pack(fill="both", expand=True, pady=20)

        rules = (
            "1. Student registration validates name, email and department.\n"
            "2. Borrowing duration must be between 1 and 30 days.\n"
            "3. Equipment can be issued only when its status is AVAILABLE.\n"
            "4. Issue/return operations use transactions and row locking.\n"
            "5. Late fine = Rs. 50 per overdue day.\n"
            "6. Damaged/Unusable equipment receives a Rs. 1500 damage fee.\n"
            "7. Return operations update equipment, borrowing, item, condition history and fine records."
        )
        ttk.Label(info, text=rules, justify="left").pack(anchor="w")

    def build_students(self):
        form = ttk.LabelFrame(self.student_tab, text="Register Student", padding=12)
        form.pack(fill="x")

        self.student_name = tk.StringVar()
        self.student_email = tk.StringVar()
        self.student_phone = tk.StringVar()
        self.student_dept = tk.StringVar()

        fields = [
            ("Name", self.student_name),
            ("Email", self.student_email),
            ("Phone", self.student_phone),
        ]
        for i, (label, var) in enumerate(fields):
            ttk.Label(form, text=label).grid(row=0, column=i * 2, padx=6, pady=6, sticky="w")
            ttk.Entry(form, textvariable=var, width=28).grid(
                row=0, column=i * 2 + 1, padx=6, pady=6
            )

        ttk.Label(form, text="Department").grid(row=1, column=0, padx=6, pady=6, sticky="w")
        self.dept_combo = ttk.Combobox(
            form,
            textvariable=self.student_dept,
            state="readonly",
            width=38,
            postcommand=self.load_departments   # refresh list each time it is opened
        )
        self.dept_combo.grid(row=1, column=1, padx=6, pady=6, sticky="w")

        # Shows how many departments were loaded, or why none were
        self.dept_status = ttk.Label(form, text="", foreground="gray")
        self.dept_status.grid(
            row=2, column=0, columnspan=4, padx=6, pady=(0, 4), sticky="w"
        )

        ttk.Button(
            form, text="Add Student", command=self.add_student
        ).grid(row=1, column=2, padx=8, pady=6)

        ttk.Button(
            form, text="Clear", command=self.clear_student_form
        ).grid(row=1, column=3, padx=8, pady=6)

        actions = ttk.Frame(self.student_tab)
        actions.pack(fill="x", pady=(8, 4))
        ttk.Button(
            actions, text="Delete Selected Student",
            command=self.delete_student_action
        ).pack(side="left", padx=4)
        ttk.Button(
            actions, text="Refresh List", command=self.refresh_students
        ).pack(side="left", padx=4)

        self.student_tree = self.make_tree(
            self.student_tab,
            ["ID", "Name", "Email", "Phone", "Department"],
            [70, 190, 250, 150, 280]
        )

    def build_equipment(self):
        toolbar = ttk.Frame(self.equipment_tab)
        toolbar.pack(fill="x", pady=(0, 10))

        ttk.Label(
            toolbar,
            text="Status:"
        ).pack(side="left")

        self.equipment_status = tk.StringVar(value="ALL")

        status_combo = ttk.Combobox(
            toolbar,
            textvariable=self.equipment_status,
            state="readonly",
            values=[
                "ALL",
                "AVAILABLE",
                "BORROWED",
                "RESERVED",
                "DAMAGED",
                "MAINTENANCE"
            ],
            width=18
        )

        status_combo.pack(side="left", padx=8)

        status_combo.bind(
            "<<ComboboxSelected>>",
            lambda e: self.refresh_equipment()
        )

        # Refresh button
        ttk.Button(
            toolbar,
            text="Refresh",
            command=self.refresh_equipment
        ).pack(side="left", padx=5)

        # Update Condition button
        ttk.Button(
            toolbar,
            text="Update Condition",
            command=self.update_condition_action
        ).pack(side="left", padx=5)

        # Equipment table
        self.equipment_tree = self.make_tree(
            self.equipment_tab,
            [
                "ID",
                "Equipment",
                "Category",
                "Asset Tag",
                "Serial No.",
                "Status",
                "Condition"
            ],
            [60, 230, 160, 120, 150, 110, 110]
        )

        # Allow double-clicking an equipment row
        self.equipment_tree.bind(
            "<Double-1>",
            lambda event: self.update_condition_action()
        )

    def build_borrow_return(self):
        issue = ttk.LabelFrame(
            self.borrow_tab, text="Issue Equipment", padding=12
        )
        issue.pack(fill="x")

        self.issue_student = tk.StringVar()
        self.issue_equipment = tk.StringVar()
        self.issue_purpose = tk.StringVar()
        self.issue_days = tk.StringVar(value="7")

        labels = [
            ("Student ID", self.issue_student),
            ("Equipment ID", self.issue_equipment),
            ("Purpose", self.issue_purpose),
            ("Days", self.issue_days),
        ]

        for i, (label, var) in enumerate(labels):
            ttk.Label(issue, text=label).grid(row=0, column=i * 2, padx=5, pady=5)
            ttk.Entry(issue, textvariable=var, width=20).grid(
                row=0, column=i * 2 + 1, padx=5, pady=5
            )

        ttk.Button(
            issue, text="Issue Equipment", command=self.issue
        ).grid(row=1, column=0, columnspan=2, padx=5, pady=8, sticky="w")

        return_box = ttk.LabelFrame(
            self.borrow_tab, text="Return Issued Equipment", padding=12
        )
        return_box.pack(fill="x", pady=12)

        self.return_item = tk.StringVar()
        self.return_condition = tk.StringVar(value="GOOD")
        self.return_notes = tk.StringVar()

        ttk.Label(return_box, text="Borrowing Item ID").grid(row=0, column=0, padx=5, pady=5)
        ttk.Entry(return_box, textvariable=self.return_item, width=18).grid(row=0, column=1, padx=5)

        ttk.Label(return_box, text="Condition").grid(row=0, column=2, padx=5)
        ttk.Combobox(
            return_box,
            textvariable=self.return_condition,
            state="readonly",
            values=["EXCELLENT", "GOOD", "FAIR", "DAMAGED", "UNUSABLE"],
            width=16
        ).grid(row=0, column=3, padx=5)

        ttk.Label(return_box, text="Notes").grid(row=0, column=4, padx=5)
        ttk.Entry(return_box, textvariable=self.return_notes, width=30).grid(row=0, column=5, padx=5)

        ttk.Button(
            return_box, text="Return Equipment", command=self.return_item_action
        ).grid(row=0, column=6, padx=8)

        ttk.Button(
            return_box, text="Refresh Issued Items", command=self.refresh_issued
        ).grid(row=1, column=0, columnspan=2, pady=8, sticky="w")

        self.issued_tree = self.make_tree(
            self.borrow_tab,
            ["Item ID", "Student", "Equipment", "Issue Date", "Due Date", "Status"],
            [80, 190, 250, 130, 130, 100]
        )

    def build_reports(self):
        toolbar = ttk.Frame(self.reports_tab)
        toolbar.pack(fill="x", pady=(0, 10))

        ttk.Button(
            toolbar, text="Overdue Items", command=self.show_overdue
        ).pack(side="left", padx=4)

        ttk.Button(
            toolbar, text="Unpaid Fines", command=self.show_fines
        ).pack(side="left", padx=4)

        ttk.Button(
            toolbar, text="All Fines", command=self.show_all_fines
        ).pack(side="left", padx=4)

        ttk.Button(
            toolbar, text="Refresh Dashboard", command=self.refresh_dashboard
        ).pack(side="left", padx=4)

        # --- Record a fine payment (select a row in a fines list first) ---
        self.report_mode = None
        ttk.Separator(toolbar, orient="vertical").pack(
            side="left", fill="y", padx=12
        )
        ttk.Label(toolbar, text="Payment Method").pack(side="left", padx=(0, 4))
        self.pay_method = tk.StringVar(value="CASH")
        ttk.Combobox(
            toolbar, textvariable=self.pay_method, state="readonly", width=10,
            values=["CASH", "CARD", "UPI", "ONLINE"]
        ).pack(side="left", padx=4)
        ttk.Button(
            toolbar, text="Mark Selected Fine as Paid",
            command=self.pay_selected_fine
        ).pack(side="left", padx=4)

        self.report_tree = self.make_tree(
            self.reports_tab,
            ["Column 1", "Column 2", "Column 3", "Column 4", "Column 5", "Column 6"],
            [150, 220, 220, 150, 180, 150]
        )

    def make_tree(self, parent, columns, widths):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)

        tree = ttk.Treeview(frame, columns=columns, show="headings")
        for col, width in zip(columns, widths):
            tree.heading(col, text=col)
            tree.column(col, width=width, anchor="center")

        vs = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        hs = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)

        tree.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        hs.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        return tree

    @staticmethod
    def fill_tree(tree, rows, keys):
        tree.delete(*tree.get_children())
        for row in rows:
            values = []
            for key in keys:
                value = row.get(key)
                if hasattr(value, "strftime"):
                    value = value.strftime("%Y-%m-%d")
                values.append("" if value is None else value)
            tree.insert("", "end", values=values)

    def test_db(self):
        try:
            info = test_connection()
            messagebox.showinfo(
                "Oracle Connection Successful",
                f"Connected to Oracle successfully.\n\n"
                f"User: {info['user']}\n"
                f"Service: {info['service']}\n"
                f"Server time: {info['server_time']}\n"
                f"DSN: {info['dsn']}"
            )
        except Exception as exc:
            messagebox.showerror(
                "Oracle Connection Failed",
                str(exc)
            )

    def refresh_dashboard(self):
        try:
            counts = db.get_dashboard_counts()
            for key, label in self.dashboard_cards.items():
                label.config(text=str(counts[key]))
        except Exception as exc:
            messagebox.showerror("Database Error", str(exc))

    def load_departments(self):
        """
        Load departments from Oracle into the Department drop-down.
        Runs independently of the student table, so a problem loading
        students can no longer leave the drop-down empty.
        """
        try:
            departments = db.get_departments()
        except Exception as exc:
            self.dept_lookup = {}
            self.dept_combo["values"] = []
            self.dept_status.config(
                text=f"Could not load departments: {exc}", foreground="red"
            )
            return False

        # "1 - Computer Science" -> 1, "2 - Mathematics" -> 2, ...
        self.dept_lookup = {
            f"{r['department_id']} - {r['department_name']}": r["department_id"]
            for r in departments
        }
        self.dept_combo["values"] = list(self.dept_lookup.keys())

        # Drop a selection that no longer exists
        if self.student_dept.get() not in self.dept_lookup:
            self.student_dept.set("")

        if self.dept_lookup:
            self.dept_status.config(
                text=f"{len(self.dept_lookup)} department(s) available.",
                foreground="gray"
            )
        else:
            self.dept_status.config(
                text=("No departments found in the DEPARTMENT table. Add "
                      "departments in Oracle and COMMIT, then open the "
                      "drop-down again."),
                foreground="red"
            )
        return True

    def refresh_students(self):
        # Departments first, so the drop-down works even if students fail
        self.load_departments()

        try:
            rows = db.get_students()
            self.fill_tree(
                self.student_tree,
                rows,
                ["student_id", "student_name", "email", "phone", "department_name"]
            )
        except Exception as exc:
            messagebox.showerror(
                "Student Loading Error",
                f"Unable to load students from Oracle.\n\n{exc}"
            )

    def add_student(self):
        try:
            # Get selected department from ComboBox
            selected = self.student_dept.get().strip()

            # Make sure a department was selected
            if not selected:
                messagebox.showwarning(
                    "Department Required",
                    "Please select a department."
                )
                return

            # Convert displayed department into department ID
            dept_id = self.dept_lookup.get(selected)

            # Make sure the department exists in the lookup
            if dept_id is None:
                messagebox.showwarning(
                    "Invalid Department",
                    "Please select a valid department from the dropdown."
                )
                return

            # Insert student into Oracle
            new_id = db.insert_student(
                self.student_name.get().strip(),
                self.student_email.get().strip(),
                self.student_phone.get().strip(),
                dept_id
            )

            messagebox.showinfo(
                "Success",
                f"Student added successfully.\n\nStudent ID: {new_id}"
            )

            # Clear form
            self.clear_student_form()

            # Refresh student table and dashboard
            self.refresh_students()
            self.refresh_dashboard()

        except Exception as exc:
            messagebox.showerror(
                "Student Registration Failed",
                str(exc)
            )

    def clear_student_form(self):
        self.student_name.set("")
        self.student_email.set("")
        self.student_phone.set("")
        self.student_dept.set("")

    def delete_student_action(self):
        """Delete the student selected in the Students table."""
        selected = self.student_tree.selection()
        if not selected:
            messagebox.showwarning(
                "No Student Selected", "Select a student in the table first."
            )
            return

        values = self.student_tree.item(selected[0])["values"]
        student_id, name = int(values[0]), values[1]

        try:
            info = db.get_student_delete_info(student_id)

            if info["active_items"]:
                messagebox.showwarning(
                    "Cannot Delete",
                    f"{name} still has {info['active_items']} item(s) issued.\n"
                    "Return the equipment first."
                )
                return
            if info["unpaid_fines"]:
                messagebox.showwarning(
                    "Cannot Delete",
                    f"{name} has {info['unpaid_fines']} unpaid fine(s).\n"
                    "Mark them as paid first (Reports tab)."
                )
                return

            if not messagebox.askyesno(
                "Confirm Delete",
                f"Permanently delete {name} (ID {student_id})?\n\n"
                f"This also deletes their history:\n"
                f"  - {info['borrowings']} borrowing record(s)\n"
                f"  - {info['items']} borrowed item(s) with fines/payments\n"
                f"  - {info['reservations']} reservation(s)\n\n"
                "This cannot be undone.",
                icon="warning",
                default="no"
            ):
                return

            db.delete_student(student_id)
            messagebox.showinfo("Deleted", f"{name} was deleted.")
            self.refresh_students()
            self.refresh_dashboard()
        except Exception as exc:
            messagebox.showerror("Delete Failed", str(exc))

    def refresh_equipment(self):
        try:
            rows = db.get_equipment(self.equipment_status.get())
            self.fill_tree(
                self.equipment_tree,
                rows,
                ["equipment_id", "equipment_name", "category_name",
                 "asset_tag", "serial_no", "availability_status",
                 "current_condition"]
            )
        except Exception as exc:
            messagebox.showerror("Database Error", str(exc))

    def update_condition_action(self):
        """
        Open a window to update the condition of the
        selected equipment.
        """

        # Get selected row
        selected = self.equipment_tree.selection()

        if not selected:
            messagebox.showwarning(
                "No Equipment Selected",
                "Please select an equipment item from the table first."
            )
            return

        # Get row values
        item = self.equipment_tree.item(selected[0])
        values = item.get("values", [])

        if not values:
            messagebox.showwarning(
                "Selection Error",
                "Unable to read the selected equipment."
            )
            return

        # Based on the Equipment table columns:
        # 0 = ID
        # 1 = Equipment
        # 2 = Category
        # 3 = Asset Tag
        # 4 = Serial No.
        # 5 = Status
        # 6 = Condition

        equipment_id = values[0]
        equipment_name = values[1]
        current_condition = values[6]

        # Create update window
        dialog = tk.Toplevel(self)
        dialog.title("Update Equipment Condition")
        dialog.geometry("480x300")
        dialog.resizable(False, False)

        # Heading
        ttk.Label(
            dialog,
            text="Update Equipment Condition",
            font=("Segoe UI", 15, "bold")
        ).pack(pady=(15, 10))

        # Equipment information
        info_frame = ttk.Frame(dialog)
        info_frame.pack(fill="x", padx=20)

        ttk.Label(
            info_frame,
            text=f"Equipment ID: {equipment_id}"
        ).pack(anchor="w", pady=3)

        ttk.Label(
            info_frame,
            text=f"Equipment: {equipment_name}"
        ).pack(anchor="w", pady=3)

        ttk.Label(
            info_frame,
            text=f"Current Condition: {current_condition}"
        ).pack(anchor="w", pady=3)

        # Condition selection
        ttk.Label(
            dialog,
            text="New Condition:"
        ).pack(anchor="w", padx=20, pady=(12, 3))

        new_condition = tk.StringVar(
            value=str(current_condition)
        )

        condition_combo = ttk.Combobox(
            dialog,
            textvariable=new_condition,
            state="readonly",
            values=[
                "EXCELLENT",
                "GOOD",
                "FAIR",
                "DAMAGED",
                "UNUSABLE"
            ],
            width=30
        )

        condition_combo.pack(
            anchor="w",
            padx=20
        )

        # Notes
        ttk.Label(
            dialog,
            text="Condition Notes:"
        ).pack(anchor="w", padx=20, pady=(10, 3))

        notes_var = tk.StringVar()

        notes_entry = ttk.Entry(
            dialog,
            textvariable=notes_var,
            width=45
        )

        notes_entry.pack(
            anchor="w",
            padx=20
        )

        # Save function
        def save_condition():

            condition = new_condition.get().strip()
            notes = notes_var.get().strip()

            if not condition:
                messagebox.showwarning(
                    "Missing Condition",
                    "Please select a condition.",
                    parent=dialog
                )
                return

            try:
                result = db.update_equipment_condition(
                    equipment_id,
                    condition,
                    notes
                )

                messagebox.showinfo(
                    "Condition Updated",
                    f"Equipment: {result['equipment_name']}\n\n"
                    f"Previous Condition: "
                    f"{result['old_condition']}\n"
                    f"New Condition: "
                    f"{result['new_condition']}\n\n"
                    f"Equipment Status: "
                    f"{result['new_status']}",
                    parent=dialog
                )

                dialog.destroy()

                # Refresh equipment table
                self.refresh_equipment()

                # Refresh dashboard because availability
                # may have changed
                self.refresh_dashboard()

            except Exception as exc:
                messagebox.showerror(
                    "Condition Update Failed",
                    str(exc),
                    parent=dialog
                )

        # Buttons
        button_frame = tk.Frame(dialog)
        button_frame.pack(pady=20)

        tk.Button(
            button_frame,
            text="Save Changes",
            command=save_condition,
            font=("Segoe UI", 10, "bold"),
            fg="black",
            bg="#e1e1e1",
            activebackground="#d0d0d0",
            width=14,
            padx=6,
            pady=4
        ).pack(side="left", padx=8)

        tk.Button(
            button_frame,
            text="Cancel",
            command=dialog.destroy,
            font=("Segoe UI", 10, "bold"),
            fg="black",
            bg="#e1e1e1",
            activebackground="#d0d0d0",
            width=14,
            padx=6,
            pady=4
        ).pack(side="left", padx=8)

        # Focus on condition selection
        condition_combo.focus_set()

    def issue(self):
        try:
            borrowing_id, item_id, due = db.issue_equipment(
                self.issue_student.get(),
                self.issue_equipment.get(),
                self.issue_purpose.get(),
                self.issue_days.get()
            )
            messagebox.showinfo(
                "Equipment Issued",
                f"Equipment issued successfully.\n\n"
                f"Borrowing ID: {borrowing_id}\n"
                f"Borrowing Item ID: {item_id}\n"
                f"Due date: {due}"
            )
            self.issue_student.set("")
            self.issue_equipment.set("")
            self.issue_purpose.set("")
            self.issue_days.set("7")
            self.refresh_all()
        except Exception as exc:
            messagebox.showerror("Issue Failed", str(exc))

    def refresh_issued(self):
        try:
            rows = db.get_issued_items()
            self.fill_tree(
                self.issued_tree,
                rows,
                ["borrowing_item_id", "student_name", "equipment_name",
                 "issue_date", "due_date", "item_status"]
            )
        except Exception as exc:
            messagebox.showerror("Database Error", str(exc))

    def return_item_action(self):
        try:
            result = db.return_equipment(
                self.return_item.get(),
                self.return_condition.get(),
                self.return_notes.get()
            )
            fine_text = (
                f"Fine created: Rs. {result['fine_amount']:.2f}"
                if result["fine_amount"] > 0
                else "No fine was created."
            )
            messagebox.showinfo(
                "Equipment Returned",
                f"Return completed successfully.\n\n"
                f"Overdue days: {result['overdue_days']}\n"
                f"{fine_text}\n"
                f"Equipment status: {result['equipment_status']}"
            )
            self.return_item.set("")
            self.return_notes.set("")
            self.refresh_all()
        except Exception as exc:
            messagebox.showerror("Return Failed", str(exc))

    def show_overdue(self):
        try:
            rows = db.get_overdue_items()
            self.fill_tree(
                self.report_tree,
                rows,
                ["borrowing_item_id", "student_name", "equipment_name",
                 "due_date", "days_overdue"]
            )
            self.set_report_headings(
                ["Item ID", "Student", "Equipment", "Due Date", "Days Overdue"]
            )
            self.report_mode = "overdue"
        except Exception as exc:
            messagebox.showerror("Report Error", str(exc))

    def _show_fines(self, rows, mode):
        self.fill_tree(
            self.report_tree,
            rows,
            ["fine_id", "student_name", "equipment_name",
             "amount", "reason", "payment_status"]
        )
        self.set_report_headings(
            ["Fine ID", "Student", "Equipment", "Amount", "Reason", "Status"]
        )
        self.report_mode = mode

    def show_fines(self):
        try:
            self._show_fines(db.get_unpaid_fines(), "unpaid_fines")
        except Exception as exc:
            messagebox.showerror("Report Error", str(exc))

    def show_all_fines(self):
        try:
            self._show_fines(db.get_all_fines(), "all_fines")
        except Exception as exc:
            messagebox.showerror("Report Error", str(exc))

    def pay_selected_fine(self):
        """Record payment for the fine selected in the Reports table."""
        if self.report_mode not in ("unpaid_fines", "all_fines"):
            messagebox.showwarning(
                "Open a Fines List",
                "Click 'Unpaid Fines' or 'All Fines', then select a fine."
            )
            return

        selected = self.report_tree.selection()
        if not selected:
            messagebox.showwarning(
                "No Fine Selected", "Select a fine in the table first."
            )
            return

        values = self.report_tree.item(selected[0])["values"]
        fine_id, student, equipment, amount, _reason, status = values[:6]

        if str(status).upper() != "UNPAID":
            messagebox.showinfo(
                "Already Settled", f"Fine {fine_id} is already {status}."
            )
            return

        method = self.pay_method.get()
        if not messagebox.askyesno(
            "Confirm Payment",
            f"Record payment of Rs. {amount} by {student} "
            f"for {equipment} ({method})?"
        ):
            return

        try:
            db.pay_fine(int(fine_id), method)
            messagebox.showinfo(
                "Payment Recorded", f"Fine {fine_id} marked as PAID."
            )
            if self.report_mode == "all_fines":
                self.show_all_fines()
            else:
                self.show_fines()
            self.refresh_dashboard()
        except Exception as exc:
            messagebox.showerror("Payment Failed", str(exc))

    def set_report_headings(self, headings):
        for i, heading in enumerate(headings):
            col = self.report_tree["columns"][i]
            self.report_tree.heading(col, text=heading)
        for i in range(len(headings), len(self.report_tree["columns"])):
            col = self.report_tree["columns"][i]
            self.report_tree.heading(col, text="")

    def refresh_all(self):
        try:
            self.refresh_dashboard()
            self.refresh_students()
            self.refresh_equipment()
            self.refresh_issued()
        except Exception:
            # Individual refresh methods already show detailed errors.
            pass


if __name__ == "__main__":
    app = CampusEquipmentApp()
    app.mainloop()
