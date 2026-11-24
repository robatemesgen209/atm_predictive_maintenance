import re
import numpy as np
import pandas as pd
from datetime import datetime

COMPONENTS = ["Card Reader","High Dispenser","Cassette 1","Cassette 2","Cassette 3","Cassette 4",
              "Screen","Power Supply","EPP / PIN Pad","Software","Camera","Shutter","Electronic Journal",
              "Network / Communication","Other / Unclassified"]

def normalize_component(problem):
    s = str(problem).lower().strip()
    # Preserve cassette numbering when present.
    if "card" in s and ("read" in s or "reader" in s): return "Card Reader"
    if "dispenser" in s or "dispens" in s:
        return "High Dispenser"
    if "1st" in s or "1st cassette" in s: return "Cassette 1"
    if "2nd" in s or "2nd cassette" in s: return "Cassette 2"
    if "3rd" in s or "3rd cassette" in s: return "Cassette 3"
    if "4th" in s or "4th cassette" in s: return "Cassette 4"
    if "cassette" in s:
        m = re.search(r'([1-4])', s)
        return f"Cassette {m.group(1)}" if m else "High Dispenser"
    if "power" in s: return "Power Supply"
    if "screen" in s or "monitor" in s or "display" in s: return "Screen"
    if "epp" in s or "pin" in s or "keypad" in s: return "EPP / PIN Pad"
    if "software" in s or "windows" in s or "application" in s: return "Software"
    if "camera" in s: return "Camera"
    if "shutter" in s: return "Shutter"
    if s in ("ej","electronic journal") or "journal" in s: return "Electronic Journal"
    if "network" in s or "communication" in s or "line" in s: return "Network / Communication"
    return "Other / Unclassified"

def _parse_dates(series):
    return pd.to_datetime(series, errors="coerce", dayfirst=False)

def forecast_for_terminal(df, terminal_id, district=None, top_n=5):
    if df.empty:
        return pd.DataFrame(), {"level":"No data","incidents":0,"unique_components":0,"repeat_rate":0.0}
    d = df.copy()
    d["component"] = d["component"].fillna(d["problem"].map(normalize_component))
    d["parsed_date"] = _parse_dates(d.get("record_date", pd.Series(index=d.index,dtype=str)))
    machine = d[d.terminal_id.astype(str).str.upper() == str(terminal_id).upper()].copy()
    if district:
        machine = machine[machine.district.astype(str).str.upper() == str(district).upper()]
    if machine.empty:
        return pd.DataFrame(), {"level":"Insufficient history","incidents":0,"unique_components":0,"repeat_rate":0.0}
    # Recency weighting: recent events contribute more, but all history remains relevant.
    latest = machine.parsed_date.max()
    if pd.isna(latest): latest = pd.Timestamp.today()
    machine["age_days"] = (latest - machine.parsed_date).dt.days.fillna(180).clip(lower=0)
    machine["weight"] = np.exp(-machine.age_days / 240.0)
    machine_scores = machine.groupby("component").weight.sum()
    district_rows = d[d.district.astype(str).str.upper() == str(machine.iloc[0].district).upper()]
    district_prior = district_rows.groupby("component").size()
    # Smoothed empirical Bayes: machine evidence is dominant; district evidence stabilizes sparse histories.
    all_components = sorted(set(machine_scores.index) | set(district_prior.index))
    total_prior = max(int(district_prior.sum()),1)
    rows=[]
    for comp in all_components:
        own = float(machine_scores.get(comp,0))
        prior = float(district_prior.get(comp,0))/total_prior
        score = own + 1.5*prior
        rows.append({"Component":comp,"Weighted machine history":round(own,2),
                     "District baseline":round(prior*100,1),"Risk score":score})
    result=pd.DataFrame(rows).sort_values("Risk score",ascending=False).head(top_n)
    if result.empty: return result, {"level":"Insufficient history","incidents":len(machine),"unique_components":0,"repeat_rate":0.0}
    result["Relative likelihood (%)"]=(result["Risk score"]/result["Risk score"].sum()*100).round(1)
    counts=machine.component.value_counts()
    repeat_rate=float((counts[counts>1].sum()/max(len(machine),1))*100)
    level="High" if len(machine)>=10 and repeat_rate>=60 else ("Moderate" if len(machine)>=4 else "Early signal")
    meta={"level":level,"incidents":len(machine),"unique_components":int(machine.component.nunique()),
          "repeat_rate":round(repeat_rate,1),"district":str(machine.iloc[0].district),
          "last_reported":str(machine.parsed_date.max().date()) if machine.parsed_date.notna().any() else "Unknown"}
    return result,meta

def district_risk_table(df):
    if df.empty: return pd.DataFrame()
    g=df.groupby(["district","terminal_id","terminal_name"],dropna=False).agg(
        Incidents=("id","count"), Components=("component","nunique"),
        Last_report=("record_date","max")).reset_index()
    g["Repeat burden"]=g["Incidents"].apply(lambda n:"High" if n>=15 else ("Medium" if n>=7 else "Low"))
    return g.sort_values(["Incidents","Last_report"],ascending=[False,False])
