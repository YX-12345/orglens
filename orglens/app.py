import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from collections import defaultdict

st.set_page_config(page_title="OrgLens", page_icon="◈", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
.block-container {padding-top: 1.6rem; max-width: 1450px;}
[data-testid="stMetric"] {background:#ffffff;border:1px solid #e5e7eb;border-radius:10px;padding:14px 16px;box-shadow:0 1px 2px rgba(0,0,0,.03)}
[data-testid="stSidebar"] {background:#f7f8fa;}
.smallnote {color:#667085;font-size:.82rem;}
.eyebrow {letter-spacing:.08em;text-transform:uppercase;color:#667085;font-size:.72rem;font-weight:700;}
.finding {border-left:4px solid #475467;background:#f8fafc;padding:12px 16px;border-radius:5px;margin:8px 0 14px 0;}
.flag {background:#fff7ed;border:1px solid #fed7aa;padding:10px 12px;border-radius:8px;}
</style>
""", unsafe_allow_html=True)

GRADES = ["GD","GE","GF","GG","GH"]
GRADE_COST = {"GD":68000,"GE":91000,"GF":122000,"GG":158000,"GH":205000}
UNITS = {
    "Investment Solutions": ["Financial Institutions", "Infrastructure", "Manufacturing"],
    "Advisory & Upstream": ["Advisory Services", "Market Creation", "Country Solutions"],
    "Corporate Services": ["Finance & Budget", "Digital Operations", "Strategy & Risk"],
}
LOCATIONS = ["Washington DC","Nairobi","Singapore","São Paulo","Istanbul","Johannesburg"]
SKILLS = ["Data & AI","Financial Analysis","Project Management","Client Engagement","Sector Expertise","Strategy"]

@st.cache_data
def build_data(seed=24):
    rng=np.random.default_rng(seed)
    rows=[]; emp=1
    # executives / directors
    ceo="E0001"; rows.append([ceo,"Avery Morgan",None,"Executive","Office of CEO","Leadership","GH","Washington DC","Leadership","Strategy",1.0,240000,14])
    emp=2
    directors={}
    for ui,(unit,depts) in enumerate(UNITS.items()):
        eid=f"E{emp:04d}"; emp+=1; directors[unit]=eid
        rows.append([eid,f"Director {ui+1}",ceo,unit,"Leadership","Leadership","GH","Washington DC","Leadership","Strategy",1.0,215000,10-ui])
        for di,dept in enumerate(depts):
            mid=f"E{emp:04d}"; emp+=1
            loc=LOCATIONS[(ui+di)%len(LOCATIONS)]
            mgr_grade="GG" if dept not in ["Advisory Services","Digital Operations"] else "GH"
            rows.append([mid,f"Manager {ui+1}-{di+1}",eid,unit,dept,"Management",mgr_grade,loc,"Management","Strategy",1.0,GRADE_COST[mgr_grade]*1.08,7])
            # deliberately varied team sizes to create realistic span flags
            base={"Advisory Services":17,"Digital Operations":15,"Finance & Budget":4,"Country Solutions":6}.get(dept,9)
            n=base + int(rng.integers(-2,3))
            for j in range(n):
                sid=f"E{emp:04d}"; emp+=1
                if dept=="Advisory Services": probs=[.03,.50,.30,.14,.03]
                elif dept=="Digital Operations": probs=[.02,.24,.37,.29,.08]
                elif dept=="Finance & Budget": probs=[.02,.18,.35,.35,.10]
                else: probs=[.04,.31,.37,.23,.05]
                grade=rng.choice(GRADES,p=probs)
                skill=rng.choice(SKILLS,p=[.13,.20,.18,.18,.20,.11])
                job_family=rng.choice(["Operations","Analytics","Finance","Program Delivery"],p=[.38,.20,.20,.22])
                loc2=rng.choice(LOCATIONS,p=[.35,.14,.13,.12,.13,.13])
                fte=float(rng.choice([1.0,1.0,1.0,.8]))
                cost=GRADE_COST[grade]*fte*float(rng.uniform(.92,1.10))
                tenure=round(float(rng.uniform(.3,11)),1)
                rows.append([sid,f"Employee {emp-1}",mid,unit,dept,"Staff",grade,loc2,job_family,skill,fte,cost,tenure])
    cols=["employee_id","name","manager_id","business_unit","department","role_type","grade","location","job_family","primary_skill","fte","annual_cost","tenure_years"]
    df=pd.DataFrame(rows,columns=cols)
    # Inject integrity issues in copies of non-leadership rows
    staff_idx=df.index[df.role_type.eq("Staff")]
    df.loc[staff_idx[3],"manager_id"]="E9999"
    df.loc[staff_idx[9],"primary_skill"]=None
    df.loc[staff_idx[15],"department"]="Unmapped Unit"
    # unit-level business metrics
    unit_metrics=[]
    for dept in [d for ds in UNITS.values() for d in ds]:
        head=(df.department==dept).sum()
        # modeled workload designed to create different alignment patterns
        factor={"Advisory Services":.70,"Digital Operations":1.20,"Finance & Budget":1.05}.get(dept,float(rng.uniform(.85,1.15)))
        workload=round(head*factor*100,0)
        prior=round(workload/float(rng.uniform(.94,1.14)),0)
        budget=float(df.loc[df.department==dept,"annual_cost"].sum()*rng.uniform(1.03,1.12))
        unit_metrics.append([dept,workload,prior,budget])
    metrics=pd.DataFrame(unit_metrics,columns=["department","workload_index","prior_workload_index","budget"])
    return df,metrics

def add_spans(df):
    counts=df.groupby("manager_id").size().rename("direct_reports")
    out=df.merge(counts,left_on="employee_id",right_index=True,how="left")
    out["direct_reports"]=out["direct_reports"].fillna(0).astype(int)
    return out

def calc_layers(df):
    mgr=dict(zip(df.employee_id,df.manager_id))
    def depth(e):
        seen=set(); d=1; cur=e
        while pd.notna(mgr.get(cur)) and mgr.get(cur) not in seen and mgr.get(cur) in mgr:
            seen.add(cur); cur=mgr[cur]; d+=1
            if d>15: break
        return d
    return pd.Series({e:depth(e) for e in df.employee_id})

def diagnostics(df, metrics):
    x=add_spans(df); manager=x[x.direct_reports>0].copy()
    valid=manager[manager.role_type.ne("Executive")]
    peer=valid.direct_reports.median() if len(valid) else 0
    findings=[]
    for _,r in valid.iterrows():
        if r.direct_reports>=12:
            findings.append({"Area":"Span of control","Unit":r.department,"Signal":f"{r.direct_reports} direct reports","Severity":"Review","Suggested diagnostic":"Review managerial capacity, delegation and reporting-line distribution."})
        elif r.direct_reports<=3:
            findings.append({"Area":"Span of control","Unit":r.department,"Signal":f"{r.direct_reports} direct reports","Severity":"Review","Suggested diagnostic":"Assess whether managerial layers or adjacent teams can be consolidated."})
    # grade mix peer comparison
    staff=df[df.role_type.eq("Staff")]
    for dept,g in staff.groupby("department"):
        if dept=="Unmapped Unit": continue
        senior=g.grade.isin(["GG","GH"]).mean()
        org=staff.grade.isin(["GG","GH"]).mean()
        if senior>org+.12:
            findings.append({"Area":"Grade mix","Unit":dept,"Signal":f"{senior:.0%} senior-grade share vs {org:.0%} organization","Severity":"Review","Suggested diagnostic":"Validate whether seniority mix reflects role complexity, leverage model and business requirements."})
    return pd.DataFrame(findings), peer

def integrity(df):
    ids=set(df.employee_id)
    orphan_mgr=df.manager_id.notna() & ~df.manager_id.isin(ids)
    missing_skill=df.primary_skill.isna()
    unmapped=df.department.eq("Unmapped Unit")
    duplicate=df.employee_id.duplicated()
    return pd.DataFrame([
        ["Orphan manager references",int(orphan_mgr.sum()),"Reporting line points to a manager not present in the dataset"],
        ["Missing skill classification",int(missing_skill.sum()),"Primary skill is not populated"],
        ["Unmapped organizational unit",int(unmapped.sum()),"Department is outside the approved hierarchy"],
        ["Duplicate employee IDs",int(duplicate.sum()),"Employee identifier appears more than once"],
    ],columns=["Check","Records","Why it matters"])

def management_brief(df, metrics, flags):
    staff=df[df.role_type.eq("Staff")]
    spans=add_spans(df); managers=spans[(spans.direct_reports>0)&(spans.role_type.ne("Executive"))]
    high=managers.sort_values("direct_reports",ascending=False).iloc[0]
    dept_cost=df.groupby("department").annual_cost.sum()
    merged=metrics.set_index("department").join(dept_cost.rename("cost"),how="left")
    # cost per modeled workload proxy
    merged["cost_per_workload"]=merged.cost/merged.workload_index
    align=merged.sort_values("cost_per_workload",ascending=False).iloc[0]
    senior=staff.assign(senior=staff.grade.isin(["GG","GH"])).groupby("department").senior.mean().sort_values(ascending=False)
    sd=senior.index[0]
    return [
        ("Management capacity", f"{high['department']} has {int(high['direct_reports'])} direct reports for its broadest manager span. This is a potential structural anomaly rather than an automatic design failure.", "Compare work complexity, geographic dispersion and delegation model with peer teams before changing reporting lines."),
        ("Workforce composition", f"{sd} has the highest senior-grade concentration at {senior.iloc[0]:.0%} of staff. The pattern may be appropriate, but it warrants comparison with role complexity and expected leverage.", "Validate job architecture and grade requirements against comparable functions."),
        ("Business alignment", f"{align.name} shows the highest modeled workforce-cost-to-workload ratio in the demonstration dataset.", "Treat workload as a diagnostic proxy; validate demand, service model and capacity assumptions with the business before drawing efficiency conclusions."),
    ]

df, metrics=build_data()
df["layer"]=df.employee_id.map(calc_layers(df))
flags, peer_span=diagnostics(df,metrics)
checks=integrity(df)

st.sidebar.markdown("### ◈ OrgLens")
st.sidebar.caption("Organizational Effectiveness & Workforce Intelligence")
page=st.sidebar.radio("Navigate",["Executive Overview","Org Effectiveness","Workforce & Business","Skills & Architecture","Management Brief","Methodology"])
st.sidebar.divider()
st.sidebar.markdown("<div class='smallnote'><b>Independent prototype</b><br>Synthetic demonstration data only.<br><br>Designed to support—not replace—human organizational judgment.</div>",unsafe_allow_html=True)

st.markdown("<div class='eyebrow'>ORGANIZATIONAL EFFECTIVENESS • WORKFORCE PLANNING • PEOPLE ANALYTICS</div>",unsafe_allow_html=True)
st.title("OrgLens")
st.caption("AI-enabled decision support for organizational diagnostics and workforce planning · Synthetic demonstration")

if page=="Executive Overview":
    spans=add_spans(df); managers=spans[(spans.direct_reports>0)&(~spans.role_type.eq("Executive"))]
    c1,c2,c3,c4,c5=st.columns(5)
    c1.metric("Workforce",f"{df.fte.sum():,.0f} FTE")
    c2.metric("People managers",len(managers))
    c3.metric("Avg. span",f"{managers.direct_reports.mean():.1f}",help="Average direct reports among people managers")
    c4.metric("Org layers",int(df.layer.max()))
    c5.metric("Workforce cost",f"${df.annual_cost.sum()/1e6:.1f}M")
    st.subheader("Organizational health signals")
    a,b=st.columns([1.25,1])
    with a:
        by_area=flags.groupby("Area").size().reset_index(name="Potential flags")
        fig=px.bar(by_area,x="Area",y="Potential flags",text="Potential flags",title=None)
        fig.update_layout(height=310,margin=dict(l=10,r=10,t=10,b=10),yaxis_title="Potential flags",xaxis_title="")
        st.plotly_chart(fig,use_container_width=True)
    with b:
        st.markdown("#### Data integrity")
        for _,r in checks.iterrows():
            status="✓" if r.Records==0 else "⚠"
            st.write(f"{status} **{r.Check}** — {r.Records}")
        st.caption("Integrity checks run before interpretation so structural findings are not built on obviously invalid records.")
    st.subheader("Workforce footprint")
    loc=df.groupby("location").fte.sum().sort_values(ascending=False).reset_index()
    fig=px.bar(loc,x="location",y="fte",labels={"location":"Location","fte":"FTE"})
    fig.update_layout(height=300,margin=dict(l=10,r=10,t=10,b=10))
    st.plotly_chart(fig,use_container_width=True)

elif page=="Org Effectiveness":
    st.header("Organizational effectiveness diagnostics")
    st.write("Surface structural patterns for **human review** using peer-relative signals rather than treating a single threshold as a universal design rule.")
    spans=add_spans(df); managers=spans[(spans.direct_reports>0)&(~spans.role_type.eq("Executive"))].copy()
    c1,c2,c3=st.columns(3)
    c1.metric("Peer median span",f"{peer_span:.1f}")
    c2.metric("Managers ≥12 reports",int((managers.direct_reports>=12).sum()))
    c3.metric("Managers ≤3 reports",int((managers.direct_reports<=3).sum()))
    left,right=st.columns([1.1,1])
    with left:
        fig=px.histogram(managers,x="direct_reports",nbins=12,labels={"direct_reports":"Direct reports"},title="Span-of-control distribution")
        fig.update_layout(height=360,margin=dict(l=10,r=10,t=45,b=10),yaxis_title="Managers")
        st.plotly_chart(fig,use_container_width=True)
    with right:
        dept=st.selectbox("Inspect a department",sorted([x for x in df.department.dropna().unique() if x!="Unmapped Unit"]))
        sub=managers[managers.department.eq(dept)][["name","grade","location","direct_reports"]].sort_values("direct_reports",ascending=False)
        st.dataframe(sub,use_container_width=True,hide_index=True)
        st.caption("Context matters: work complexity, geography, grade mix and delegation should be reviewed before recommending redesign.")
    st.subheader("Potential structural flags")
    st.dataframe(flags,use_container_width=True,hide_index=True,column_config={"Suggested diagnostic":st.column_config.TextColumn(width="large")})

elif page=="Workforce & Business":
    st.header("Workforce composition & business alignment")
    unit=st.selectbox("Business unit",["All"]+list(UNITS.keys()))
    f=df if unit=="All" else df[df.business_unit.eq(unit)]
    a,b=st.columns(2)
    with a:
        grade=f[f.role_type.eq("Staff")].groupby("grade").fte.sum().reindex(GRADES).fillna(0).reset_index()
        fig=px.bar(grade,x="grade",y="fte",title="Grade mix",labels={"grade":"Grade","fte":"FTE"})
        fig.update_layout(height=350,margin=dict(l=10,r=10,t=45,b=10))
        st.plotly_chart(fig,use_container_width=True)
    with b:
        comp=f.groupby("job_family").fte.sum().reset_index()
        fig=px.bar(comp,x="job_family",y="fte",title="Job-family composition",labels={"job_family":"Job family","fte":"FTE"})
        fig.update_layout(height=350,margin=dict(l=10,r=10,t=45,b=10))
        st.plotly_chart(fig,use_container_width=True)
    st.subheader("Capacity, cost and modeled workload")
    cost=df.groupby("department").agg(FTE=("fte","sum"),Workforce_Cost=("annual_cost","sum")).join(metrics.set_index("department"),how="inner").reset_index()
    cost["Cost / workload"]=(cost.Workforce_Cost/cost.workload_index).round(0)
    cost["Workload change"]=(cost.workload_index/cost.prior_workload_index-1)
    st.dataframe(cost[["department","FTE","Workforce_Cost","budget","workload_index","Workload change","Cost / workload"]],use_container_width=True,hide_index=True,
                 column_config={"Workforce_Cost":st.column_config.NumberColumn(format="$%.0f"),"budget":st.column_config.NumberColumn("Budget",format="$%.0f"),"Workload change":st.column_config.NumberColumn(format="%.1%%"),"Cost / workload":st.column_config.NumberColumn(format="$%.0f")})
    st.info("Modeled workload is a synthetic diagnostic proxy—not a productivity score. A real assessment would validate demand, service model, role complexity and business context with stakeholders.")

elif page=="Skills & Architecture":
    st.header("Skills & job architecture")
    staff=df[df.role_type.eq("Staff")].copy()
    a,b=st.columns([1,1])
    with a:
        skills=staff.groupby("primary_skill").fte.sum().sort_values().reset_index()
        fig=px.bar(skills,x="fte",y="primary_skill",orientation="h",title="Current skill distribution",labels={"fte":"FTE","primary_skill":"Primary skill"})
        fig.update_layout(height=390,margin=dict(l=10,r=10,t=45,b=10))
        st.plotly_chart(fig,use_container_width=True)
    with b:
        st.markdown("#### Illustrative architecture")
        arch=pd.DataFrame([
            ["Operations","Analyst","GE","Data analysis; program delivery"],
            ["Operations","Specialist","GF","Project management; client engagement"],
            ["Operations","Senior Specialist","GG","Sector expertise; strategy; leadership"],
            ["Analytics","Analyst","GE","Data analysis; visualization"],
            ["Analytics","Specialist","GF","Advanced analytics; stakeholder advisory"],
        ],columns=["Job family","Role","Illustrative grade","Core capabilities"])
        st.dataframe(arch,use_container_width=True,hide_index=True)
        st.caption("Illustrative architecture only; it is not IFC's job architecture.")
    pivot=pd.crosstab(staff.department,staff.primary_skill,values=staff.fte,aggfunc="sum").fillna(0)
    st.subheader("Skills coverage by department")
    st.dataframe(pivot,use_container_width=True)

elif page=="Management Brief":
    st.header("Management brief")
    st.write("A controlled narrative layer converts **validated aggregate metrics** into decision-ready observations. The analytical engine—not the language model—owns the calculations.")
    if st.button("Generate executive assessment",type="primary",use_container_width=False):
        for title,obs,rec in management_brief(df,metrics,flags):
            st.markdown(f"<div class='finding'><b>{title}</b><br><br><b>Observation</b><br>{obs}<br><br><b>Recommended diagnostic</b><br>{rec}</div>",unsafe_allow_html=True)
        st.markdown("#### Responsible-AI guardrail")
        st.info("OrgLens supports interpretation of aggregate organizational metrics. It does not evaluate individual performance, recommend employment actions, or make autonomous organizational decisions. Findings require human validation and business context.")
    else:
        st.caption("Generate the brief to see how analytical signals are translated into a management narrative.")

else:
    st.header("Methodology & responsible use")
    st.markdown("""
**Purpose.** OrgLens is an independent portfolio prototype demonstrating an organizational-effectiveness workflow: data validation → workforce metrics → structural diagnostics → business-context interpretation → management narrative.

**Synthetic data.** All people, organizational units, reporting lines, costs, workloads and skills in this application are fictional. No World Bank Group or IFC employee data are used.

**Diagnostic—not prescriptive.** Spans, grade mix, layers and cost/workload relationships are signals for review. They are not universal measures of organizational quality and should be interpreted alongside strategy, role complexity, geography, delivery model and stakeholder context.

**AI design.** Calculations and flags are deterministic. A generative-AI layer can be added to transform validated aggregate findings into audience-specific summaries, while preserving human review and source metrics.

**Data integrity.** Organizational analytics depend on hierarchy quality. The prototype therefore checks manager references, classification gaps, unmapped units and duplicate identifiers before interpretation.
""")
    st.markdown("#### Capability demonstrated")
    st.write("Organizational diagnostics · workforce composition · grade mix · staffing ratios · business alignment · skills architecture · data quality · visualization · management storytelling · responsible AI")
