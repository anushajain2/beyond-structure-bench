# BeyondStructure Bench experimental reference dataset

`chipff_references.csv` holds the experimental values BeyondStructure Bench compares against, for 33 materials used
in semiconductor devices: 462 values of lattice parameters, bulk moduli and thermal-expansion coefficients
(linear per axis, or volumetric where the source gives the full tensor). It is meant to be reusable without the rest of the project. Every value carries its source,
a citation, a short verbatim quote where one could be taken, and a quality audit.

Regenerate it with `python scripts/export_references.py`. The underlying records, with longer notes on
conversions and conflicts, are in `data/experimental/*.json`; the audit is in `data/reference_quality.yaml`.

## Columns

| Column | Meaning |
|---|---|
| `material`, `formula`, `phase`, `class` | the material and its crystal form; `class` is one of five device classes |
| `mp_id` | the Materials Project structure the benchmark starts from |
| `property` | `lattice_parameter`, `monoclinic_beta`, `bulk_modulus` or `linear_thermal_expansion` |
| `axis` | lattice axis (`a`, `b`, `c`), or `iso` for an isotropic or polycrystalline value |
| `value`, `unit` | the number: Å, degrees, GPa, or 10⁻⁶ per K |
| `T_K` | measurement temperature where stated (empty if the source gives none); a range like `300-910` for a range value |
| `tier` | `core`: primary measurement or critically evaluated compilation, stated conditions, no unresolved conflict larger than its uncertainty. `extended`: usable but weaker; see `audit_note` |
| `quality` | `primary`, `evaluated_compilation`, `compilation`, `provisional_compilation` or `secondary` |
| `kind` | what the number is: for bulk moduli `adiabatic` (ultrasonic, Brillouin, resonance), `isothermal` (static equation of state) or `unspecified`; for expansion `point`, `short_interval_mean` (means over about 100 K intervals) or `range_average` (one constant value over a wide range, not a value at a specific temperature) |
| `rel_sigma_1` | 1-σ relative uncertainty used in the benchmark's bootstrap (for lattice parameters, of the lattice constant) |
| `sigma_from` | `source` (stated by the source), `spread` (set by disagreement between sources) or `default` |
| `audit_note` | why the value has its tier, in one line |
| `citation`, `source`, `quote` | where the value comes from: citation, the URL it was read from, and a short quote |

## Known limitations

- **HfO₂ and ZrO₂ expansion** (since 2026-10-24) is volumetric, the trace of the full expansion tensor from
  Haggerty et al., J. Am. Ceram. Soc. 97, 2213 (2014), so it includes the monoclinic-angle term the earlier
  axial (TPRC) data missed. It starts at 323 K (HfO₂) and 373 K (ZrO₂), so there is still no measured value
  at 300 K.
- **β-Si₃N₄ expansion** (since 2026-10-24) is a secondary table (Bruls et al. 2001) derived from 1981
  dilatometry whose sample is not documented; it is in the extended tier.
- **InP and NiSi expansion** are range averages, not values at 300 K. The benchmark does not use them for its
  300 K comparison.
- Several values were derived (VRH averages from elastic constants, derivatives of published fits, interval
  means from tabulated expansion); the notes in `data/experimental/` say which and how.
- Bulk moduli mix adiabatic and isothermal measurements. Converting the adiabatic ones to isothermal would
  lower them by a median of about 0.8 % (results/robustness/adiabatic_sensitivity.csv).

## Licence and citation

The values are facts reported by the cited sources; cite those sources when you use them. The compilation,
audit and code are MIT-licensed. To cite the compilation: A. Jain, *BeyondStructure Bench*, v1.1.0 (2026),
https://github.com/anushajain2/beyond-structure-bench.
