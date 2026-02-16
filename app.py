import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import io, zipfile, os

import db

UPLOAD_DIR = Path("data") / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

st.set_page_config(page_title="Laundry KPI App (v1)", layout="wide")


# ----------------- AUTH -----------------
def login_view():
    st.title("Laundry KPI App (v1)")
    st.caption("Local Laptop • SQLite • Admin + Wash Tech • Data Entry + Export (ZIP) + Dashboard")

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

    if submitted:
        user = db.validate_user(username, password)
        if user:
            st.session_state.user = user
            st.success(f"Welcome, {user.get('full_name') or user['username']} ({user['role']})")
            st.rerun()
        else:
            st.error("Invalid username/password.")

def require_login():
    if "user" not in st.session_state:
        login_view()
        st.stop()

def sidebar_menu():
    user = st.session_state.user
    st.sidebar.write(f"👤 **{user.get('full_name') or user['username']}**")
    st.sidebar.write(f"Role: `{user['role']}`")
    if st.sidebar.button("Logout"):
        st.session_state.pop("user", None)
        st.rerun()

    pages = ["Data Entry", "Export", "Dashboard"]
    if user["role"] == "admin":
        pages.insert(0, "Admin Panel")

    return st.sidebar.radio("Menu", pages)


# ----------------- ADMIN -----------------
def master_block(title, table_name):
    st.subheader(title)
    col1, col2 = st.columns([1, 1])

    with col1:
        new_name = st.text_input(f"Add {title} name", key=f"add_{table_name}")
        if st.button(f"Add {title}", key=f"btn_add_{table_name}"):
            if new_name.strip():
                db.add_master(table_name, new_name)
                st.success("Added.")
                st.rerun()

    with col2:
        rows = db.fetch_all(table_name)
        names = [r["name"] for r in rows]
        del_name = st.selectbox(f"Delete {title}", [""] + names, key=f"del_{table_name}")
        if st.button("Delete", key=f"btn_del_{table_name}"):
            if del_name:
                db.delete_master(table_name, del_name)
                st.warning("Deleted.")
                st.rerun()

    st.write("Current list:")
    st.dataframe(pd.DataFrame([{"name": r["name"]} for r in db.fetch_all(table_name)]), use_container_width=True)

def admin_panel():
    st.header("Admin Panel")

    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "Users", "Laundry", "Factory", "Department", "Customer", "Wash Category", "Wash Issues"
    ])

    with tab1:
        st.subheader("Create User")
        with st.form("create_user"):
            u = st.text_input("Username")
            p = st.text_input("Password")
            r = st.selectbox("Role", ["wash_tech", "admin"])
            fn = st.text_input("Full name (optional)")
            ok = st.form_submit_button("Create")
        if ok:
            try:
                db.create_user(u, p, r, fn)
                st.success("User created.")
            except Exception as e:
                st.error(f"Could not create user: {e}")

        st.info("Default admin: username=`admin`, password=`admin123`")

    with tab2:
        master_block("Laundry", "laundries")
    with tab3:
        master_block("Factory", "factories")
    with tab4:
        master_block("Department", "departments")
    with tab5:
        master_block("Customer", "customers")

    with tab6:
        st.subheader("Wash Category")
        new_cat = st.text_input("Add Wash Category (e.g., Garment Dye, Denim Wash)")
        if st.button("Add Category"):
            if new_cat.strip():
                db.add_wash_category(new_cat)
                st.success("Category added.")
                st.rerun()
        cats = db.get_wash_categories()
        st.dataframe(pd.DataFrame([{"category": x["name"]} for x in cats]), use_container_width=True)

    with tab7:
        master_block("Wash Issue", "wash_issues")


# ----------------- DATA ENTRY -----------------
def data_entry():
    st.header("Data Entry")

    laundries = [r["name"] for r in db.fetch_all("laundries")]
    factories = [r["name"] for r in db.fetch_all("factories")]
    departments = [r["name"] for r in db.fetch_all("departments")]
    customers = [r["name"] for r in db.fetch_all("customers")]
    issues = [r["name"] for r in db.fetch_all("wash_issues")]
    wash_categories = [r["name"] for r in db.get_wash_categories()]

    if not laundries or not factories or not departments or not customers or not wash_categories:
        st.warning("Admin must add Masters first: Laundry/Factory/Department/Customer/Wash Category.")
        return

    with st.form("entry_form", clear_on_submit=True):
        colA, colB, colC = st.columns(3)

        with colA:
            customer_name = st.selectbox("Customer", customers)
            style_no = st.text_input("Style No")
            contract_no = st.text_input("Contract No")

            customer_order_qty = st.number_input("UK(Customer) Order Qty", min_value=0, step=1)
            factory_order_qty = st.number_input("Factory Order Qty", min_value=0, step=1)

            wash_receive_qty = st.number_input("Wash Receive Qty", min_value=0, step=1)
            wash_delivery_qty = st.number_input("Wash Delivery Qty", min_value=0, step=1)

            total_shipment_qty = st.number_input("Total Shipment Qty", min_value=0, step=1)


        with colB:
            factory_name = st.selectbox("Factory", factories)
            laundry_name = st.selectbox("Laundry", laundries)
            department_name = st.selectbox("Department", departments)

            wash_category = st.selectbox("Wash Category", wash_categories)

            # ✅ PCD Date removed; planned & actual kept
            planned_pcd_date = st.date_input("Planned PCD Date", value=None, key="planned_pcd")
            actual_pcd_date = st.date_input("Actual PCD Date", value=None, key="actual_pcd")

            # ✅ Dates
            wash_receive_date = st.date_input("Wash Receive Date", value=None, key="wash_receive_date")

            shade_band_submission_date = st.date_input("Shade Band Submission Date", value=None, key="sb_submit")
            shade_band_approval_date = st.date_input("Shade Band Approval Date", value=None, key="sb_approval")

            # ✅ Wash Closing Date এখন approval এর পরে
            wash_closing_date = st.date_input("Wash Closing Date", value=None, key="wash_closing_date")


            agreed_ex_factory = st.date_input("Agreed Ex Factory", value=None, key="agreed_ex_factory")
            actual_ex_factory = st.date_input("Actual Ex Factory", value=None, key="actual_ex_factory")

        with colC:
            subcontract_washing = st.selectbox("Subcontract washing", ["NO", "YES"], index=0)
            st.markdown("**Top 3 Wash Issues**")
            issue_1 = st.selectbox("Issue 1", [""] + issues)
            issue_2 = st.selectbox("Issue 2", [""] + issues, key="i2")
            issue_3 = st.selectbox("Issue 3", [""] + issues, key="i3")

            other_issue = st.checkbox("Other Issue?")
            other_issue_text = ""
            if other_issue:
                other_issue_text = st.text_input("Specify other issue (max 20 chars)", max_chars=20)

            remarks = st.text_area("Remarks (Wash Tech Comment)", height=120)
            image_file = st.file_uploader("Upload Style Image (jpg/png)", type=["jpg", "jpeg", "png"])

        submitted = st.form_submit_button("Save Entry")

    if submitted:
        image_path = ""
        if image_file is not None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = f"{ts}_{image_file.name}".replace(" ", "_")
            out_path = UPLOAD_DIR / safe_name
            out_path.write_bytes(image_file.getbuffer())
            image_path = out_path.as_posix()

        entry = {
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "created_by": st.session_state.user["username"],

            "customer_name": customer_name,
            "style_no": style_no.strip(),
            "contract_no": contract_no.strip(),

            "customer_order_qty": int(customer_order_qty),
            "factory_order_qty": int(factory_order_qty),
            "total_shipment_qty": int(total_shipment_qty),
            "wash_receive_qty": int(wash_receive_qty),
            "wash_delivery_qty": int(wash_delivery_qty),

            "planned_pcd_date": str(planned_pcd_date) if planned_pcd_date else None,
            "actual_pcd_date": str(actual_pcd_date) if actual_pcd_date else None,

            "wash_receive_date": str(wash_receive_date) if wash_receive_date else None,
            "wash_closing_date": str(wash_closing_date) if wash_closing_date else None,

            "shade_band_submission_date": str(shade_band_submission_date) if shade_band_submission_date else None,
            "shade_band_approval_date": str(shade_band_approval_date) if shade_band_approval_date else None,

            "agreed_ex_factory": str(agreed_ex_factory) if agreed_ex_factory else None,
            "actual_ex_factory": str(actual_ex_factory) if actual_ex_factory else None,

            "factory_name": factory_name,
            "laundry_name": laundry_name,
            "subcontract_washing": subcontract_washing,

            "department_name": department_name,
            "wash_category": wash_category,


            "issue_1": issue_1,
            "issue_2": issue_2,
            "issue_3": issue_3,
            "other_issue_text": other_issue_text.strip(),

            "remarks": remarks.strip(),
            "image_path": image_path,
        }

        db.save_entry(entry)
        st.success("✅ Saved successfully!")


# ----------------- EXPORT (ZIP: CSV + IMAGES) -----------------
def export_view():
    st.header("Export (ZIP: CSV + Images)")

    col1, col2, col3 = st.columns([1, 1, 1.2])
    with col1:
        preset = st.selectbox("Quick Range", ["Custom", "Last 1 Month", "Last 6 Months", "Last 1 Year"])
    with col2:
        d_from = st.date_input("From", value=date.today() - relativedelta(months=1))
    with col3:
        d_to = st.date_input("To", value=date.today())

    if preset != "Custom":
        if preset == "Last 1 Month":
            d_from = date.today() - relativedelta(months=1)
        elif preset == "Last 6 Months":
            d_from = date.today() - relativedelta(months=6)
        elif preset == "Last 1 Year":
            d_from = date.today() - relativedelta(years=1)
        d_to = date.today()

    data = db.read_entries(str(d_from), str(d_to))
    df = pd.DataFrame(data)

    st.write(f"Rows: **{len(df)}**")
    if len(df) == 0:
        st.info("No data in this range.")
        return

    if "image_path" not in df.columns:
        df["image_path"] = ""

    def rel_img(p):
        if not p:
            return ""
        return "images/" + Path(p).name

    df["image_rel_path"] = df["image_path"].apply(rel_img)

    st.dataframe(df, use_container_width=True, height=350)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # CSV
        zf.writestr("entries.csv", df.to_csv(index=False).encode("utf-8"))

        # Images folder
        for p in df["image_path"].dropna().unique():
            if p and os.path.exists(p):
                zf.write(p, arcname=f"images/{Path(p).name}")

        zf.writestr(
            "README.txt",
            "Unzip this file.\n"
            "entries.csv contains image_rel_path column.\n"
            "Images are stored inside images/ folder.\n"
        )

    zip_buffer.seek(0)

    st.download_button(
        "⬇️ Download ZIP (CSV + Images)",
        data=zip_buffer.getvalue(),
        file_name=f"laundry_export_{d_from}_to_{d_to}.zip",
        mime="application/zip"
    )


# ----------------- DASHBOARD -----------------
def dashboard_view():
    st.header("Dashboard")

    factories = ["All"] + [r["name"] for r in db.fetch_all("factories")]
    laundries = ["All"] + [r["name"] for r in db.fetch_all("laundries")]

    c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
    with c1:
        factory_filter = st.selectbox("Factory", factories)
    with c2:
        laundry_filter = st.selectbox("Laundry", laundries)
    with c3:
        d_from = st.date_input("From", value=date.today() - relativedelta(months=6), key="dash_from")
    with c4:
        d_to = st.date_input("To", value=date.today(), key="dash_to")

    data = db.read_entries(str(d_from), str(d_to))
    if not data:
        st.info("No data in this range.")
        return

    df = pd.DataFrame(data)

    # Filters
    if factory_filter != "All":
        df = df[df.get("factory_name", "") == factory_filter]
    if laundry_filter != "All":
        df = df[df.get("laundry_name", "") == laundry_filter]

    if df.empty:
        st.warning("No data after applying filters.")
        return

    # Numeric conversions
    df["factory_order"] = pd.to_numeric(df.get("factory_order_qty", 0), errors="coerce").fillna(0)
    df["uk_order"] = pd.to_numeric(df.get("customer_order_qty", 0), errors="coerce").fillna(0)
    df["ship_qty"] = pd.to_numeric(df.get("total_shipment_qty", 0), errors="coerce").fillna(0)

    total_factory_order = df["factory_order"].sum()
    total_uk_order = df["uk_order"].sum()
    total_ship = df["ship_qty"].sum()

    factory_ship_pct = (total_ship / total_factory_order * 100) if total_factory_order else 0
    uk_ship_pct = (total_ship / total_uk_order * 100) if total_uk_order else 0

    k1, k2, k3 = st.columns(3)
    k1.metric("Factory Order vs Shipment %", f"{factory_ship_pct:.1f}%")
    k2.metric("UK(Customer) Order vs Shipment %", f"{uk_ship_pct:.1f}%")
    k3.metric("Total Shipment Qty", f"{int(total_ship)}")

    st.divider()

    # All laundry performance (single dashboard)
    st.subheader("All Laundries Performance (Order vs Shipment %)")

    perf = df.groupby("laundry_name", as_index=False).agg(
        factory_order=("factory_order", "sum"),
        uk_order=("uk_order", "sum"),
        shipment=("ship_qty", "sum"),
    )

    perf["shipment_vs_factory_%"] = perf.apply(
        lambda r: (r["shipment"] / r["factory_order"] * 100) if r["factory_order"] else 0, axis=1
    )
    perf["shipment_vs_uk_%"] = perf.apply(
        lambda r: (r["shipment"] / r["uk_order"] * 100) if r["uk_order"] else 0, axis=1
    )
    perf = perf.sort_values("shipment_vs_factory_%", ascending=False)

    st.dataframe(perf, use_container_width=True)
    st.bar_chart(perf.set_index("laundry_name")[["shipment_vs_factory_%"]])

    st.divider()

    # Top 3 issues (defects) per laundry
    st.subheader("Top 3 Wash Issues (Defects) by Laundry")

    for col in ["issue_1", "issue_2", "issue_3", "other_issue_text"]:
        if col not in df.columns:
            df[col] = ""

    long_rows = []
    for _, r in df.iterrows():
        lname = (r.get("laundry_name") or "").strip()
        for col in ["issue_1", "issue_2", "issue_3"]:
            v = (r.get(col) or "").strip()
            if v:
                long_rows.append((lname, v))
        other = (r.get("other_issue_text") or "").strip()
        if other:
            long_rows.append((lname, other))

    if not long_rows:
        st.info("No issues found in selected range/filters.")
        return

    long_df = pd.DataFrame(long_rows, columns=["laundry_name", "issue"])
    top = long_df.groupby(["laundry_name", "issue"]).size().reset_index(name="count")
    top = top.sort_values(["laundry_name", "count"], ascending=[True, False])
    top3 = top.groupby("laundry_name").head(3)

    st.dataframe(top3, use_container_width=True)


# ----------------- MAIN -----------------
def main():
    db.init_db()
    require_login()

    page = sidebar_menu()

    if page == "Admin Panel":
        admin_panel()
    elif page == "Data Entry":
        data_entry()
    elif page == "Export":
        export_view()
    elif page == "Dashboard":
        dashboard_view()

if __name__ == "__main__":
    main()
