import os
from datetime import date
import pandas as pd
import plotly.express as px
import streamlit as st
from db import init_db, seed_historical_data, get_conn, load_incidents, count_incidents, add_incident, update_incident, import_dataframe, audit
from auth import user_count, create_user, authenticate, require_login, logout, reset_password
from predictor import forecast_for_terminal, district_risk_table, normalize_component, COMPONENTS

st.set_page_config(page_title="ATM Sentinel | Predictive Maintenance", page_icon="🏧", layout="wide",
                   initial_sidebar_state="expanded")
init_db()
seed_historical_data()

st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@600;700;800&display=swap');
html, body, [class*="css"] {font-family:'DM Sans',sans-serif;}
.block-container{padding-top:1.4rem;padding-bottom:2rem;max-width:1500px}
h1,h2,h3{font-family:'Manrope',sans-serif;letter-spacing:-.4px}
.hero{background:linear-gradient(120deg,#102A43,#176B87);padding:28px 30px;border-radius:18px;color:white;margin-bottom:18px}
.hero h1{color:white;font-size:2.1rem;margin:0}.hero p{color:#d9eaf2;margin:.45rem 0 0}
.kpi{background:white;border:1px solid #e5edf3;border-radius:14px;padding:17px 19px;box-shadow:0 4px 16px rgba(16,42,67,.04)}
.kpi .label{font-size:.82rem;color:#607789}.kpi .value{font-family:Manrope;font-size:1.8rem;font-weight:800;color:#102A43}
.kpi .hint{font-size:.78rem;color:#78909c}
.small-note{color:#667d8d;font-size:.85rem}
div[data-testid="stSidebar"]{border-right:1px solid #e5edf3}
.stButton>button{border-radius:9px;font-weight:600}
</style>""", unsafe_allow_html=True)

def hero(title, subtitle):
    st.markdown(f'<div class="hero"><h1>{title}</h1><p>{subtitle}</p></div>',unsafe_allow_html=True)

def kpi(label,value,hint=""):
    st.markdown(f'<div class="kpi"><div class="label">{label}</div><div class="value">{value}</div><div class="hint">{hint}</div></div>',unsafe_allow_html=True)

def login_screen():
    st.markdown("<br><br>",unsafe_allow_html=True)
    left,mid,right=st.columns([1,1.15,1])
    with mid:
        st.markdown('<div class="hero"><h1>🏧 ATM Sentinel</h1><p>Predictive maintenance • Incident intelligence • District operations</p></div>',unsafe_allow_html=True)
        if user_count()==0:
            st.subheader("Create the first administrator")
            st.info("First-run setup: create your administrator account. Do this only on a trusted deployment.")
            with st.form("bootstrap"):
                name=st.text_input("Full name")
                username=st.text_input("Admin username")
                p1=st.text_input("Password (minimum 10 characters)",type="password")
                p2=st.text_input("Confirm password",type="password")
                submitted=st.form_submit_button("Create administrator",use_container_width=True)
            if submitted:
                if p1!=p2: st.error("Passwords do not match.")
                else:
                    try:
                        create_user(username,p1,"admin","",name)
                        st.success("Administrator created. Sign in below.")
                        st.rerun()
                    except Exception as e: st.error(str(e))
        else:
            with st.form("login"):
                username=st.text_input("Username")
                password=st.text_input("Password",type="password")
                submitted=st.form_submit_button("Sign in",use_container_width=True)
            if submitted:
                user=authenticate(username,password)
                if user:
                    st.session_state.user=user
                    audit(username,"login")
                    st.rerun()
                else: st.error("Invalid username/password or inactive account.")
        st.caption("Access is role-based. District accounts can only access their assigned district.")

if "user" not in st.session_state:
    login_screen()
    st.stop()

user=require_login()
role=user["role"]
district=user["district"] if role=="district" else None
df=load_incidents(district)
all_df=load_incidents() if role in ("admin","manager") else df
districts=sorted([x for x in all_df.district.dropna().astype(str).unique() if x.strip()])
st.sidebar.markdown("## 🏧 ATM Sentinel")
st.sidebar.caption("Predictive maintenance platform")
st.sidebar.divider()
st.sidebar.markdown(f"**{user['full_name'] or user['username']}**")
st.sidebar.caption(f"{role.title()}"+(f" · {user['district']}" if district else " · All districts"))
pages=["Overview","ATM Forecast","Incident Register","Machine Explorer"]
if role in ("admin","manager"): pages += ["District Analytics"]
if role=="admin": pages += ["User Administration","Data Management","Audit Log"]
page=st.sidebar.radio("WORKSPACE",pages,label_visibility="visible")
st.sidebar.divider()
st.sidebar.caption(f"{len(df):,} visible incident records")
if st.sidebar.button("Sign out",use_container_width=True):
    logout()

if page=="Overview":
    hero("ATM Operations Overview","A live view of registered ATM incidents, recurring faults and maintenance exposure.")
    total=len(df); machines=df.terminal_id.nunique() if total else 0
    pending=int(df.status.astype(str).str.lower().isin(["new","pending","open"]).sum()) if total else 0
    repeat=int((df.terminal_id.value_counts()>1).sum()) if total else 0
    c=st.columns(4)
    with c[0]: kpi("Incident records",f"{total:,}","Visible data scope")
    with c[1]: kpi("Unique ATMs",f"{machines:,}","Machines with registered history")
    with c[2]: kpi("Open / pending",f"{pending:,}","Requires operational follow-up")
    with c[3]: kpi("Repeat-incident ATMs",f"{repeat:,}","More than one recorded case")
    if total:
        st.write("")
        a,b=st.columns([1.25,1])
        with a:
            st.subheader("Incident volume by district")
            counts=df.groupby("district").size().sort_values(ascending=False).reset_index(name="Incidents")
            fig=px.bar(counts.head(15),x="Incidents",y="district",orientation="h",color="Incidents",
                       color_continuous_scale=["#b9dce8","#176B87"])
            fig.update_layout(height=430, yaxis_title="",xaxis_title="Registered incidents",showlegend=False,
                              coloraxis_showscale=False,margin=dict(l=0,r=10,t=10,b=10))
            st.plotly_chart(fig,use_container_width=True)
        with b:
            st.subheader("Most reported components")
            comp=df.component.value_counts().head(10).reset_index()
            comp.columns=["Component","Incidents"]
            fig=px.pie(comp,names="Component",values="Incidents",hole=.58)
            fig.update_layout(height=430,margin=dict(l=0,r=0,t=10,b=10),legend=dict(orientation="h",y=-.15))
            st.plotly_chart(fig,use_container_width=True)
        st.subheader("ATMs with the most repeat incidents")
        top=df.groupby(["terminal_id","terminal_name","district"]).size().reset_index(name="Incidents").sort_values("Incidents",ascending=False).head(12)
        st.dataframe(top,use_container_width=True,hide_index=True)
    else: st.info("No incident data is loaded yet. An administrator can import the provided CSV under Data Management.")

elif page=="ATM Forecast":
    hero("ATM Failure Forecast","Estimate the next most likely component issue from each ATM's registered incident history.")
    if df.empty: st.warning("No incidents are available in your district.")
    else:
        ids=sorted(df.terminal_id.astype(str).unique())
        chosen=st.selectbox("Select ATM terminal",ids)
        machine=df[df.terminal_id.astype(str)==chosen]
        label=machine.terminal_name.iloc[0] if len(machine) else chosen
        st.markdown(f"### {label}  ·  `{chosen}`")
        forecast,meta=forecast_for_terminal(df,chosen,district)
        a,b,c,d=st.columns(4)
        with a: kpi("Historical incidents",meta["incidents"],"For selected terminal")
        with b: kpi("Distinct components",meta["unique_components"],"Different normalized fault types")
        with c: kpi("Repeat burden",f'{meta["repeat_rate"]}%',"Share of cases in repeated categories")
        with d: kpi("Signal strength",meta["level"],"History-based indicator")
        st.write("")
        if forecast.empty:
            st.info("Not enough history to generate a forecast.")
        else:
            st.subheader("Most likely future component categories")
            st.caption("Relative likelihood is a normalized ranking score based on recency-weighted machine history plus a small district-level prior. It is not a calibrated probability of failure.")
            st.dataframe(forecast[["Component","Relative likelihood (%)","Weighted machine history","District baseline"]].rename(columns={"Relative likelihood (%)":"Relative score (%)"}),
                         use_container_width=True,hide_index=True)
            fig=px.bar(forecast.sort_values("Relative likelihood (%)"),x="Relative likelihood (%)",y="Component",
                       orientation="h",color="Relative likelihood (%)",color_continuous_scale=["#b9dce8","#176B87"])
            fig.update_layout(height=330,showlegend=False,coloraxis_showscale=False,margin=dict(l=0,r=0,t=10,b=10))
            st.plotly_chart(fig,use_container_width=True)
            lead=forecast.iloc[0]["Component"]
            st.success(f"Maintenance attention: inspect **{lead}** first, then verify the physical condition before replacing parts.")
            st.markdown("**Recommended workflow**")
            st.write("1. Inspect the component and check error codes / electronic journal where applicable.")
            st.write("2. Confirm the fault with a technician before ordering or replacing hardware.")
            st.write("3. Record the confirmed diagnosis and resolution as a new incident to improve future forecasts.")
        st.subheader("Incident history for this ATM")
        hist=machine.sort_values("record_date",ascending=False)
        st.dataframe(hist[["record_date","problem","component","status","comment"]],use_container_width=True,hide_index=True)

elif page=="Incident Register":
    hero("Incident Register","Review and register ATM incidents. District users are restricted to their assigned district.")
    with st.expander("＋ Register a new incident",expanded=False):
        with st.form("new_incident"):
            c1,c2=st.columns(2)
            with c1:
                tid=st.text_input("Terminal ID *")
                tname=st.text_input("ATM / branch name")
                prob=st.selectbox("Problem category",COMPONENTS)
                custom=st.text_input("Raw problem description (optional)")
            with c2:
                dist=st.selectbox("District", [district] if district else districts)
                status=st.selectbox("Status",["new","pending","solved"])
                rdate=st.date_input("Incident date",value=date.today())
                comment=st.text_area("Technician notes / symptoms")
            save=st.form_submit_button("Save incident",type="primary")
        if save:
            if not tid.strip(): st.error("Terminal ID is required.")
            else:
                try:
                    add_incident({"terminal_id":tid,"terminal_name":tname,"problem":custom.strip() or prob,
                                  "district":dist,"status":status,"record_date":rdate.isoformat(),"comment":comment},user["username"])
                    st.success("Incident registered.")
                    st.rerun()
                except Exception as e: st.error(f"Could not save incident: {e}")
    if len(df):
        with st.expander("Update an existing incident"):
            options={f"#{int(row.id)} · {row.terminal_id} · {row.problem} · {row.record_date}":int(row.id)
                     for row in df.sort_values("record_date",ascending=False).head(500).itertuples()}
            with st.form("update_incident"):
                selected_label=st.selectbox("Incident",list(options.keys()))
                new_status=st.selectbox("New status",["new","pending","solved"])
                new_comment=st.text_area("Updated technician notes")
                update=st.form_submit_button("Save incident update")
            if update:
                try:
                    update_incident(options[selected_label],new_status,new_comment,user["username"],district)
                    st.success("Incident updated.")
                    st.rerun()
                except Exception as e: st.error(str(e))
    st.subheader("Search and filter")
    f1,f2,f3=st.columns(3)
    with f1: search=st.text_input("Terminal ID / ATM name")
    with f2: comps=st.multiselect("Component",sorted(df.component.unique()) if len(df) else [])
    with f3: statuses=st.multiselect("Status",sorted(df.status.astype(str).unique()) if len(df) else [])
    view=df.copy()
    if search: view=view[view.terminal_id.astype(str).str.contains(search,case=False)|view.terminal_name.astype(str).str.contains(search,case=False)]
    if comps: view=view[view.component.isin(comps)]
    if statuses: view=view[view.status.isin(statuses)]
    st.caption(f"{len(view):,} matching incidents")
    st.dataframe(view[["record_date","terminal_id","terminal_name","district","problem","component","status","comment"]],
                 use_container_width=True,hide_index=True)
    st.download_button("Download filtered CSV",view.to_csv(index=False).encode("utf-8"),"atm_incidents.csv","text/csv")

elif page=="Machine Explorer":
    hero("Machine Explorer","Investigate the service history and recurring component patterns of an individual ATM.")
    if df.empty: st.info("No incident data available.")
    else:
        tid=st.selectbox("ATM terminal ID",sorted(df.terminal_id.unique()))
        m=df[df.terminal_id==tid].copy()
        x,y=st.columns([1,1])
        with x:
            st.subheader(m.terminal_name.iloc[0])
            st.write(f"**Terminal:** `{tid}`")
            st.write(f"**District:** {m.district.iloc[0]}")
            st.metric("Total registered incidents",len(m))
        with y:
            vc=m.component.value_counts().rename_axis("Component").reset_index(name="Cases")
            fig=px.bar(vc,x="Component",y="Cases",color="Cases",color_continuous_scale=["#b9dce8","#176B87"])
            fig.update_layout(height=300,showlegend=False,coloraxis_showscale=False,xaxis_tickangle=-25)
            st.plotly_chart(fig,use_container_width=True)
        st.subheader("Full service history")
        st.dataframe(m.sort_values("record_date",ascending=False),use_container_width=True,hide_index=True)

elif page=="District Analytics":
    hero("District Analytics","Compare all districts and identify where recurring ATM faults are concentrated.")
    if df.empty: st.info("No data.")
    else:
        a,b=st.columns(2)
        with a:
            st.subheader("Incident distribution")
            dist=df.district.value_counts().reset_index()
            dist.columns=["District","Incidents"]
            fig=px.bar(dist,x="District",y="Incidents",color="Incidents",color_continuous_scale=["#b9dce8","#176B87"])
            fig.update_layout(height=400,xaxis_tickangle=-35,showlegend=False,coloraxis_showscale=False)
            st.plotly_chart(fig,use_container_width=True)
        with b:
            st.subheader("Status by district")
            cross=df.pivot_table(index="district",columns="status",values="id",aggfunc="count",fill_value=0).reset_index()
            fig=px.bar(cross,x="district",y=[c for c in cross.columns if c!="district"],barmode="stack")
            fig.update_layout(height=400,xaxis_tickangle=-35,legend_title="Status")
            st.plotly_chart(fig,use_container_width=True)
        st.subheader("Highest repeat-incident ATM exposure")
        risk=district_risk_table(df)
        st.dataframe(risk,use_container_width=True,hide_index=True)
        st.download_button("Export district report",risk.to_csv(index=False).encode("utf-8"),"district_atm_risk.csv","text/csv")

elif page=="User Administration":
    hero("User Administration","Create accounts and control access to operational data.")
    with st.expander("＋ Add user",expanded=True):
        with st.form("add_user"):
            c1,c2=st.columns(2)
            with c1:
                uname=st.text_input("Username")
                fullname=st.text_input("Full name")
                pw=st.text_input("Temporary password (minimum 10 characters)",type="password")
            with c2:
                urole=st.selectbox("Role",["district","manager","admin"])
                udistrict=st.selectbox("Assigned district",districts) if urole=="district" and districts else ""
            submitted=st.form_submit_button("Create account",type="primary")
        if submitted:
            try:
                create_user(uname,pw,urole,udistrict,fullname)
                audit(user["username"],"user_created",f"{uname}:{urole}:{udistrict}")
                st.success(f"Created {uname}. Share the temporary password securely.")
                st.rerun()
            except Exception as e: st.error(str(e))
    with get_conn() as conn:
        users=pd.read_sql_query("SELECT id,username,full_name,role,district,is_active,created_at FROM users ORDER BY id",conn)
    st.subheader("Registered users")
    st.dataframe(users,use_container_width=True,hide_index=True)
    if len(users):
        with st.expander("Reset a user's password"):
            with st.form("reset_user_password"):
                reset_user=st.selectbox("Account",users.username.tolist(),key="reset_username")
                new_pw=st.text_input("New password (minimum 10 characters)",type="password")
                reset=st.form_submit_button("Reset password")
            if reset:
                try:
                    reset_password(reset_user,new_pw)
                    audit(user["username"],"password_reset",reset_user)
                    st.success(f"Password reset for {reset_user}. Share the new password securely.")
                except Exception as e: st.error(str(e))
        with st.form("user_status"):
            selected=st.selectbox("Select account",users.username.tolist())
            active=st.selectbox("Account status",["Active","Inactive"])
            change=st.form_submit_button("Update account status")
        if change:
            if selected==user["username"] and active=="Inactive": st.error("You cannot deactivate your own active session.")
            else:
                with get_conn() as conn:
                    conn.execute("UPDATE users SET is_active=? WHERE username=?",(1 if active=="Active" else 0,selected))
                audit(user["username"],"user_status_changed",f"{selected}:{active}")
                st.success("Account updated."); st.rerun()

elif page=="Data Management":
    hero("Data Management","Import historical incident data and maintain the predictive maintenance dataset.")
    st.metric("Total records in system",f"{count_incidents():,}")
    st.subheader("Import CSV")
    st.write("Required columns: `terminal_id`, `problem`, `district`. Other columns are optional. Existing rows are not automatically deduplicated.")
    uploaded=st.file_uploader("Choose incident CSV",type=["csv"])
    if uploaded:
        try:
            preview=pd.read_csv(uploaded)
            st.write(f"Preview · {len(preview):,} rows")
            st.dataframe(preview.head(10),use_container_width=True,hide_index=True)
            if st.button("Import records",type="primary"):
                n=import_dataframe(preview,user["username"])
                st.success(f"Imported {n:,} rows.")
                st.rerun()
        except Exception as e: st.error(f"CSV could not be read: {e}")
    st.subheader("Download current dataset")
    st.download_button("Download all visible records",df.to_csv(index=False).encode("utf-8"),"atm_incidents_export.csv","text/csv")

elif page=="Audit Log":
    hero("Audit Log","Administrative activity history.")
    with get_conn() as conn:
        logs=pd.read_sql_query("SELECT username,action,detail,created_at FROM audit_log ORDER BY id DESC LIMIT 1000",conn)
    st.dataframe(logs,use_container_width=True,hide_index=True)
