# CCS Static

`fm_ccs_static` extracts scalar optimization targets from an Eclipse summary file (`UNSMRY`) using a YAML configuration.

## What It Does

The job supports two complementary extraction modes that can be combined in the same config file:

- **`fip_section`**: extracts values by FIP region number. The keyword is constructed as `{keyword}{suffix}:{fipxxx_number}`, for example `ROIPNUM:1` from `fip_keyword: FIPNUM` and `keyword: ROIP`.
- **`keyword_section`**: extracts any UNSMRY vector directly by name, for example `FOPT`, `FGPT`, or a derived field keyword.

Each configured entry writes one scalar output file named exactly as `output_name`.

## CLI

```text
fm_ccs_static -c CONFIG -cn CASE_NAME [--lint] [--schema]
```

- `-c/--config`: path to the YAML configuration file.
- `-cn/--case-name`: base path for the simulation case. The job appends `.UNSMRY` to resolve the summary file.

## Configuration

Generic example:

```yaml
{!> reference/ccs_static/config.yml!}
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

## Scalar Transformation And Normalization

Without normalization keys, the written value is:

$$
	ext{value} = \text{raw} \times m
$$

With normalization keys (`obj_min`, `obj_max`, and `obj_mean` or `obj_ref`), the written value is:

$$
	ext{value} = \left(\frac{\text{raw} - \text{obj\_mean}}{\text{obj\_max} - \text{obj\_min}}\right) \times m
$$

where:

- $m = 1$ for `max` / `maximize`.
- $m = -1$ for `min` / `minimize`.
- $m = 1$ when `optimization_direction` is omitted.

Normalization validation rules:

- If any normalization key is used, both `obj_min` and `obj_max` are required.
- Provide either `obj_mean` or `obj_ref`.
- `obj_min`, `obj_max`, and `obj_mean` / `obj_ref` must be numeric.
- `obj_max` and `obj_min` must be different.

## Validation Rules

The configuration validator enforces:

- At least one of `fip_section` or `keyword_section` must be present.
- `fip_section` requires `fip_keyword` and `fipxxx_region`.
- Each region requires `fipxxx_number`, `output_name`, `output_date`, `keyword`.
- Each `keyword_section` entry requires `source_name` and `output_name`.
- Normalization is optional per entry, but when used it must include `obj_min`, `obj_max`, and `obj_mean` or `obj_ref`.
- The deprecated `max_value` key is rejected with an informative message.
- Duplicate YAML keys are rejected.

## Manager

::: everest_models.jobs.fm_ccs_static.manager
