from everest_models.jobs.shared.arguments import bootstrap_parser, get_parser
from everest_models.jobs.shared.validators import valid_input_file

CONFIG_ARGUMENT = "-c/--config"


@bootstrap_parser
def build_argument_parser(skip_type=False):
    parser, required_group = get_parser(
        description=(
            "Compute plume distance targets from a YAML configuration, with optional "
            "EGRID and UNRST overrides from the command line."
        )
    )
    required_group.add_argument(
        *CONFIG_ARGUMENT.split("/"),
        required=True,
        type=valid_input_file if not skip_type else str,
        help="Path to plume dynamic YAML configuration file.",
    )
    parser.add_argument(
        "-cn",
        "--case-name",
        default=None,
        help=(
            "Case base path used to resolve CASE.EGRID and CASE.UNRST when explicit "
            "paths are not provided."
        ),
    )
    parser.add_argument("--egrid", default=None, help="Path to EGRID file.")
    parser.add_argument("--unrst", default=None, help="Path to UNRST file.")
    parser.add_argument(
        "--output-date",
        default=None,
        help="Target report date in YYYY-MM-DD format. Overrides step when provided.",
    )
    parser.add_argument(
        "--step",
        type=int,
        default=None,
        help="UNRST time-step index. Defaults to the last report step.",
    )
    return parser