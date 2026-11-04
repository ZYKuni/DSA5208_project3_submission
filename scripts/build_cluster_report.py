#!/usr/bin/env python3
"""Build the Vanda group report exclusively from completed, archived evidence.

Requires reportlab and matplotlib. No placeholder measurements are supported.
"""
import argparse
import hashlib
import json
import statistics
from pathlib import Path
from xml.sax.saxutils import escape

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import reportlab
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Polygon
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                               TableStyle, Image, PageBreak, KeepTogether, Preformatted)

ROOT=Path(__file__).resolve().parents[1]
BLUE='#173C53'
TEAL='#157C80'
INK='#243341'


def load(path):
    return json.loads(path.read_text())


def fmt(value):
    return f'{value:.4f}' if value<1 else f'{value:.3f}'


def generate(measure, pilot, output):
    assert (measure/'exit_code.txt').read_text().strip()=='0', 'measurement job did not finish successfully'
    assert (pilot/'exit_code.txt').read_text().strip()=='0', 'pilot did not finish successfully'
    cfg=load(measure/'collection/config.json')
    manifest=load(measure/'collection/manifest.json')
    runs=load(measure/'collection/runs.json')
    rows=load(measure/'summary/summary.json')
    assert all(r['status']=='PASS' for r in rows+runs)
    assert len(runs)==sum(len(s['cases']) for s in cfg['studies'])*(cfg['repeats']+cfg['warmups'])
    assert cfg['scope']=='cluster' and cfg['cluster']=='Vanda'
    validation=load(pilot/'parallel_summary.json')
    assert validation['passed']==294 and validation['status']=='PASS'
    source=load(measure/'source_archive.json')
    team=load(ROOT/'report/source/team.json')
    pmax=cfg['maximum_test_cores']
    studies={name:[r for r in rows if r['study']==name] for name in {r['study'] for r in rows}}
    strong=studies['strong_vanda']; weak=studies['weak_vanda']
    ratio=studies['ratio_vanda']; comm=studies['communication_vanda']; solution=studies['solution_vanda']
    best=min(strong,key=lambda r:r['median_seconds'])
    best_layout=min(ratio,key=lambda r:r['median_seconds'])
    blocking=next(r for r in comm if r['label']=='sendrecv')
    overlap=next(r for r in comm if r['label']=='overlap')
    comm_ratio=blocking['median_seconds']/overlap['median_seconds']
    plots=ROOT/'report/figures/Vanda_1103';plots.mkdir(parents=True,exist_ok=True)
    plt.rcParams.update({'font.size':10,'font.family':'DejaVu Sans','axes.spines.top':False,'axes.spines.right':False,
                         'figure.dpi':160,'savefig.bbox':'tight'})

    def save(fig,name):
        fig.savefig(plots/(name+'.png'),dpi=200);fig.savefig(plots/(name+'.pdf'));plt.close(fig)

    fig,ax=plt.subplots(1,2,figsize=(9,3.3))
    mpi=sorted([r for r in strong if r['variant']=='mpi'],key=lambda r:r['cores'])
    base=next(r for r in strong if r['label']=='serial')['median_seconds']
    ax[0].plot([r['cores'] for r in mpi],[r['speedup'] for r in mpi],'o-',color=BLUE,label='MPI Sendrecv')
    ax[0].plot([1,pmax],[1,pmax],'--',color='gray',label='Ideal')
    hybrid_best=min((r for r in strong if r['variant']=='mpi_openmp'),key=lambda r:r['median_seconds'])
    omp=next(r for r in strong if r['variant']=='openmp')
    ax[0].scatter(hybrid_best['cores'],hybrid_best['speedup'],marker='s',s=48,color=TEAL,label='Best hybrid: '+hybrid_best['label'])
    ax[0].scatter(omp['cores'],omp['speedup'],marker='^',s=48,color='#B97732',label='Standalone OpenMP')
    ax[0].set(xlabel='Physical cores (R x T)',ylabel='Speedup vs serial',title='Strong scaling: N=2048')
    ax[0].legend(fontsize=7.5);ax[0].grid(alpha=.2)
    labs=[r['label'] for r in ratio]
    vals=[r['median_seconds'] for r in ratio]
    ax[1].bar(labs,vals,color=[TEAL if r is best_layout else BLUE for r in ratio],yerr=[[r['median_seconds']-r['min_seconds'] for r in ratio],
        [r['max_seconds']-r['median_seconds'] for r in ratio]],capsize=3)
    ax[1].set(xlabel=f'Ranks x threads ({pmax} cores)',ylabel='Solve time (s)',title='Fixed resource layouts')
    ax[1].tick_params(axis='x',labelsize=8);fig.tight_layout();save(fig,'strong_layout')

    fig,ax=plt.subplots(1,2,figsize=(9,3.3))
    for variant,label,marker in [('mpi','MPI','o'),('mpi_openmp','Hybrid T=2','s')]:
        data=sorted([r for r in weak if r['variant']==variant],key=lambda r:r['cores'])
        ax[0].plot([r['cores'] for r in data],[100*r['efficiency'] for r in data],marker+'-',color=BLUE if variant=='mpi' else TEAL,label=label)
    ax[0].axhline(100,ls='--',color='gray');ax[0].set(xlabel='Physical cores',ylabel='Weak efficiency (%)',title='N approximately 512 sqrt(P)')
    ax[0].legend(fontsize=8);ax[0].grid(alpha=.2)
    ax[1].bar([r['label'] for r in comm],[r['median_seconds'] for r in comm],color=[BLUE,'#C07830'],
        yerr=[[r['median_seconds']-r['min_seconds'] for r in comm],[r['max_seconds']-r['median_seconds'] for r in comm]],capsize=4)
    ax[1].set(ylabel='Solve time (s)',title=f'Communication: R={blocking["ranks"]}, T={blocking["threads"]}')
    fig.tight_layout();save(fig,'weak_communication')

    fonts=Path(matplotlib.get_data_path())/'fonts/ttf'
    pdfmetrics.registerFont(TTFont('ReportSans',str(fonts/'DejaVuSans.ttf')))
    pdfmetrics.registerFont(TTFont('ReportSansBold',str(fonts/'DejaVuSans-Bold.ttf')))
    pdfmetrics.registerFont(TTFont('ReportSansItalic',str(fonts/'DejaVuSans-Oblique.ttf')))
    pdfmetrics.registerFontFamily('ReportSans',normal='ReportSans',bold='ReportSansBold',italic='ReportSansItalic')
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='ReportBody',fontName='ReportSans',fontSize=9.6,leading=14,spaceAfter=8,textColor=colors.HexColor(INK)))
    styles.add(ParagraphStyle(name='SmallReport',fontName='ReportSans',fontSize=8.1,leading=11.2,spaceAfter=6,textColor=colors.HexColor(INK)))
    styles.add(ParagraphStyle(name='ReportTitle',fontName='ReportSansBold',fontSize=29,leading=35,textColor=colors.HexColor(BLUE),spaceAfter=18))
    styles.add(ParagraphStyle(name='Equation',fontName='ReportSans',fontSize=10.2,leading=17,spaceBefore=7,spaceAfter=10,leftIndent=12,backColor=colors.HexColor('#F0F5F7'),borderPadding=9))
    for name in ('Heading1','Heading2'):
        styles[name].textColor=colors.HexColor(BLUE)
        styles[name].fontName='ReportSansBold'
    styles.add(ParagraphStyle(name='TableHeader',parent=styles['SmallReport'],fontName='ReportSansBold',textColor=colors.white))
    styles.add(ParagraphStyle(name='CodeBlock',fontName='Courier',fontSize=8,leading=12,leftIndent=10,spaceBefore=5,spaceAfter=8,backColor=colors.HexColor('#F0F5F7'),borderPadding=8))
    styles['Heading1'].fontSize=17
    styles['Heading1'].leading=22
    styles['Heading1'].spaceAfter=13
    styles['Heading2'].fontSize=11
    styles['Heading2'].leading=15
    styles['Heading2'].spaceBefore=10
    story=[]
    def para(text,style='ReportBody'):
        story.append(Paragraph(text,styles[style]))
    def heading(text):para(text,'Heading1')
    def sub(text):para(text,'Heading2')
    def page():story.append(PageBreak())
    def table(data,widths=None):
        contents=[[Paragraph(escape(str(c)),styles['TableHeader' if i==0 else 'SmallReport']) for c in row] for i,row in enumerate(data)]
        t=Table(contents,colWidths=widths,repeatRows=1,hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor(BLUE)),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F2F6F8')]),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),
            ('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),5),('TOPPADDING',(0,0),(-1,-1),5),
            ('LINEBELOW',(0,0),(-1,0),.7,colors.HexColor(BLUE)),('LINEBELOW',(0,1),(-1,-1),.25,colors.HexColor('#DDDDDD'))]))
        story.append(t);story.append(Spacer(1,9))
    def fig(name,caption):
        story.append(Image(str(plots/(name+'.png')),width=6.75*inch,height=2.48*inch,kind='proportional'))
        para(caption,'SmallReport')
    def timing_table(data,extra=False):
        header=['Layout','N','R x T','Median (s)','Range (s)','Speedup / E']
        body=[]
        for r in data:
            metric=(f'{r["speedup"]:.2f}x / {100*r["efficiency"]:.1f}%' if r['speedup'] is not None
                    else f'{100*r["efficiency"]:.1f}% weak')
            body.append([r['label'],r['n'],f'{r["ranks"]} x {r["threads"]}',fmt(r['median_seconds']),
                         f'{fmt(r["min_seconds"])} - {fmt(r["max_seconds"])}',metric])
        table([header]+body,[67,43,53,67,115,138])

    para('DSA5208 Project 3','Heading2')
    para('Hybrid MPI + OpenMP<br/>for a 2D Poisson Solver','ReportTitle')
    para('Jacobi iteration, domain decomposition, and measured CPU scaling on NUS Vanda')
    table([['Team member','Student ID']]+[[m['name'],m['student_id']] for m in team['members']],[220,160])
    para('NUS DSA5208 | Final project report | Experiments: 3 November 2026','SmallReport')
    table([['BEST STRONG SPEEDUP','MEDIAN SOLVE TIME','16-CORE EFFICIENCY'],[f'{best["speedup"]:.2f}x',f'{best["median_seconds"]:.3f} s',f'{100*best["efficiency"]:.1f}%']],[161,161,161])
    sub('Abstract')
    para(f'We implement a serial C++17 Jacobi solver and parallel versions using MPI row slabs, OpenMP row loops, and two halo exchange methods. The complete mixed validation matrix passes 294 cases and five negative cases on Vanda. At N=2048 and {cfg["calibrated_iterations"]} fixed iterations, the fastest tested strong-scaling configuration is {best["label"]}, with median solve time {fmt(best["median_seconds"])} s and {best["speedup"]:.2f}x speedup over the serial executable. Every configuration has one warmup and five measured repetitions. The experiments compare core scaling, weak scaling, rank/thread balance, and blocking versus nonblocking communication on one CPU node.')
    para('These are measured results from a completed PBS allocation. Fixed-iteration workloads test execution efficiency; a separate small-grid convergence experiment tests time to solution. No real dataset is used.','SmallReport')
    para('Keywords: Jacobi iteration; domain decomposition; halo exchange; hybrid parallelism; strong and weak scaling.','SmallReport')
    sub('Provenance and code availability')
    para(f'Performance PBS job: {manifest["job_id"]}. Validation PBS job: 1514325.stdct-mgmt-02. Fixed source revision: {source["revision"]}.','SmallReport')

    para('Source code and run instructions: <link href="'+team['submission_repository']+'" color="#157C80">github.com/ZYKuni/DSA5208_project3_submission</link>.','SmallReport')

    page();heading('1. Algorithm and numerical contract')
    para('We solve -Δu = f on Ω = (0,1)<super>2</super> with u = 0 on the boundary. The grid has N x N interior points and spacing h=1/(N+1). A five-point finite difference stencil gives a sparse linear system. Jacobi updates each interior value using only the previous iterate, so the update is easy to parallelize locally but requires consistent neighbor values across MPI subdomains.')
    para('u<super>(k+1)</super><sub>i,j</sub> = ¼ [u<super>(k)</super><sub>i-1,j</sub> + u<super>(k)</super><sub>i+1,j</sub> + u<super>(k)</super><sub>i,j-1</sub> + u<super>(k)</super><sub>i,j+1</sub> + h<super>2</super>f<sub>i,j</sub>]','Equation')
    para('Two solution buffers alternate roles after each sweep. A third array stores the right-hand side. Values use double precision and row-major layout, with contiguous columns. The serial cost is O(KN<super>2</super>) for K sweeps, and the principal array storage is approximately 24(N+2)<super>2</super> bytes. At N=2048, this is about 96 MiB before halo and runtime overhead.')
    sub('Manufactured solutions')
    para('The continuous test uses u* = sin(πx)sin(πy) and f = 2π<super>2</super>u*. Its difference from the converged discrete solution measures second-order discretization error. Separate discrete sine and asymmetric mixed-mode problems use analytically derived discrete eigenvalues; these isolate iteration and indexing correctness from discretization error. Zero forcing checks the initially converged case and avoids division by zero.')
    para('For a discrete mode sin(pπx)sin(qπy), λ<sub>p,q</sub> = 4h<super>-2</super>[sin<super>2</super>(pπh/2) + sin<super>2</super>(qπh/2)]. From a zero initial iterate, its exact Jacobi amplitude after K sweeps is 1 - (1 - h<super>2</super>λ<sub>p,q</sub>/4)<super>K</super>. Superposing unequal (p,q) modes gives an independent finite-iteration reference that detects axis swaps and halo/indexing errors.','SmallReport')
    sub('Stopping and timing')
    para('The relative residual is ||f - A<sub>h</sub>u||<sub>2</sub> / ||f||<sub>2</sub>, with an absolute residual when the forcing norm is zero. Each rank forms a local squared sum; MPI_Allreduce sums before taking the square root. Convergence mode checks the initial iterate and then the requested intervals. Fixed mode always performs exactly K iterations, even when a tolerance happens to be met. A check is forced at the final requested iteration.')
    para('The solve timer includes sweeps, halo exchanges, buffer swaps, scheduled residual evaluations, and their reductions. It excludes allocation, right-hand-side initialization and norm, final diagnostics, optional gathering, and file output. MPI reports the maximum rank elapsed time, after one starting barrier. Serial and standalone OpenMP use the same timer scope. Job duration and MPI process startup time are excluded.')
    sub('Why parallelization is challenging')
    para('Iterations depend on the previous global state. Halo messages, global convergence reductions, synchronization, load balance, and memory locality affect performance. The nonblocking version must compute only rows whose inputs are already valid, and must complete sends before old storage can be reused. The problem is therefore not embarrassingly parallel.')

    page();heading('2. Parallel design decisions')
    sub('MPI decomposition and exchange')
    para('R MPI ranks own contiguous row slabs. Quotient/remainder partitioning gives the first N mod R ranks one extra row; ownership differs by at most one row. Each slab keeps an upper and lower ghost row. Global row offsets preserve the manufactured forcing, and MPI_PROC_NULL preserves physical boundaries. The implementation rejects R>N rather than creating empty owners.')
    para('The Sendrecv method exchanges two rows before updating the entire slab. The overlap method posts two receives and two sends, updates interior rows 2 through rows-1, waits for all four requests, and updates the boundary rows. One- and two-row slabs have explicit guards, preventing repeated updates. Current-solution ghosts are exchanged again before residual evaluation; this straightforward implementation retains some repeated communication.')
    diagram=Drawing(483,70)
    for rank,(start,end) in enumerate(((1,3),(4,5),(6,7))):
        x=rank*165
        diagram.add(Rect(x,22,145,40,fillColor=colors.HexColor('#EDF4F5'),strokeColor=colors.HexColor(TEAL),strokeWidth=.7))
        diagram.add(String(x+72.5,46,f'Rank {rank}',fontName='ReportSansBold',fontSize=9,textAnchor='middle',fillColor=colors.HexColor(BLUE)))
        diagram.add(String(x+72.5,31,f'owns global rows {start}-{end}',fontName='ReportSans',fontSize=8,textAnchor='middle'))
        if rank<2:
            diagram.add(Line(x+146,42,x+163,42,strokeColor=colors.HexColor(TEAL)))
            diagram.add(Polygon([x+146,42,x+150,45,x+150,39],fillColor=colors.HexColor(TEAL),strokeColor=None))
            diagram.add(Polygon([x+163,42,x+159,45,x+159,39],fillColor=colors.HexColor(TEAL),strokeColor=None))
    diagram.add(String(0,6,'Example: N=7, R=3. Adjacent owners exchange boundary rows into ghost storage.',fontName='ReportSans',fontSize=8,fillColor=colors.HexColor(INK)))
    story.append(diagram)
    sub('OpenMP integration')
    para('The MPI driver accepts update, residual, and norm kernels through a LocalKernels interface. The OpenMP kernels distribute outer rows with schedule(static), retain contiguous inner-column accesses, and use reductions for local sums. Checks run before the parallel region; updates write distinct output cells. Dynamic teams are disabled, and the reported team size is probed in a real parallel region and checked across ranks.')
    para('The hybrid driver requests MPI_THREAD_FUNNELED and verifies the provided level. All MPI operations occur on the initializing thread outside OpenMP regions, consistent with the Open MPI interface [1]. Loop worksharing has an end barrier [2]. This avoids concurrent MPI calls from worker threads but still incurs a parallel-region entry and exit per kernel call.')
    sub('Expected tradeoffs')
    para('Each rank performs about N<super>2</super>/R updates and exchanges up to two N-element rows per sweep. Increasing R reduces compute per rank while leaving message length unchanged; global residual reductions add latency. At fixed P=R x T, fewer ranks reduce halo boundaries, but more threads add barriers and can share memory bandwidth. The nonblocking path can hide transfer time only when enough interior work exists and the MPI runtime makes progress. Its separate interior/boundary OpenMP calls can cost more than they save.')
    para('We do not use persistent OpenMP teams, explicit SIMD, parallel first-touch, a 2D process grid, multigrid, or asynchronous convergence. Array allocation and initialization are serial within each rank. These choices keep the baseline auditable and provide concrete explanations for saturation, without claiming to have isolated each mechanism experimentally.')

    page();heading('3. Correctness validation')
    table([['Validation on Vanda','Observed result'],['CTest suite','9 / 9 passed'],
           ['Mixed OpenMP / hybrid matrix','294 / 294 oracle cases; 5 negative cases'],
           ['MPI-only matrix','124 / 124 cases; 4 negative cases'],
           ['Bound hybrid smoke runs','Sendrecv and overlap, 2 ranks x 2 threads passed']],[270,213])
    para('The matrices overlap; these counts are not independent samples to be added. They cover one/two-row slabs, uneven ownership, asymmetric forcing, K=0 and odd/even K, zero forcing, convergence cadence, halo boundaries, full-field comparison to independent dense/modal oracles, and independent residual checks. Full fields use an absolute-plus-relative tolerance of 1e-10 + 1e-10 |reference|. The performance collector separately checks executable identity, ranks, actual threads, communication mode, finite diagnostics, stopping rules, and exit status.')
    para('The first 4-CPU pilot failed: a 12-thread correctness case timed out, followed by an unhelpful missing-result exception. The exception handling was fixed without changing the numerical kernels or tolerances. The successful pilot used 16 CPUs and passive OpenMP waiting. A later performance-preparation job failed on a Python probe syntax error before measurements; its logs are retained. Neither failed job contributes timing samples.')
    sub('Discretization accuracy and portable reproduction')
    local=load(ROOT/'docs/A/results/A_1104/local/serial/serial_validation_summary.json')
    table([['Interior grid N','Maximum error in continuous-sine solution','Error ratio']]+[[n,f'{error:.6e}','-' if i==0 else f'{local["refinement_ratios"][i-1]:.4f}'] for i,(n,error) in enumerate(zip((7,15,31),local['refinement_max_errors']))],[100,260,123])
    para('Serial manufactured-solution refinement, recorded in the later Linux verification. Halving h reduces the maximum error by approximately four, consistent with the second-order spatial stencil. These error values are correctness evidence, not additional Vanda timing samples.','SmallReport')
    para('A subsequent portable verification expanded the mixed matrix to 390 cases plus five negative cases, including the missing OpenMP-kernel layouts 1 x 4, 2 x 1, and 3 x 1 under both exchange methods. Fresh Ubuntu builds and GitHub x86_64 CI passed all four configurations: serial (6 CTest groups), MPI (7), OpenMP (8), and hybrid (9). A source-package extraction was independently rebuilt and checked. The measured solver sources and CMake remain identical to the Vanda revision; later test counts must not be substituted for the historical 294 Vanda cases.')
    para('An independent audit of the Vanda job output checked all 180 launches, 150 measured samples, 30 configurations, evidence archive hashes, and the statistics used below.','SmallReport')

    page();heading('4. Experimental method')
    table([['Measurement environment','Recorded value'],['Platform / allocation',f'Vanda; 1 node; {cfg["assigned_physical_cores"]} assigned physical cores'],
           ['CPU',cfg['cpu_model']],['Node physical cores',cfg['physical_cores_per_node']],
           ['Toolchain','GCC 12.3.0; Open MPI 4.1.8; CMake 3.26.3'],
           ['Compilation','C++17, Release -O3 -DNDEBUG; OpenMP -fopenmp; no fast-math'],
           ['Repetitions',f'{cfg["warmups"]} warmup + {cfg["repeats"]} measured, sequential case order'],
           ['Formal OpenMP environment','DYNAMIC=FALSE; PLACES=cores; PROC_BIND=close; WAIT_POLICY=ACTIVE']],[165,318])
    sub('Workloads and comparisons')
    purposes={'strong_vanda':('Fixed N=2048; K=2600','Serial executable'),
              'weak_vanda':('N=round(512 sqrt(P)); K=2600','MPI, one rank'),
              'ratio_vanda':('N=2048; 16 total cores','16 ranks x 1 thread'),
              'communication_vanda':('N=2048; 4 ranks x 4 threads','Sendrecv exchange'),
              'solution_vanda':('N=127; tolerance 1e-8','Serial, same tolerance')}
    table([['Study','Count','Work held comparable','Reference']]+[[st['id'].replace('_vanda','').title(),len(st['cases']),*purposes[st['id']]] for st in cfg['studies']],[83,48,200,152])
    para('Thirty configurations x (one warmup + five measured launches) give 180 launches and 150 formal samples. Fixed-sweep studies use a residual check every 10 iterations. Strong efficiency is S(P)/P relative to the serial median; weak efficiency is t(MPI,1)/t(P). Fixed-core and communication comparisons are runtime ratios at equal resources, rather than serial scaling efficiencies.','SmallReport')
    sub('Placement, timing, and experimental controls')
    para('Source was exported from the fixed Git revision and compiled on a Vanda compute node, then the same executable hashes were verified for measurement. The export contains no .git directory; the archive SHA256 and recorded source/binary hashes establish identity. PBS routes the auto queue to batch_cpu. Actual memory allocation is recorded in scheduler.txt and may exceed the requested minimum. No GPUs are used.','SmallReport')
    para('The launcher uses --map-by slot:PE=T --bind-to core --report-bindings [3]. Before timing, a real MPI probe for every R:T layout confirms exactly T physical cores per rank, no inter-rank overlap, and containment within the PBS CPU set. Standalone serial is constrained to that allocation but is not pinned to one individual core; OpenMP applies its own core placement. Thus this is a single-allocation comparison, not a fully controlled NUMA or frequency experiment.','SmallReport')

    page();heading('5. Strong scaling and rank/thread balance')
    para(f'For strong scaling, N=2048, K={cfg["calibrated_iterations"]}, and the residual is checked every 10 iterations. K was selected using the successful pilot serial calibration ({cfg["calibration_seconds"]:.3f} s for 1000 iterations) to target approximately 15 seconds serial work. Speedup S(P)=median(t_serial)/median(t_P); efficiency E(P)=S(P)/P. Five repetitions give a median and observed min-max range, not a confidence interval.')
    fig('strong_layout','Figure 1. Strong-scaling speedup and fixed-core layout runtime. Bars show medians; whiskers show the measured minimum and maximum. MPI points use one thread per rank; the best hybrid and standalone OpenMP are also shown.')
    timing_table(strong)
    para(f'The fastest tested strong configuration is {best["label"]}: {fmt(best["median_seconds"])} s, {best["speedup"]:.2f}x speedup, and {100*best["efficiency"]:.1f}% efficiency. In the separate {pmax}-core layout study, {best_layout["label"]} is fastest at {fmt(best_layout["median_seconds"])} s. Repeated configurations belong to different sequential study blocks, so their medians need not be identical. Cross-block variation should temper claims of small differences.','SmallReport')
    mpi1=next(r for r in strong if r['variant']=='mpi' and r['cores']==1)
    if mpi1['max_seconds']/mpi1['min_seconds']>1.5:
        para(f'The one-rank MPI samples span {fmt(mpi1["min_seconds"])} to {fmt(mpi1["max_seconds"])} s, despite identical commands and successful validation. The cause was not isolated, so this anomaly must not be interpreted as a stable MPI overhead. No samples were removed. The R=1, T={pmax} layout also has a wide range; the ranking of nearby layout medians is tentative.','SmallReport')
    if any(r['efficiency']>1.05 for r in strong):
        para('Some measured efficiencies exceed 100% relative to the serial executable. This can reflect cache working-set changes, compiler/kernel differences, frequency or node-load variation; it does not imply more than one core of work per core. No cache counters or frequency traces were collected, so the cause of apparent superlinear speedup is not established.','SmallReport')

    page();heading('6. Weak scaling and communication method')
    para(f'Weak scaling keeps approximately 512 squared interior points per core, using N=round(512 sqrt(P)) and the same K={cfg["calibrated_iterations"]}. The maximum rounding error in work per core is {100*max(abs(r["work_per_core_ratio"]-1) for r in weak):.3f}%. Weak efficiency is median(t_MPI,1)/median(t_P). It measures fixed-sweep execution, not equivalent PDE convergence as the grid is refined.')
    fig('weak_communication','Figure 2. Weak efficiency relative to the one-rank MPI baseline, and the matched Sendrecv/overlap comparison. Communication bars show median and min-max solve times at the same R:T layout.')
    timing_table(weak)
    para(f'For the communication comparison, Sendrecv takes {fmt(blocking["median_seconds"])} s and overlap takes {fmt(overlap["median_seconds"])} s; the blocking/overlap ratio is {comm_ratio:.3f}. A ratio above one favors overlap. Nonblocking communication is not evidence by itself that communication and computation progressed simultaneously. The experiment measures complete solve time and does not collect a communication timeline.','SmallReport')
    if max(blocking['min_seconds'],overlap['min_seconds'])<=min(blocking['max_seconds'],overlap['max_seconds']):
        para('The two observed timing ranges overlap. This run does not demonstrate a robust performance advantage for nonblocking exchange. More repetitions with interleaved case order would be needed to assess a small median difference.','SmallReport')
    weak_mpi=next(r for r in weak if r['variant']=='mpi' and r['cores']==pmax)
    weak_hybrid=next(r for r in weak if r['variant']=='mpi_openmp' and r['cores']==pmax)
    para(f'At {pmax} cores, weak efficiency is {100*weak_mpi["efficiency"]:.1f}% for MPI and {100*weak_hybrid["efficiency"]:.1f}% for the T=2 hybrid. The overlap median is {abs(100*(overlap["median_seconds"]/blocking["median_seconds"]-1)):.1f}% '+('lower' if overlap['median_seconds']<blocking['median_seconds'] else 'higher')+' than Sendrecv. These single-node results combine memory, cache, synchronization, and communication costs. More MPI ranks shrink the independent interior; more threads increase region coordination. No bandwidth counters or NUMA experiment were collected, so these are possible mechanisms rather than established hardware causes.','SmallReport')

    page();heading('7. Time to solution and conclusions')
    para('A separate N=127 continuous-sine problem runs in convergence mode with tolerance 1e-8, check interval 20, and a 200000-iteration cap. These runs compare the same discrete problem and stopping threshold. The table reports actual work and residuals from all measured samples, rather than the iteration cap.')
    soldata=[]
    for r in solution:
        samples=[x['result'] for x in runs if x['study']==r['study'] and x['label']==r['label'] and not x['warmup']]
        assert all(s['converged'] and s['stop_reason']=='tolerance' for s in samples)
        iters=sorted({s['actual_iterations'] for s in samples})
        soldata.append([r['label'],fmt(r['median_seconds']),','.join(map(str,iters)),
                        f'{max(s["final_relative_residual"] for s in samples):.3e}',f'{r["speedup"]:.2f}x'])
    table([['Layout','Median s','Actual iterations','Max final rel. residual','Speedup']]+soldata,[93,70,105,139,76])
    para('Small-grid time to solution can be dominated by coordination, so it need not follow the large fixed-work ranking. For Jacobi, slow damping of low-frequency modes also means that finer-grid solution time is much larger than a short fixed-iteration timing. The large-grid scaling runs are intentionally not presented as converged solutions.')
    sub('Conclusions and limits')
    para(f'The implementation is numerically validated across serial, MPI, standalone OpenMP, and hybrid execution. On the tested Vanda allocation, {best["label"]} gives the lowest strong-study median, while {best_layout["label"]} leads the fixed-{pmax}-core comparison. The data demonstrate that the rank/thread balance and communication path are experimental choices, not automatic improvements. All conclusions apply to these grid sizes, source revision, compiler, placement, and one CPU node.')
    para('We have not measured multi-node scaling or GPU execution. Open MPI logs warnings about unavailable PBS/UCX plugins; single-node execution and actual rank affinity were verified, but inter-node placement and network overlap have not been validated. The node is not reserved in its entirety. Case order is sequential, samples are limited to five, and no hardware counters or frequency controls are used. Follow-up work should test multiple nodes, randomized study order, parallel first-touch, persistent thread teams, and a 2D decomposition.')
    para('All inputs are manufactured numerical problems. There is no real dataset from which to draw application-domain conclusions. The results concern solver correctness and parallel execution efficiency.')
    sub('AI usage')
    para('An OpenAI coding assistant supported implementation, code review, testing, command execution, evidence checking, figures, and drafting. Team members remain responsible for experimental design and interpretation. AI-generated prose and synthetic fixtures were not treated as measured evidence; performance claims trace to archived Vanda logs and validation output.','SmallReport')

    page();heading('8. Reproduction')
    para('The root README describes the four executables and local build/test commands. The cluster scripts contain PBS requests, compute-node compilation, correctness validation, calibration, affinity checks, collection, and aggregation. Use a project allocation authorized for your own account.')
    code=f"""cmake -S . -B build -DCMAKE_BUILD_TYPE=Release \\
  -DENABLE_MPI=ON -DENABLE_OPENMP=ON
cmake --build build --parallel 2
ctest --test-dir build --output-on-failure

OMP_NUM_THREADS=4 mpiexec --map-by slot:PE=4 \\
  --bind-to core -n 4 build/poisson_hybrid \\
  --n 2048 --mode fixed --iterations {cfg['calibrated_iterations']} \\
  --check-every 10 --communication sendrecv"""
    story.append(Preformatted(code,styles['CodeBlock']))
    para('Run from the submission directory. Install GCC, CMake, Python 3, and Open MPI development/runtime tools first. Backslashes above continue shell commands. Quick correctness runs on small machines should set OMP_WAIT_POLICY=PASSIVE and OMP_DYNAMIC=FALSE; do not reuse that setting as the formal ACTIVE timing environment.','SmallReport')
    para('Fixed source archive SHA256:<br/>'+source['sha256'],'SmallReport')
    sub('References')
    para('[1] Open MPI 4.1.8, MPI_Init_thread documentation. <link href="https://www.open-mpi.org/doc/v4.1/man3/MPI_Init_thread.3.php" color="#174B78">Official reference</link>. Thread-support semantics; accessed 3 November 2026.','SmallReport')
    para('[2] OpenMP API 5.0, section 2.9.2, Worksharing-Loop Construct. <link href="https://www.openmp.org/spec-html/5.0/openmpsu41.html" color="#174B78">Official specification</link>. Cited for basic loop semantics, not as a claim of runtime version.','SmallReport')
    para('[3] Open MPI 4.1.8, mpirun documentation. <link href="https://www.open-mpi.org/doc/v4.1/man1/mpirun.1.php" color="#174B78">Official reference</link>. Rank mapping and core binding.','SmallReport')
    para('[4] Project source: src/solver_mpi.cpp, src/kernel_openmp.cpp, and the validation scripts in the submission repository. Numerical equations and implementation descriptions are derived directly from these sources.','SmallReport')

    def footer(canvas,doc):
        canvas.saveState();canvas.setStrokeColor(colors.HexColor('#D5E0EA'));canvas.line(48,41,547,41)
        canvas.setFont('ReportSans',7.5);canvas.setFillColor(colors.HexColor('#536579'))
        canvas.drawString(48,28,'DSA5208 | MPI + OpenMP Poisson solver | Vanda experiments')
        canvas.drawRightString(547,28,f'{doc.page:02d}');canvas.restoreState()
    output.parent.mkdir(parents=True,exist_ok=True)
    doc=SimpleDocTemplate(str(output),pagesize=(595.28,841.89),rightMargin=48,leftMargin=48,
                          topMargin=43,bottomMargin=55,title='DSA5208 Project 3: MPI + OpenMP Poisson Solver',
                          author='; '.join(m['name'] for m in team['members']))
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    facts={'performance_job':manifest['job_id'],'source_revision':source['revision'],
           'configurations':len(rows),'launches':len(runs),'measured_samples':sum(not x['warmup'] for x in runs),
           'best_strong':best,'best_layout':best_layout,'blocking_over_overlap':comm_ratio,
           'pdf_sha256':hashlib.sha256(output.read_bytes()).hexdigest()}
    output.with_name(output.stem+'_facts.json').write_text(json.dumps(facts,indent=2)+'\n')
    print(json.dumps(facts,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--measure',type=Path,required=True)
    parser.add_argument('--pilot',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=ROOT/'output/pdf/Project3_report.pdf')
    args=parser.parse_args();generate(args.measure,args.pilot,args.output)
