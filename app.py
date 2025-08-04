import streamlit as st
import json
import os
from datetime import datetime
import openpyxl
import pandas as pd

DATA_FILE = "inventory_data.json"

# ====== Utilitas ======
def timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {
        "users": {
            "admin": {"password": "admin123", "role": "admin"},
            "user": {"password": "user123", "role": "user"},
        },
        "inventory": {},
        "item_counter": 0,
        "pending_requests": [],
        "history": [],
    }

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# ====== Session State ======
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.role = ""
if "req_in_items" not in st.session_state:
    st.session_state.req_in_items = []
if "req_out_items" not in st.session_state:
    st.session_state.req_out_items = []

data = load_data()

# ====== Login Page ======
if not st.session_state.logged_in:
    st.title("🔐 Login Inventory System")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        user = data["users"].get(username)
        if user and user["password"] == password:
            st.session_state.logged_in = True
            st.session_state.username = username
            st.session_state.role = user["role"]
            st.success(f"Login berhasil sebagai {user['role'].upper()}")
            st.rerun()
        else:
            st.error("❌ Username atau password salah.")

# ====== Main Menu ======
else:
    role = st.session_state.role
    st.sidebar.title("Menu")
    st.sidebar.write(f"👋 Halo, {st.session_state.username} ({role})")

    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.role = ""
        st.rerun()

    # ==== Menu Admin ====
    if role == "admin":
        menu = st.sidebar.radio("Pilih Menu", [
            "Lihat Stok Barang",
            "Tambah Master Barang",
            "Approve Request",
            "Lihat Riwayat User",
            "Export Laporan ke Excel"
        ])

        if menu == "Lihat Stok Barang":
            st.header("📦 Stok Barang")
            if data["inventory"]:
                df = pd.DataFrame([
                    {"Kode": code, "Nama Barang": item["name"], "Qty": item["qty"]}
                    for code, item in data["inventory"].items()
                ])
                st.dataframe(df, use_container_width=True)
            else:
                st.info("Belum ada barang di inventory.")

        elif menu == "Tambah Master Barang":
            st.header("➕ Tambah Master Barang")
            name = st.text_input("Nama Barang")
            qty = st.number_input("Jumlah Stok Awal", min_value=0, step=1)
            if st.button("Tambah Barang"):
                data["item_counter"] += 1
                code = f"ITM-{data['item_counter']:04d}"
                data["inventory"][code] = {"name": name, "qty": qty}
                data["history"].append({
                    "action": "ADD_ITEM",
                    "item": name,
                    "qty": qty,
                    "stock": qty,
                    "user": st.session_state.username,
                    "event": "-",
                    "timestamp": timestamp()
                })
                save_data(data)
                st.success(f"Barang '{name}' berhasil ditambahkan dengan kode {code}")
                st.rerun()

        elif menu == "Approve Request":
            st.header("✅ Approve Request")
            if data["pending_requests"]:
                df = pd.DataFrame(data["pending_requests"])
                df_display = df[["user","item","type","qty","timestamp","event"]] if "event" in df else df
                selected = st.multiselect("Pilih request untuk di-approve", df_display.index, format_func=lambda x: f"{df_display.iloc[x].to_dict()}")
                
                st.dataframe(df_display, use_container_width=True)

                if st.button("Approve Selected") and selected:
                    for idx in sorted(selected, reverse=True):
                        req = data["pending_requests"].pop(idx)
                        for code, item in data["inventory"].items():
                            if item["name"] == req["item"]:
                                if req["type"] == "IN":
                                    item["qty"] += req["qty"]
                                else:
                                    item["qty"] -= req["qty"]

                                data["history"].append({
                                    "action": f"APPROVE_{req['type']}",
                                    "item": req["item"],
                                    "qty": req["qty"],
                                    "stock": item["qty"],
                                    "user": req["user"],
                                    "event": req.get("event","-"),
                                    "timestamp": timestamp()
                                })
                    save_data(data)
                    st.success("Request terpilih berhasil di-approve.")
                    st.rerun()
            else:
                st.info("Tidak ada pending request.")

        elif menu == "Lihat Riwayat User":
            st.header("📜 Riwayat User (Stock Card)")
            if data["history"]:
                df = pd.DataFrame(data["history"])
                df_display = df[["action","item","qty","stock","user","event","timestamp"]]
                st.dataframe(df_display, use_container_width=True)
            else:
                st.info("Belum ada riwayat.")

        elif menu == "Export Laporan ke Excel":
            st.header("📤 Export Laporan ke Excel")
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(["Kode", "Nama Barang", "Qty"])
            for code, item in data["inventory"].items():
                ws.append([code, item["name"], item["qty"]])
            file_name = "inventory_report.xlsx"
            wb.save(file_name)
            st.success(f"Laporan berhasil diexport ke '{file_name}'")

    # ==== Menu User ====
    elif role == "user":
        menu = st.sidebar.radio("Pilih Menu", [
            "Request Barang IN",
            "Request Barang OUT"
        ])

        items = list(data["inventory"].values())

        # Request Barang IN
        if menu == "Request Barang IN":
            st.header("📥 Request Barang Masuk (Multi Item)")
            if items:
                col1, col2 = st.columns(2)
                idx = col1.selectbox("Pilih Barang", range(len(items)), format_func=lambda x: f"{items[x]['name']} (Stok: {items[x]['qty']})")
                qty = col2.number_input("Jumlah", min_value=1, step=1)

                if st.button("Tambah Item IN"):
                    st.session_state.req_in_items.append({
                        "item": items[idx]["name"],
                        "qty": qty,
                        "event": "-"
                    })

                # Tabel preview
                if st.session_state.req_in_items:
                    st.subheader("Daftar Item Request IN")
                    df_req_in = pd.DataFrame(st.session_state.req_in_items)
                    st.dataframe(df_req_in, use_container_width=True)

                    # Hapus item
                    remove_idx = st.number_input("Hapus item ke-", min_value=0, max_value=len(st.session_state.req_in_items), step=1)
                    if st.button("Hapus Item") and remove_idx>0:
                        st.session_state.req_in_items.pop(remove_idx-1)
                        st.rerun()

                    # Submit
                    if st.button("Ajukan Semua Request IN"):
                        for req in st.session_state.req_in_items:
                            data["pending_requests"].append({
                                "user": st.session_state.username,
                                "item": req["item"],
                                "qty": req["qty"],
                                "type": "IN",
                                "timestamp": timestamp(),
                                "event": "-"
                            })
                        st.session_state.req_in_items = []
                        save_data(data)
                        st.success("Request IN berhasil diajukan.")
                        st.rerun()
            else:
                st.info("Belum ada barang di inventory.")

        # Request Barang OUT
        elif menu == "Request Barang OUT":
            st.header("📤 Request Barang Keluar (Multi Item)")
            if items:
                # Event Dropdown atau Input Baru
                existing_events = list({
                    h.get("event") for h in data["history"] + data["pending_requests"]
                    if h.get("event") and h.get("event") != "-"
                })
                existing_events.sort()

                event_choice = st.selectbox(
                    "Pilih Event",
                    ["➕ Tambah Event Baru..."] + existing_events
                )

                if event_choice == "➕ Tambah Event Baru...":
                    event = st.text_input("Nama Event Baru")
                else:
                    event = event_choice

                # Input barang jika event sudah valid
                if event:
                    col1, col2 = st.columns(2)
                    idx = col1.selectbox("Pilih Barang", range(len(items)), format_func=lambda x: f"{items[x]['name']} (Stok: {items[x]['qty']})")
                    qty = col2.number_input("Jumlah", min_value=1, step=1)

                    if st.button("Tambah Item OUT"):
                        st.session_state.req_out_items.append({
                            "item": items[idx]["name"],
                            "qty": qty,
                            "event": event
                        })

                # Preview table
                if st.session_state.req_out_items:
                    st.subheader("Daftar Item Request OUT")
                    df_req_out = pd.DataFrame(st.session_state.req_out_items)
                    st.dataframe(df_req_out, use_container_width=True)

                    # Hapus item
                    remove_idx = st.number_input("Hapus item OUT ke-", min_value=0, max_value=len(st.session_state.req_out_items), step=1)
                    if st.button("Hapus Item OUT") and remove_idx>0:
                        st.session_state.req_out_items.pop(remove_idx-1)
                        st.rerun()

                    # Submit
                    if st.button("Ajukan Semua Request OUT"):
                        for req in st.session_state.req_out_items:
                            data["pending_requests"].append({
                                "user": st.session_state.username,
                                "item": req["item"],
                                "qty": req["qty"],
                                "type": "OUT",
                                "timestamp": timestamp(),
                                "event": req["event"]
                            })
                        st.session_state.req_out_items = []
                        save_data(data)
                        st.success("Request OUT berhasil diajukan.")
                        st.rerun()
            else:
                st.info("Belum ada barang di inventory.")
