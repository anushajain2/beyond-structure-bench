#!/bin/sh
# Matched PBE production runs (docs/matched_dft_plan.md): GaAs DFPT at 3 volumes, then the Si supercell route and Si DFPT
# (jobs already finished are skipped).
# One job at a time, 4 MPI ranks; waits for free memory before each job (other sessions share the Mac).
export PATH=$HOME/miniforge3/envs/qe/bin:$PATH OMP_NUM_THREADS=1
REPO=$(cd "$(dirname "$0")/.." && pwd)
PY=${PY:-$REPO/.venv/bin/python}
LOG=$HOME/chipff-dft/run_all.log
log() { echo "$(date '+%F %T') $*" >> $LOG; }
waitmem() {  # $1 = minimum free percentage
  while :; do
    f=$(memory_pressure | awk -F': ' '/free percentage/ {print $2+0}')
    [ "$f" -ge "$1" ] && break
    log "waiting: memory free $f% < $1%"; sleep 120
  done
}
run() {  # dir, input, output, flags
  cd "$1"
  [ -f "$3" ] && grep -q "JOB DONE" "$3" && { log "skip $1/$3 (done)"; return 0; }
  waitmem $5; log "start $1/$3 (free mem $(memory_pressure | awk -F': ' '/free percentage/ {print $2}'))"
  mpirun -np 4 $4 -in "$2" > "$3" 2> "${3%.out}.err"; rc=$?
  log "end $1/$3 rc=$rc $(grep -E 'PWSCF.*WALL|PHONON.*WALL' "$3" | tail -1)"
  return $rc
}
dfpt() {  # primitive-cell DFPT on the 4x4x4 q-grid, then force constants without the non-analytic term
  run $1 scf.in scf.out "pw.x -nk 4" 30 || exit 1
  run $1 ph.in ph.out "ph.x -nk 4" 30 || exit 1
  [ -f $1/gaas_nonac.fc ] && return 0
  cd $1 && $PY -I -c "import sys; sys.path[:0] = ['$REPO/src', '$REPO/scripts']; from pathlib import Path; import matched_dft as m; m.strip_nac(Path('gaas.dyn'), Path('nonac.dyn'))" \
    && q2r.x < q2r.in > q2r.out 2>&1 && log "q2r $1 done"
}
log "=== start"
# GaAs: DFPT at the three gamma volumes
for s in 0.985 1.000 1.015; do dfpt $HOME/chipff-dft/gaas/v$s; done
# Si: the benchmark's supercell route (set aside for gamma and alpha, docs/matched_dft_plan.md section 8)
for s in 0.960 0.975 0.985 0.990 1.000 1.015 1.030 1.045 1.060 1.080; do
  d=$HOME/chipff-dft/si/v$s
  run $d prim.in prim.out "pw.x -nk 4" 30 || exit 1
  run $d disp0.in disp0.out "pw.x -nk 1 -nd 1" 50 || exit 1
done
# Si: DFPT at all ten volumes, for gamma and the full QHA
for s in 0.960 0.975 0.985 0.990 1.000 1.015 1.030 1.045 1.060 1.080; do dfpt $HOME/chipff-dft/si_dfpt/v$s; done
log "=== all done"
