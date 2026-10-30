#!/usr/bin/env python3
"""Recreate manuscript tables using the bundled evidence extracts."""
from pathlib import Path
import pandas as pd

P=Path(__file__).resolve().parents[1]
T=P/'tables'; T.mkdir(exist_ok=True)
e1=pd.read_csv(P/'data/e1_summary.csv').set_index('method')
e2=pd.read_csv(P/'data/e2_summary_corrected.csv').set_index('condition')
replay=pd.read_csv(P/'data/e1_replay_summary.csv').set_index('method')


def pm(row,key,digits=2):
    return f'${row[key+"_mean"]:.{digits}f} \\pm {row[key+"_sd"]:.{digits}f}$'


def table(name,columns,header,rows):
    text='\\begin{tabular}{'+columns+'}\n\\toprule\n'+header+' \\\\\n\\midrule\n'
    text+=''.join(' & '.join(str(x) for x in row)+' \\\\\n' for row in rows)
    text+='\\bottomrule\n\\end{tabular}\n'
    (T/name).write_text(text)

table('e1_primary.tex','lcrr',r'Method & Completed/started & Time (s) & $J_{\mathrm{excess}}$ (N\,s)',
      [[m,f'{int(e1.loc[m,"completed"])}/5',pm(e1.loc[m],'completion_time_s'),pm(e1.loc[m],'J_excess_Ns',3)]
       for m in ['R','T','C']])
table('e1_replay.tex','lcr',r'Method & Replay completed & Replay time (s)',
      [[m,'5/5',pm(replay.loc[m],'B_completion_time_s')] for m in ['R','T','C']])
table('e2_times.tex','lcrr',r'Condition & Completed/attempted & Completed time (s) & All-attempt interval (s)',
      [[m,f'{int(e2.loc[m,"completed"])}/5',pm(e2.loc[m],'completion_time_corrected_s'),pm(e2.loc[m],'execution_duration_s')]
       for m in ['A','B','C']])
table('e2_force_travel.tex','lrrr',r'Condition & Mean $F_z^B$ (N) & Peak $F_z^B$ (N) & XY travel (mm)',
      [[m,pm(e2.loc[m],'mean_fz_N'),pm(e2.loc[m],'peak_fz_N'),pm(e2.loc[m],'tcp_xy_path_mm')]
       for m in ['A','B','C']])

a=pd.read_csv(P/'data/e1_runs.csv'); b=pd.read_csv(P/'data/e2_runs_corrected.csv')
table('e1_all.tex','llrr',r'Run & Procedural outcome & Time (s) & $J_{\mathrm{excess}}$ (N\,s)',
      [[r.label,r.outcome, '\\NA' if pd.isna(r.completion_time_s) else f'{r.completion_time_s:.3f}',f'{r.J_excess_Ns:.4f}']
       for _,r in a.iterrows()])
table('e2_all.tex','llrr',r'Run & Task outcome & Completion (s) & Interval to stop (s)',
      [[r.label,'interrupted' if r.label=='A4' else 'operator completed',
        '\\NA' if pd.isna(r.completion_time_corrected_s) else f'{r.completion_time_corrected_s:.3f}',f'{r.execution_duration_s:.3f}']
       for _,r in b.iterrows()])
print('Wrote six summary and individual-run tables from CSV.')
