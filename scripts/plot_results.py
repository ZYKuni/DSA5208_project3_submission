#!/usr/bin/env python3
"""Plot measured summaries with range bars and explicit scope labels."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def main():
    p=argparse.ArgumentParser();p.add_argument("--summary",type=Path,required=True);p.add_argument("--output",type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    rows=json.loads(a.summary.read_text())
    plt.rcParams.update({"font.size":10,"axes.spines.top":False,"axes.spines.right":False,"figure.dpi":150})
    for study in dict.fromkeys(r["study"] for r in rows):
        group=[r for r in rows if r["study"]==study and r["status"]=="PASS"]
        if not group: continue
        scope=group[0]["scope"]
        label="LOCAL CONTAINER - not Atlas/Vanda" if scope=="local-container" else scope.upper()
        fig,axes=plt.subplots(1,3 if group[0]["kind"]=="strong" else 2,figsize=(12,3.8),layout="constrained")
        x=list(range(len(group)));labels=[r["label"] for r in group]
        times=[r["median_seconds"] for r in group]
        axes[0].bar(x,times,color="#3066a5",yerr=[[r["median_seconds"]-r["min_seconds"] for r in group],
            [r["max_seconds"]-r["median_seconds"] for r in group]],capsize=4)
        axes[0].set_ylabel("Solve wall time (s)");axes[0].set_title("Median; bars show min-max")
        if group[0]["kind"]=="strong":
            axes[1].plot(x,[r["speedup"] for r in group],"o-",color="#26735a");axes[1].set_ylabel("Speedup vs "+group[0]["baseline"])
        ax=axes[-1]
        ax.plot(x,[r["efficiency"] for r in group],"o-",color="#c17b25");ax.axhline(1,color="gray",ls="--",lw=1)
        ax.set_ylabel("Weak efficiency" if group[0]["kind"]=="weak" else "Relative efficiency")
        for ax in axes:
            ax.set_xticks(x,labels,rotation=30,ha="right");ax.grid(axis="y",alpha=.2);ax.set_axisbelow(True)
        fig.suptitle(study+" | "+label,fontweight="bold",fontsize=11)
        fig.savefig(a.output/(study+".png"));plt.close(fig)
if __name__=="__main__":main()
