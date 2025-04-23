import streamlit as st
import sqlite3
from datetime import date

# Global variable
DB_NAME = "users.db"

# DATABASE FUNCTIONS
def add_user(username, password, role="Employee", manager=None):
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password, role, manager) VALUES (?, ?, ?, ?)", 
                 (username, password, role, manager))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # Username already exists
        return False
    finally:
        conn.close()

def verify_user(username, password):
    #Check if username and password match a user in database
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
    user = c.fetchone()
    conn.close()
    return user  # Returns user data if found, None otherwise

def get_managers():
    #Get list of all users with Manager role
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT username FROM users WHERE role = 'Manager'")
    managers = [row[0] for row in c.fetchall()]
    conn.close()
    return managers

def get_user_role(username):
    #Get the role of a specific user
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT role FROM users WHERE username = ?", (username,))
    role = c.fetchone()
    conn.close()
    return role[0] if role else None

def get_user_manager(username):
    #Get the manager of a specific user
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT manager FROM users WHERE username = ?", (username,))
    manager = c.fetchone()
    conn.close()
    return manager[0] if manager else None


# LEAVE MANAGEMENT FUNCTIONS
def apply_leave(username, leave_date, leave_type, comment=''):
    #Submit a new leave request
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO leaves (username, date, leave_type, comment, status) VALUES (?, ?, ?, ?, 'Waiting')",
              (username, leave_date, leave_type, comment))
    conn.commit()
    conn.close()

def get_user_leaves(username):
    #Get all leave requests for a specific user
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, date, leave_type, comment, status FROM leaves WHERE username = ?", (username,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_leaves_for_manager(manager_username):
    #Get all leave requests that need to be reviewed by a specific manager
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        SELECT l.id, l.username, l.date, l.leave_type, l.comment, l.status
        FROM leaves l
        JOIN users u ON l.username = u.username
        WHERE u.manager = ?
    ''', (manager_username,))
    rows = c.fetchall()
    conn.close()
    return rows

def update_leave_status(leave_id, status):
    #Update the status of a leave request (Approved/Rejected)
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE leaves SET status = ? WHERE id = ?", (status, leave_id))
    conn.commit()
    conn.close()


# UI FUNCTIONS
def show_login_page():
    #Display login and registration option
    st.title("Login / Register")
    tab1, tab2 = st.tabs(["Login", "Register"])

    # Login tab
    with tab1:
        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pass")

        if st.button("Login"):
            if verify_user(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username
                st.success("Login successful!")
                st.rerun()  # Refresh page to show dashboard
            else:
                st.error("Invalid credentials")

    # Registration tab
    with tab2:
        new_user = st.text_input("New Username", key="reg_user")
        new_pass = st.text_input("New Password", type="password", key="reg_pass")
        role = st.selectbox("Role", ["Employee", "Manager"], key="reg_role")

        # If role is Employee, need to select a manager
        manager = None
        if role == "Employee":
            available_managers = get_managers()
            if available_managers:
                manager = st.selectbox("Select Manager", available_managers, key="reg_manager")
            else:
                st.warning("No managers available. Please register a manager first.")

        if st.button("Register"):
            if role == "Employee" and not manager:
                st.error("Please select a manager.")
            elif add_user(new_user, new_pass, role, manager):
                st.success("Account created! You can now log in.")
            else:
                st.warning("Username already exists.")

def show_employee_dashboard(username):
    #Display dashboard for employee users#
    st.header("Apply for Multiple Leaves (up to 10)")
    
    # Multi-leave application form
    num_leaves = st.number_input("Number of leave days to apply for", min_value=1, max_value=10, step=1)
    
    with st.form("multi_leave_form"):
        leave_entries = []
        
        # Create input fields for each leave day
        for i in range(num_leaves):
            st.markdown(f"Leave #{i+1}")
            l_date = st.date_input(f"Leave Date #{i+1}", key=f"date_{i}", min_value=date.today())
            l_type = st.selectbox(f"Leave Type #{i+1}", 
                                ["Sick Leave", "Casual Leave", "Earned Leave"], 
                                key=f"type_{i}")
            l_comment = st.text_area(f"Comment #{i+1} (Optional)", key=f"comment_{i}")
            
            leave_entries.append((l_date, l_type, l_comment))
            st.markdown("---")  # Separator between leave entries

        submitted = st.form_submit_button("Submit All Leaves")

        # Process form submission
        if submitted:
            for l_date, l_type, l_comment in leave_entries:
                apply_leave(username, str(l_date), l_type, l_comment)
            st.success(f"{len(leave_entries)} leave(s) submitted successfully!")

    # Display leave history
    st.subheader("Your Leave History")
    leaves = get_user_leaves(username)
    
    if leaves:
        # Convert to more readable format for display
        display_leaves = []
        for leave in leaves:
            leave_id, l_date, l_type, comment, status = leave
            display_leaves.append({
                "ID": leave_id,
                "Date": l_date,
                "Type": l_type,
                "Comment": comment,
                "Status": status
            })
        st.table(display_leaves)
    else:
        st.info("No leave records found.")

def show_manager_dashboard(username):
    #Display dashboard for manager users
    st.header("Pending Leave Requests")
    
    # Get all leave requests for employees under this manager
    leaves = get_leaves_for_manager(username)
    
    if leaves:
        for leave in leaves:
            leave_id, emp, l_date, l_type, comment, status = leave
            
            # Create expandable section for each leave request
            with st.expander(f"Leave #{leave_id} - {emp} ({status})"):
                st.write(f"Date: {l_date}")
                st.write(f"Type: {l_type}")
                st.write(f"Comment: {comment}")

                # Show approve/reject buttons for pending requests
                if status == "Waiting":
                    col1, col2 = st.columns(2)
                    if col1.button(f"Approve #{leave_id}"):
                        update_leave_status(leave_id, "Approved")
                        st.success(f"Leave #{leave_id} Approved")
                        st.rerun()
                    if col2.button(f"Reject #{leave_id}"):
                        update_leave_status(leave_id, "Rejected")
                        st.warning(f"Leave #{leave_id} Rejected")
                        st.rerun()
    else:
        st.info("No pending leave requests.")


# MAIN APPLICATION
def main():
    #Main function to run the Streamlit app
    st.set_page_config(page_title="Leave Management System")
    st.title("Leave Management System")

    # Initialize session state variables
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "username" not in st.session_state:
        st.session_state.username = ""

    # Check if user is logged in
    if not st.session_state.logged_in:
        show_login_page()
    else:
        username = st.session_state.username
        role = get_user_role(username)

        # Setup sidebar with user info
        sidebar_info = f"Logged in as: {username} ({role})"
        
        # Show manager name for employees
        if role == "Employee":
            manager = get_user_manager(username)
            if manager:
                sidebar_info += f"\nManager: **{manager}**"

        st.sidebar.title("Navigation")
        st.sidebar.markdown(sidebar_info)
        
        # Logout button
        if st.sidebar.button("Logout"):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.rerun()

        # Show appropriate dashboard based on user role
        if role == "Employee":
            show_employee_dashboard(username)
        elif role == "Manager":
            show_manager_dashboard(username)

# Run the application
if __name__ == "__main__":
    main()