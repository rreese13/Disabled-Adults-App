

import streamlit as st
import psycopg2
import pandas as pd

DB_URL = st.secrets["database"]["DB_URL"]

def get_connection():
    return psycopg2.connect(DB_URL)

# ----------------------
# GENERIC DB FUNCTIONS
# ----------------------

def fetch_all(table):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM {table};")
    cols = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    conn.close()
    return pd.DataFrame(rows, columns=cols)


def delete_row(table, row_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"DELETE FROM {table} WHERE id = %s", (row_id,))
    conn.commit()
    conn.close()


# Establish a connection and cursor for table creation
conn = get_connection()
cur = conn.cursor()

# Drop tables if they exist to ensure schema is always up-to-date
# Drop dependent tables first
cur.execute("DROP TABLE IF EXISTS attendance;")
cur.execute("DROP TABLE IF EXISTS adult_intern;")
cur.execute("DROP TABLE IF EXISTS class;")
cur.execute("DROP TABLE IF EXISTS internship;")
cur.execute("DROP TABLE IF EXISTS adults CASCADE;") # Use CASCADE to drop dependent objects too

# 1. Adults table
cur.execute("""
CREATE TABLE IF NOT EXISTS adults (
    id SERIAL PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    date_of_birth DATE,
    email VARCHAR(100) UNIQUE,
    phone VARCHAR(20),
    emergency_contact VARCHAR(100),
    disability_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")

# 2. Internship table
cur.execute("""
CREATE TABLE IF NOT EXISTS internship (
    id SERIAL PRIMARY KEY,
    organization_name VARCHAR(100) NOT NULL,
    position_title VARCHAR(100),
    location VARCHAR(150),
    supervisor_name VARCHAR(100),
    supervisor_contact VARCHAR(100),
    start_date DATE,
    end_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")

# 3. Adult_Intern (bridge table)
cur.execute("""
CREATE TABLE IF NOT EXISTS adult_intern (
    id SERIAL PRIMARY KEY,
    adult_id INTEGER REFERENCES adults(id) ON DELETE CASCADE,
    internship_id INTEGER REFERENCES internship(id) ON DELETE CASCADE,
    participation_status VARCHAR(50), -- e.g., Active, Completed, Dropped
    start_date DATE,
    end_date DATE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(adult_id, internship_id)
);
""")

# 4. Class table
cur.execute("""
CREATE TABLE IF NOT EXISTS class (
    id SERIAL PRIMARY KEY,
    class_name VARCHAR(100) NOT NULL,
    instructor_name VARCHAR(100),
    schedule VARCHAR(100), -- e.g., "Mon/Wed 10-11am"
    location VARCHAR(150),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")

# 5. Attendance (bridge table for Adults & Class)
cur.execute("""
CREATE TABLE IF NOT EXISTS attendance (
    id SERIAL PRIMARY KEY,
    adult_id INTEGER REFERENCES adults(id) ON DELETE CASCADE,
    class_id INTEGER REFERENCES class(id) ON DELETE CASCADE,
    attendance_date DATE NOT NULL,
    status VARCHAR(20), -- Present, Absent, Late
    participation_level VARCHAR(50), -- High, Medium, Low
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")

conn.commit()
cur.close()
conn.close()

print("✅ All 5 tables created successfully!")

import streamlit as st
import psycopg2
import pandas as pd

def get_connection():
    return psycopg2.connect(DB_URL)
# ----------------------
# GENERIC DB FUNCTIONS
# ----------------------
def fetch_all(table):
    conn = get_connection()
    df = pd.read_sql(f"SELECT * FROM {table}", conn)
    conn.close()
    return df

def delete_row(table, row_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"DELETE FROM {table} WHERE id=%s", (row_id,))
    conn.commit()
    cur.close()
    conn.close()

def update_row(table, row_id, data):
    conn = get_connection()
    cur = conn.cursor()
    set_clause = ", ".join([f"{col} = %s" for col in data.keys()])
    values = list(data.values()) + [row_id]
    cur.execute(f"UPDATE {table} SET {set_clause} WHERE id=%s", values)
    conn.commit()
    cur.close()
    conn.close()

def add_row(table, data):
    conn = get_connection()
    cur = conn.cursor()
    columns = ", ".join(data.keys())
    placeholders = ", ".join(["%s"] * len(data))
    values = list(data.values())
    cur.execute(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", values)
    conn.commit()
    cur.close()
    conn.close()

# ----------------------
# HOME PAGE
# ----------------------
def home_page():
    st.title("Dashboard")

    adults = fetch_all("adults")
    classes = fetch_all("class")
    internships = fetch_all("internship")

    st.subheader("Total Adults")
    st.metric("Adults Count", len(adults))

    st.subheader("Classes")
    st.write(classes["class_name"] if not classes.empty else "No classes available")

    st.subheader("Internships")
    st.write(internships["organization_name"] if not internships.empty else "No internships available")

# ----------------------
# GENERIC MANAGEMENT PAGE
# ----------------------
def management_page(table, display_columns, add_columns, title):
    st.title(title)

    df = fetch_all(table)
    if df.empty:
        st.write("No data available")

    # Dropdown filter & search
    st.subheader("Filter / Search")
    filter_column = add_columns[0]  # example: first column for dropdown
    options = ["All"] + sorted(df[filter_column].dropna().unique().tolist()) if not df.empty else ["All"]
    selected_option = st.selectbox(f"Filter by {filter_column}", options)
    search_query = st.text_input("Search by text")

    filtered_df = df.copy()
    if selected_option != "All":
        filtered_df = filtered_df[filtered_df[filter_column] == selected_option]
    if search_query.strip():
        filtered_df = filtered_df[
            filtered_df.apply(lambda row: row.astype(str).str.contains(search_query, case=False).any(), axis=1)
        ]

    # Add new record form
   with st.form(f"add_{table}"):
    st.subheader(f"Add New {title[:-1]}")
    new_data = {}

    for col in add_columns:
        if "date" in col.lower():
            new_data[col] = st.date_input(
                col,
                min_value=date(1900, 1, 1),
                max_value=date.today(),
                value=date(2000, 1, 1)
            )
        else:
            new_data[col] = st.text_input(col)

    submitted = st.form_submit_button("Add")

    if submitted:
        errors = [
            col for col in add_columns
            if (
                new_data[col] is None or
                (isinstance(new_data[col], str) and not new_data[col].strip())
            )
        ]

            if errors:
                for err in errors:
                    st.error(f"{err} is required.")
            else:
                add_row(table, new_data)
                st.success(f"{title[:-1]} added successfully!")
                st.experimental_rerun()

    # Display filtered table with Edit/Delete
    st.subheader(f"Existing {title}")
    for _, row in filtered_df.iterrows():
        cols = st.columns([3,1,1])
        with cols[0]:
            st.write({col: row[col] for col in display_columns})
        with cols[1]:
            if st.button("Edit", key=f"edit_{table}_{row['id']}"):
                st.session_state['edit_id'] = row['id']
        with cols[2]:
            if st.button("Delete", key=f"delete_{table}_{row['id']}"):
                st.session_state['delete_id'] = row['id']

    # Edit form
    if 'edit_id' in st.session_state:
        edit_id = st.session_state['edit_id']
        record = df[df['id'] == edit_id].iloc[0]
        st.subheader(f"Edit {title[:-1]} ID {edit_id}")
        edited_data = {}
        for col in add_columns:
            if "date" in col.lower():
                edited_data[col] = st.date_input(col, record[col])
            else:
                edited_data[col] = st.text_input(col, record[col])
        if st.button("Save Changes"):
            update_row(table, edit_id, edited_data)
            st.success("Updated successfully!")
            del st.session_state['edit_id']
            st.experimental_rerun()

    # Delete confirmation
    if 'delete_id' in st.session_state:
        delete_id = st.session_state['delete_id']
        st.warning(f"Are you sure you want to delete {title[:-1]} ID {delete_id}?")
        if st.button("Confirm Delete"):
            delete_row(table, delete_id)
            st.success("Deleted successfully!")
            del st.session_state['delete_id']
            st.experimental_rerun()
        if st.button("Cancel"):
            del st.session_state['delete_id']

# ----------------------
# NAVIGATION
# ----------------------
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Home", "Adults", "Classes", "Internships"])

if page == "Home":
    home_page()
elif page == "Adults":
    management_page(
        table="adults",
        display_columns=["id","first_name","last_name","date_of_birth","email","phone","emergency_contact","disability_notes"],
        add_columns=["first_name","last_name","date_of_birth","email","phone","emergency_contact","disability_notes"],
        title="Adults"
    )
elif page == "Classes":
    management_page(
        table="class",
        display_columns=["id","class_name","instructor_name","schedule"],
        add_columns=["class_name","instructor_name","schedule"],
        title="Classes"
    )
elif page == "Internships":
    management_page(
        table="internship",
        display_columns=["id","organization_name","position_title","location"],
        add_columns=["organization_name","position_title","location"],
        title="Internships"
    )

import streamlit as st

DB_URL = st.secrets["database"]["DB_URL"]
print(DB_URL)  # should print your database URL

from datetime import date

for col in add_columns:
    if "date" in col.lower():
        if "dob" in col.lower():  # special case for DOB
            new_data[col] = st.date_input(
                col,
                min_value=date(1900, 1, 1),
                max_value=date.today()
            )
        else:
            new_data[col] = st.date_input(col)
    else:
        new_data[col] = st.text_input(col)
