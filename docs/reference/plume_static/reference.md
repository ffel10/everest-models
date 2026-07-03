# Plume Static

`fm_plume_static` extracts scalar optimization targets from an Eclipse summary file (`UNSMRY`) using a YAML configuration.

## What It Does

The job supports two complementary extraction modes that can be combined in the same config file:

- **`fip_section`**: extracts values by FIP region number. The keyword is constructed as `{keyword}{suffix}:{fipxxx_number}`, for example `ROIPNUM:1` from `fip_keyword: FIPNUM` and `keyword: ROIP`.
- **`keyword_section`**: extracts any UNSMRY vector directly by name, for example `FOPT`, `FGPT`, or a derived field keyword.

Each configured entry writes one scalar output file named exactly as `output_name`.

## CLI

```text
fm_plume_static -c CONFIG -cn CASE_NAME [--lint] [--schema]
```

- `-c/--config`: path to the YAML configuration file.
- `-cn/--case-name`: base path for the simulation case. The job appends `.UNSMRY` to resolve the summary file.

## Configuration

Generic example:

```yaml
{!> reference/plume_static/config.yml!}
```

## FIP Vector Construction

For a `fip_section`, the job constructs the UNSMRY vector name as:

$$
\text{vector} = \text{keyword} + \text{suffix}[\text{1:3}] + \text{:} + \text{fipxxx\_number}
$$

where suffix is the 3-character tail of `fip_keyword` after `FIP`.

For example, `fip_keyword: FIPNUM` and `keyword: ROIP` and `fipxxx_number: 2` produces `ROIPNUM:2`.

## Time Selection

The `output_date` field controls which time step value is extracted:

| `output_date` value | Behaviour |
|---|---|
| `YYYY-MM-DD` | value at that exact report date |
| `min` | minimum value across all time steps |
| `max` | maximum value across all time steps |
| `mean` | mean value across all time steps |
| omitted | last time step |

## Scalar Transformation

The raw extracted value is transformed before writing:

$$
\text{value} = \left( \frac{\text{raw} - \text{factor}}{\text{scale}} \right) \times m
$$

where:

- `factor` defaults to `0` when omitted.
- `scale` defaults to `1` and must be non-zero.
- $m = 1$ for `max` / `maximize`.
- $m = -1$ for `min` / `minimize`.
- $m = 1$ when `optimization_direction` is omitted.

## Validation Rules

The configuration validator enforces:

- At least one of `fip_section` or `keyword_section` must be present.
- `fip_section` requires `fip_keyword` and `fipxxx_regions`.
- Each region requires `fipxxx_number`, `output_name`, `output_date`, `keyword`.
- Each `keyword_section` entry requires `source_name` and `output_name`.
- `scale` must be non-zero.
- The deprecated `max_value` key is rejected with an informative message.

## Tasks

::: everest_models.jobs.fm_plume_static.tasks
