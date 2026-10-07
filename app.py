from pathlib import Path
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(page_title='OrgLens | Workforce Intelligence', page_icon='◈', layout='wide', initial_sidebar_state='expanded')
BASE=Path(__file__).parent; DATA=BASE/'data'
GRADES=['GD','GE','GF','GG','GH']

st.markdown('''<style>
.block-container{padding-top:1.35rem;max-width:1480px}[data-testid="stMetric"]{background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:14px 16px;box-shadow:0 1px 2px rgba(0,0,0,.03)}[data-testid="stSidebar"]{background:#f7f8fa}.smallnote{color:#667085;font-size:.82rem}.eyebrow{letter-spacing:.08em;text-transform:uppercase;color:#667085;font-size:.72rem;font-weight:700}.finding{border-left:4px solid #475467;background:#f8fafc;padding:13px 16px;border-radius:6px;margin:8px 0 14px}.signal{background:#fff7ed;border:1px solid #fed7aa;padding:10px 12px;border-radius:8px}.good{background:#ecfdf3;border:1px solid #abefc6;padding:10px 12px;border-radius:8px}.byline{color:#667085;font-size:.78rem;margin-top:1rem}</style>''',unsafe_allow_html=True)

@st.cache_data
def load_defaults():
    return (pd.read_csv(DATA/'workforce.csv'),pd.read_csv(DATA/'business_metrics.csv'),pd.read_csv(DATA/'skill_demand.csv'),pd.read_csv(DATA/'job_architecture.csv'))

def add_spans(df):
    c=df.groupby('manager_id').size().rename('direct_reports'); x=df.merge(c,left_on='employee_id',right_index=True,how='left'); x['direct_reports']=x.direct_reports.fillna(0).astype(int); return x

def calc_layers(df):
    mgr=dict(zip(df.employee_id,df.manager_id))
    def depth(e):
        seen=set(); d=1; cur=e
        while pd.notna(mgr.get(cur)) and mgr.get(cur) not in seen and mgr.get(cur) in mgr:
            seen.add(cur); cur=mgr[cur]; d+=1
            if d>15: break
        return d
    return pd.Series({e:depth(e) for e in df.employee_id})

def integrity(df):
    ids=set(df.employee_id)
    return pd.DataFrame([
      ['Orphan manager references',int((df.manager_id.notna() & ~df.manager_id.isin(ids)).sum()),'Reporting line points to a manager not present in the dataset'],
      ['Missing skill classification',int(df.primary_skill.isna().sum()),'Primary skill is not populated'],
      ['Unmapped organizational unit',int(df.department.eq('Unmapped Unit').sum()),'Department is outside the approved hierarchy'],
      ['Duplicate employee identifiers',int(df.employee_id.duplicated().sum()),'Employee identifier appears more than once']],columns=['Check','Records','Why it matters'])

def diagnostics(df):
    x=add_spans(df); managers=x[(x.direct_reports>0)&(~x.role_type.eq('Executive'))]; peer=managers.direct_reports.median(); findings=[]
    for _,r in managers.iterrows():
        if r.direct_reports>=12: findings.append(['Span of control',r.department,f'{r.direct_reports} direct reports','Review','Review managerial capacity, delegation and reporting-line distribution.'])
        elif r.direct_reports<=3: findings.append(['Span of control',r.department,f'{r.direct_reports} direct reports','Review','Assess whether managerial layers or adjacent teams should be reviewed.'])
    staff=df[df.role_type.eq('Staff')]; org=staff.grade.isin(['GG','GH']).mean()
    for dept,g in staff.groupby('department'):
        if dept=='Unmapped Unit': continue
        senior=g.grade.isin(['GG','GH']).mean()
        if senior>org+.12: findings.append(['Grade mix',dept,f'{senior:.0%} senior-grade share vs {org:.0%} organization','Review','Validate whether seniority mix reflects role complexity, leverage model and business requirements.'])
    return pd.DataFrame(findings,columns=['Area','Unit','Signal','Status','Suggested diagnostic']),peer

def unit_summary(df,metrics,dept):
    d=df[df.department.eq(dept)]; s=d[d.role_type.eq('Staff')]; spans=add_spans(d); mgrs=spans[spans.direct_reports>0]; m=metrics[metrics.department.eq(dept)].iloc[0]
    return {'fte':d.fte.sum(),'managers':len(mgrs),'max_span':int(mgrs.direct_reports.max()) if len(mgrs) else 0,'senior_share':s.grade.isin(['GG','GH']).mean() if len(s) else 0,'cost':d.annual_cost.sum(),'workload':m.workload_index,'cost_per_workload':d.annual_cost.sum()/m.workload_index}

def fmt_money(x): return f'${x/1e6:.2f}M' if x>=1e6 else f'${x:,.0f}'

workforce,business,skill_demand,architecture=load_defaults()
# Optional no-code session refresh. Files are not persisted; GitHub data files remain the durable source.
st.sidebar.markdown('### ◈ OrgLens'); st.sidebar.caption('Organizational Effectiveness & Workforce Intelligence')
page=st.sidebar.radio('Navigate',['Executive Overview','Analyze a Business Unit','Organizational Effectiveness','Workforce Alignment','Skills & Job Architecture','Scenario Lab','Data & Refresh','Management Brief','Methodology & Glossary'])
st.sidebar.divider(); st.sidebar.markdown("<div class='smallnote'><b>Independent portfolio prototype</b><br>Synthetic demonstration data only.<br><br><b>Designed & developed by Phoebe Wang</b><br>2026</div>",unsafe_allow_html=True)

workforce['layer']=workforce.employee_id.map(calc_layers(workforce)); flags,peer_span=diagnostics(workforce); checks=integrity(workforce)
st.markdown("<div class='eyebrow'>ORGANIZATIONAL EFFECTIVENESS • WORKFORCE PLANNING • PEOPLE ANALYTICS</div>",unsafe_allow_html=True); st.title('OrgLens'); st.caption('Decision support for organizational diagnostics and workforce planning · Synthetic demonstration')

if page=='Executive Overview':
    spans=add_spans(workforce); managers=spans[(spans.direct_reports>0)&(~spans.role_type.eq('Executive'))]
    c1,c2,c3,c4,c5=st.columns(5); c1.metric('Workforce capacity',f'{workforce.fte.sum():,.0f} FTE',help='Full-Time Equivalent (FTE) measures workforce capacity. 1.0 FTE equals one full-time workload.'); c2.metric('People managers',len(managers)); c3.metric('Average span of control',f'{managers.direct_reports.mean():.1f}',delta=f'{managers.direct_reports.mean()-peer_span:+.1f} vs median',help='Span of control is the number of direct reports assigned to a manager.'); c4.metric('Organizational layers',int(workforce.layer.max()),help='Number of reporting levels in the modeled hierarchy.'); c5.metric('Modeled workforce cost (USD)',fmt_money(workforce.annual_cost.sum()))
    st.subheader('What requires attention?'); a,b=st.columns([1.35,1])
    with a:
        by=flags.groupby('Area').size().reset_index(name='Potential signals'); fig=px.bar(by,x='Area',y='Potential signals',text='Potential signals'); fig.update_layout(height=300,margin=dict(l=10,r=10,t=10,b=10),xaxis_title='',yaxis_title='Signals for review'); st.plotly_chart(fig,use_container_width=True)
    with b:
        st.markdown('#### Data integrity before interpretation')
        for _,r in checks.iterrows(): st.write(f"{'✓' if r.Records==0 else '⚠'} **{r.Check}** — {r.Records}")
        st.caption('Structural findings should not be interpreted until obvious hierarchy and classification issues are understood.')
    st.subheader('Where is workforce capacity located?'); loc=workforce.groupby('location').fte.sum().sort_values(ascending=False).reset_index(); fig=px.bar(loc,x='location',y='fte',labels={'location':'Location','fte':'Full-Time Equivalents (FTE)'}); fig.update_layout(height=300,margin=dict(l=10,r=10,t=10,b=10)); st.plotly_chart(fig,use_container_width=True)

elif page=='Analyze a Business Unit':
    st.header('Analyze a business unit'); st.write('Move from an organization-wide signal to a **business-context diagnostic**. Metrics identify questions for review; they do not determine organizational quality.')
    depts=sorted([x for x in business.department.unique() if x!='Unmapped Unit']); dept=st.selectbox('Select business unit / department',depts,index=depts.index('Advisory Services') if 'Advisory Services' in depts else 0); u=unit_summary(workforce,business,dept); org_cpw=workforce[workforce.department.isin(business.department)].annual_cost.sum()/business.workload_index.sum()
    c1,c2,c3,c4,c5=st.columns(5); c1.metric('Workforce capacity',f"{u['fte']:.1f} FTE",help='Full-Time Equivalent: one full-time workload equals 1.0 FTE.'); c2.metric('People managers',u['managers']); c3.metric('Broadest span of control',u['max_span'],delta=f"{u['max_span']-peer_span:+.0f} vs peer median"); c4.metric('Senior-grade share',f"{u['senior_share']:.0%}"); c5.metric('Modeled workforce cost (USD)',fmt_money(u['cost']))
    st.subheader('Key diagnostic signals'); x,y,z=st.columns(3)
    x.markdown(f"<div class='signal'><b>Management capacity</b><br><br>Broadest span: <b>{u['max_span']}</b><br>Peer median: <b>{peer_span:.0f}</b><br><br>Review work complexity, geography and delegation before redesign.</div>",unsafe_allow_html=True)
    org_senior=workforce[workforce.role_type.eq('Staff')].grade.isin(['GG','GH']).mean(); y.markdown(f"<div class='signal'><b>Seniority mix</b><br><br>Selected unit: <b>{u['senior_share']:.0%}</b><br>Organization: <b>{org_senior:.0%}</b><br><br>Validate grade requirements against role complexity and leverage.</div>",unsafe_allow_html=True)
    z.markdown(f"<div class='signal'><b>Business alignment</b><br><br>Cost / workload proxy (USD): <b>${u['cost_per_workload']:,.0f}</b><br>Organization: <b>${org_cpw:,.0f}</b><br><br>Validate demand and service model before drawing efficiency conclusions.</div>",unsafe_allow_html=True)
    st.subheader('Questions for the HR business partner / business'); st.markdown('1. Is the management span consistent with work complexity and employee seniority?  \n2. Does geographic dispersion increase coordination requirements?  \n3. Is the grade mix explained by specialized role requirements?  \n4. Does the modeled workload proxy adequately represent the unit’s demand and service model?')

elif page=='Organizational Effectiveness':
    st.header('Organizational effectiveness diagnostics'); st.write('**Business question:** Are reporting structures and seniority patterns materially different from comparable teams?')
    spans=add_spans(workforce); managers=spans[(spans.direct_reports>0)&(~spans.role_type.eq('Executive'))]; c1,c2,c3=st.columns(3); c1.metric('Peer median span of control',f'{peer_span:.1f}',help='Median number of direct reports among modeled people managers.'); c2.metric('Managers with 12+ reports',int((managers.direct_reports>=12).sum())); c3.metric('Managers with 3 or fewer reports',int((managers.direct_reports<=3).sum()))
    left,right=st.columns([1.1,1]);
    with left:
        span_counts=managers.groupby('direct_reports').size().reset_index(name='Managers'); fig=px.bar(span_counts,x='direct_reports',y='Managers',labels={'direct_reports':'Direct reports'},title='Span-of-control distribution'); fig.update_traces(width=0.65); fig.update_layout(height=350,margin=dict(l=10,r=10,t=45,b=10),yaxis_title='Managers',xaxis=dict(dtick=1)); st.plotly_chart(fig,use_container_width=True)
    with right:
        st.markdown('#### Why this matters'); st.write('Very broad or narrow spans can signal a need to review managerial capacity, delegation, layers or team design. There is **no universal ideal span**; context determines whether a pattern is appropriate.'); st.markdown('#### Take action'); st.write('Use the flags below to prioritize conversations, then validate work complexity, geography, seniority and delivery model with the business.')
    st.subheader('Potential structural signals'); st.dataframe(flags,use_container_width=True,hide_index=True,column_config={'Suggested diagnostic':st.column_config.TextColumn(width='large')})

elif page=='Workforce Alignment':
    st.header('Workforce alignment'); st.write('**Business question:** Are workforce capacity, composition, seniority, location, skills and affordability aligned with modeled business requirements?')
    unit=st.selectbox('Business unit',['All']+sorted(workforce.business_unit.dropna().unique())); f=workforce if unit=='All' else workforce[workforce.business_unit.eq(unit)]
    a,b=st.columns(2)
    with a:
        grade=f[f.role_type.eq('Staff')].groupby('grade').fte.sum().reindex(GRADES).fillna(0).reset_index(); fig=px.bar(grade,x='grade',y='fte',title='Seniority / grade mix',labels={'grade':'Illustrative grade','fte':'Full-Time Equivalents (FTE)'}); fig.update_layout(height=330,margin=dict(l=10,r=10,t=45,b=10)); st.plotly_chart(fig,use_container_width=True)
    with b:
        comp=f.groupby('job_family').fte.sum().reset_index(); fig=px.bar(comp,x='job_family',y='fte',title='Job-family composition',labels={'job_family':'Job family','fte':'Full-Time Equivalents (FTE)'}); fig.update_layout(height=330,margin=dict(l=10,r=10,t=45,b=10)); st.plotly_chart(fig,use_container_width=True)
    cost=workforce.groupby('department').agg(FTE=('fte','sum'),Workforce_Cost=('annual_cost','sum')).join(business.set_index('department'),how='inner').reset_index(); cost['Workload change']=cost.workload_index/cost.prior_workload_index-1; cost['Cost / workload']=cost.Workforce_Cost/cost.workload_index
    st.subheader('Capacity, affordability and modeled demand'); st.dataframe(cost[['department','FTE','Workforce_Cost','budget','workload_index','Workload change','Cost / workload']],use_container_width=True,hide_index=True,column_config={'FTE':st.column_config.NumberColumn('FTE',format='%.1f'),'Workforce_Cost':st.column_config.NumberColumn('Workforce cost (USD)',format='$%,.0f'),'budget':st.column_config.NumberColumn('Budget (USD)',format='$%,.0f'),'workload_index':st.column_config.NumberColumn('Modeled workload',format='%,.0f'),'Workload change':st.column_config.NumberColumn('Workload change',format='%.1%%'),'Cost / workload':st.column_config.NumberColumn('Cost / workload (USD)',format='$%,.0f')}); st.info('Modeled workload is a synthetic diagnostic proxy—not a productivity score. A real assessment would validate demand, service model, role complexity and business context with stakeholders.')

elif page=='Skills & Job Architecture':
    st.header('Skills & job architecture'); st.write('**Business question:** Does current skill capacity broadly match modeled future requirements, and where should an analyst investigate gaps?')
    staff=workforce[workforce.role_type.eq('Staff')]; supply=staff.groupby('primary_skill').fte.sum().rename('Current capacity').reset_index().rename(columns={'primary_skill':'Skill'}); gap=supply.merge(skill_demand.rename(columns={'skill':'Skill','modeled_requirement_fte':'Modeled requirement'}),on='Skill',how='outer').fillna(0); gap['Gap']=gap['Current capacity']-gap['Modeled requirement']; gap['Coverage']=np.where(gap['Modeled requirement']>0,gap['Current capacity']/gap['Modeled requirement'],np.nan)
    left,right=st.columns([1.2,1])
    with left:
        long=gap.melt(id_vars='Skill',value_vars=['Current capacity','Modeled requirement'],var_name='Measure',value_name='FTE'); fig=px.bar(long,x='Skill',y='FTE',color='Measure',barmode='group',title='Current skill capacity vs modeled requirement'); fig.update_layout(height=390,margin=dict(l=10,r=10,t=45,b=10)); st.plotly_chart(fig,use_container_width=True)
    with right:
        worst=gap.sort_values('Gap').iloc[0]; st.markdown(f"<div class='signal'><b>Largest modeled capability gap</b><br><br><b>{worst['Skill']}</b><br>Current: {worst['Current capacity']:.1f} FTE<br>Modeled requirement: {worst['Modeled requirement']:.1f} FTE<br>Gap: <b>{worst['Gap']:.1f} FTE</b><br><br>Investigate build, buy, borrow, redeploy or reskill options after validating demand.</div>",unsafe_allow_html=True); st.caption('Requirements are fictional and included only to demonstrate a supply-versus-demand workflow.')
    st.dataframe(gap,use_container_width=True,hide_index=True,column_config={'Current capacity':st.column_config.NumberColumn(format='%.1f'),'Modeled requirement':st.column_config.NumberColumn(format='%.1f'),'Gap':st.column_config.NumberColumn(format='%.1f'),'Coverage':st.column_config.ProgressColumn('Coverage',min_value=0,max_value=1,format='%.0f%%')})
    st.subheader('Illustrative job architecture'); st.dataframe(architecture,use_container_width=True,hide_index=True); st.caption("Illustrative only; this is not IFC's job architecture.")

elif page=='Scenario Lab':
    st.header('Scenario lab'); st.write('Explore a simple organizational-design trade-off. This is **not an optimization engine** and does not recommend a restructuring decision.')
    dept=st.selectbox('Department',sorted(business.department.unique()),index=0); u=unit_summary(workforce,business,dept); add_mgr=st.slider('Additional manager positions in scenario',0,10,1,step=1,help='Illustrative range only; this does not recommend adding management positions.'); manager_cost=st.number_input('Illustrative annual cost per added manager (USD)',min_value=80000,max_value=300000,value=175000,step=5000,help='Synthetic assumption for scenario comparison only.'); current_span=u['max_span']; scenario_span=max(1,current_span/(1+add_mgr)); scenario_cost=u['cost']+add_mgr*manager_cost
    st.subheader('Current vs proposed scenario'); sc=pd.DataFrame([['People managers',f"{u['managers']:,}",f"{u['managers']+add_mgr:,}"],['Illustrative modeled broadest span',f"{current_span:.1f}",f"~{scenario_span:.1f}"],['Workforce cost (USD)',fmt_money(u['cost']),fmt_money(scenario_cost)],['Incremental cost (USD)','—',fmt_money(scenario_cost-u['cost'])]],columns=['Measure','Current','Scenario']); st.dataframe(sc,use_container_width=True,hide_index=True); st.caption('Illustrative scenario assumes reporting load can be redistributed across management positions. Actual spans depend on role design, reporting relationships, geography and managerial responsibilities.')
    st.markdown(f"<div class='finding'><b>Trade-off to validate</b><br><br>Adding {add_mgr} manager position(s) could reduce the modeled broadest span from <b>{current_span}</b> toward approximately <b>{scenario_span:.1f}</b>, while increasing modeled annual workforce cost by <b>{fmt_money(scenario_cost-u['cost'])}</b>. Before redesign, validate managerial workload, role complexity, geography, delegation and whether an additional management position creates unnecessary layering.</div>",unsafe_allow_html=True)

elif page=='Data & Refresh':
    st.header('Data & refresh'); st.write('OrgLens separates **data from code** so the analytical workflow can be refreshed without rewriting calculations.')
    c1,c2,c3,c4=st.columns(4); c1.metric('Workforce records',len(workforce)); c2.metric('Source tables',4); c3.metric('Validation issues',int(checks.Records.sum())); c4.metric('Refresh mode','CSV → model')
    st.subheader('Source-to-insight pipeline'); st.code('Workforce roster + Organizational hierarchy\n        + Skills demand + Job architecture\n        + Business / financial metrics\n                    ↓\n          Validation & transformation\n                    ↓\n       Organizational analytical model\n                    ↓\n Diagnostics → scenarios → management brief',language=None)
    st.subheader('Source files'); src=pd.DataFrame([['workforce.csv','Workforce roster, hierarchy, grade, location, skills, FTE and cost'],['business_metrics.csv','Modeled workload and budget by organizational unit'],['skill_demand.csv','Modeled future skill requirements'],['job_architecture.csv','Illustrative job family / role / grade framework']],columns=['File','Purpose']); st.dataframe(src,use_container_width=True,hide_index=True)
    st.subheader('How Phoebe can update the demo without coding'); st.write('Edit the CSV files in Excel or another spreadsheet tool, then replace the corresponding file in the GitHub **data** folder. Streamlit will reload the repository and recalculate the app. Keep the same column names so the analytical model continues to work.')
    st.warning('For this portfolio demo, the durable source is GitHub. In a production environment, these inputs would normally come from governed HR, finance and planning systems rather than manual CSV replacement.')
    st.subheader('Current validation results'); st.dataframe(checks,use_container_width=True,hide_index=True)

elif page=='Management Brief':
    st.header('Management brief'); st.write('Convert validated organizational metrics into audience-specific, decision-ready briefs. **Analytical calculations remain deterministic and traceable; generative AI could be integrated as a controlled drafting layer in a production environment.**')
    dept=st.selectbox('Business unit / department',sorted(business.department.unique()),index=0); audience=st.segmented_control('Audience',['HR Business Partner','Executive'],default='HR Business Partner'); u=unit_summary(workforce,business,dept); org_senior=workforce[workforce.role_type.eq('Staff')].grade.isin(['GG','GH']).mean()
    if st.button('Generate assessment',type='primary'):
        if audience=='Executive':
            st.markdown(f"<div class='finding'><b>{dept} — executive summary</b><br><br>The unit has {u['fte']:.1f} Full-Time Equivalents and modeled annual workforce cost of {fmt_money(u['cost'])} USD. Its broadest management span is {u['max_span']} direct reports versus a peer median of {peer_span:.0f}; senior-grade share is {u['senior_share']:.0%} versus {org_senior:.0%} organization-wide. These are diagnostic signals, not conclusions. Validate work complexity, demand, geography and role requirements before considering structural changes.</div>",unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='finding'><b>{dept} — HRBP diagnostic brief</b><br><br><b>Observation</b><br>Broadest span of control is {u['max_span']} versus peer median {peer_span:.0f}. Senior-grade share is {u['senior_share']:.0%}. Modeled cost-to-workload proxy is ${u['cost_per_workload']:,.0f} USD.<br><br><b>Recommended diagnostic</b><br>Review reporting-line distribution, manager capacity, role complexity, geographic dispersion and whether modeled demand captures the unit’s service model.<br><br><b>Data limitation</b><br>Workload and skill requirements are synthetic proxies. Findings require business validation and should not be used for individual employment decisions.</div>",unsafe_allow_html=True)
        st.info('Responsible-use guardrail: OrgLens supports interpretation of aggregate organizational metrics. It does not evaluate individual performance, recommend employment actions, or make autonomous organizational decisions.')
    st.caption('A future production version could pass only validated aggregate findings—not raw employee records—to an approved language model for controlled drafting.')

else:
    st.header('Methodology & glossary'); st.markdown('''**Purpose.** OrgLens is an independent portfolio prototype demonstrating an end-to-end organizational-effectiveness workflow: source data → validation → workforce metrics → structural diagnostics → business-context interpretation → scenario analysis → management narrative.

**Synthetic data.** All people, organizational units, reporting lines, costs, workloads and skills are fictional. No World Bank Group or IFC employee data are used. Deliberate structural and data-quality patterns are embedded so the analytical workflow can detect them.

**Diagnostic—not prescriptive.** Spans, grade mix, layers and cost/workload relationships are signals for review. They are not universal measures of organizational quality and should be interpreted alongside strategy, role complexity, geography, delivery model and stakeholder context.

**AI-ready design.** The prototype keeps calculations deterministic and explainable. A production implementation could use an approved generative-AI layer to draft audience-specific summaries from validated aggregate findings while preserving human review.

**Span of influence.** The prototype models formal reporting relationships (span of control), not informal influence networks. Measuring influence would require appropriate collaboration/network data and privacy safeguards.''')
    st.subheader('Glossary'); glossary=pd.DataFrame([
      ['Full-Time Equivalent (FTE)','A workforce-capacity measure. One full-time workload equals 1.0 FTE; a 50% workload equals 0.5 FTE.'],['Span of control','Number of employees who report directly to a manager.'],['Organizational layer','A reporting level in the organizational hierarchy.'],['Grade mix','Distribution of workforce across modeled seniority / grade levels.'],['Job architecture','Framework connecting job families, roles, grades and capabilities.'],['Workforce planning','Process of aligning workforce capacity and composition with business requirements.'],['Modeled workload','Synthetic proxy for business demand used here to demonstrate alignment analysis.'],['Cost / workload','Diagnostic ratio comparing modeled workforce cost with modeled workload; not a productivity score.'],['Skill supply / demand','Comparison of current skill capacity with a modeled future requirement.'],['HR Business Partner (HRBP)','HR professional who works with business leaders on workforce and organizational priorities.'],['Currency','All monetary values in this synthetic demonstration are modeled in U.S. dollars (USD).']],columns=['Term','Plain-English meaning']); st.dataframe(glossary,use_container_width=True,hide_index=True)
    st.markdown("<div class='byline'>OrgLens · Independent portfolio prototype · Designed & developed by <b>Phoebe Wang</b> · 2026</div>",unsafe_allow_html=True)
