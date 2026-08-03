# CCS Dynamic

`fm_ccs_dynamic` computes plume-distance targets from `EGRID` and `UNRST` data using a YAML configuration.

## What It Does

Each entry in `distance_calculations` produces one scalar target file named exactly as `output_name`.

Supported calculation types:

- `point`: shortest 2D distance from matching active cells to a point.
- `line`: shortest 2D distance from matching active cells to a finite line segment.
- `plume_extent`: longest 2D distance from matching active cells to a point.

Property filtering is based on one or more `property` / `threshold` / `output_date` combinations from the YAML file.
Only cells matching the active property filter contribute to each target.

## CLI

```text
fm_ccs_dynamic -c CONFIG -cn CASE_NAME [--egrid EGRID] [--unrst UNRST] [--output_date YYYY-MM-DD|min|max|mean] [--step STEP]
```

Path resolution order:

- `--egrid` overrides YAML `egrid` and `case`.
- `--unrst` overrides YAML `unrst` and `case`.
- `-cn/--case_name` resolves `CASE_NAME.EGRID` and `CASE_NAME.UNRST` when explicit paths are not given.

Time selection order:

- Per-calculation `step` overrides everything else for that calculation.
- CLI `--step` overrides YAML `step`.
- Per-calculation `output_date` overrides top-level YAML `output_date`.
- CLI `--output_date` overrides top-level YAML `output_date` when `--step` is not set.
- If no explicit step is chosen, the job falls back to YAML `step` and then the last report step.

## Configuration

Generic example:

```yaml
{!> reference/ccs_dynamic/config.yml!}
```

## Distance Calculation

The job works on active grid-cell centers from the `EGRID` file. For each calculation, it first filters the active cells using the configured `property`, `threshold`, and selected report step from `UNRST`. Distances are then computed only for the cells that pass that filter.

Only the horizontal coordinates are used in the distance calculation. The `z` coordinate is not part of the optimization scalar; it is only used later when writing polygon output.

### Property Mask Construction

The filter is implemented as a boolean mask over active cells.

For each configured property/date/threshold combination, the job reads the selected `UNRST` keyword at the chosen report step and marks a cell as active for that filter when:

$$
	ext{mask}_i = \left( v_i \ge t \right)
$$

where $v_i$ is the property value in active cell $i$ and $t$ is the configured threshold.

In practice, this means:

- `property` selects the `UNRST` keyword, for example `SGAS`.
- `threshold` sets the lower cutoff.
- `output_date` or `step` selects which report step is used to build the mask.

If multiple property filters are defined, the code builds one mask per unique `(property, threshold, date)` combination and computes separate distance columns for each of them. Those derived columns are then aggregated into the final scalar output.

If no property is provided, the mask defaults to all active cells in the grid.

### Point

For `type: point`, the raw distance is the 2D Euclidean distance from each selected cell center $(x_i, y_i)$ to the configured point $(x_0, y_0)$:

$$
d_i = \sqrt{(x_i - x_0)^2 + (y_i - y_0)^2}
$$

The scalar written for the calculation is the minimum of these distances.

### Line

For `type: line`, the job builds a finite line segment centered at $(x_0, y_0)$ using `angle` and `line_length`.

- `angle` is interpreted clockwise from north.
- `line_length` is the half-length of the segment, so the line extends that far in both directions from the anchor point.

The segment endpoints are:

$$
	heta = \mathrm{radians}(\text{angle} \bmod 360)
$$

$$
dx = \sin(\theta), \quad dy = \cos(\theta)
$$

$$
A = (x_0 - L dx, y_0 - L dy), \quad B = (x_0 + L dx, y_0 + L dy)
$$

where $L = \text{line_length}$.

For each cell center, the code projects the point onto the segment, clamps the projection to the finite segment, and then computes the 2D Euclidean distance to that closest point on the segment. The scalar written for the calculation is the minimum of those distances.

If `line_length = 0`, the line calculation degenerates to the same point-distance formula used by `type: point`.

### Plume Extent

For `type: plume_extent`, the raw distances are computed with the same point-distance formula as `type: point`:

$$
d_i = \sqrt{(x_i - x_0)^2 + (y_i - y_0)^2}
$$

The difference is in the aggregation step: the scalar written for the calculation is the maximum of the matching distances, not the minimum. In other words, this mode measures the farthest selected plume cell from the reference point.

### Multiple Property Filters

If the YAML defines multiple property/threshold/date combinations, the job computes one distance array per matching property filter and writes additional property-specific output files. The main scalar for a calculation is then aggregated across those generated columns:

- `point` uses the minimum across matching columns
- `line` uses the minimum across matching columns
- `plume_extent` uses the maximum across matching columns

## Scalar Transformation

For each calculation, the raw scalar is written as-is unless normalization keys are configured.

Without normalization:

$$
	ext{value} = \text{raw} \times m
$$

With normalization (`obj_min`, `obj_max`, and `obj_mean` or `obj_ref`):

$$
	ext{value} = \left(\frac{\text{raw} - \text{obj\_mean}}{\text{obj\_max} - \text{obj\_min}}\right) \times m
$$

where $m = 1$ for `max` / `maximize`, and $m = -1$ for `min` / `minimize`.

## Output Files

For each calculation, the job writes:

- One scalar file with the exact name from `output_name`.
- Additional property-specific scalar files when multiple property filters are active.
- Optional polygon files when `writing_polygons: true`.

Polygon outputs:

- `line` writes a visualization polygon for the configured line.
- `line` writes `*_mindist.pol` files to the nearest cell.
- `point` writes `*_mindist.pol` files to the nearest cell.
- `plume_extent` writes `*_maxdist.pol` files to the farthest matching cell.

## Validation Rules

The configuration validator enforces:

- Required top-level keys: `property`, `threshold`, `output_date`, `distance_calculations`
- Allowed calculation types: `point`, `line`, `plume_extent`
- Required calculation keys: `type`, `output_name`, `optimization_direction`, `x`, `y`
- Duplicate YAML keys are rejected

## Manager

::: everest_models.jobs.fm_ccs_dynamic.manager
